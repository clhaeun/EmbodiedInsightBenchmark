"""Symbolic time system for SF (Scenario Flexibility) evaluation.

Manages non-stationary environment state that evolves with each action.
Each action costs one time_step (= step_duration_minutes).
The system is purely symbolic — no PhysX physics, just lookup-table state.

Multi-strategy design with independent "bonus tracks":
  - Base: cake extraction + doneness
  - Track A: cream quality (liquid / dirty-whipped / clean-whipped)
  - Track B: chocolate quality (pieces / melted via kettle water bath)
  - Track C: presentation (platter from cabinet)
  - Track D: extra baking (power restore + oven reheat)

Each track has independent time costs and hidden variables,
creating genuine strategic diversity for SF measurement.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class _DoorHistory:
    """Track open/close periods for a single appliance door."""
    is_open: bool = False
    periods: List[tuple] = field(default_factory=list)
    current_open_step: Optional[int] = None

    def open(self, step: int):
        if self.is_open:
            return
        self.is_open = True
        self.current_open_step = step

    def close(self, step: int):
        if not self.is_open:
            return
        self.is_open = False
        if self.current_open_step is not None:
            self.periods.append((self.current_open_step, step))
        self.current_open_step = None

    def total_open_steps(self, at_step: int) -> int:
        total = 0
        for open_s, close_s in self.periods:
            # Only count open steps up to at_step
            effective_close = min(close_s, at_step)
            if effective_close > open_s:
                total += effective_close - open_s
        if self.is_open and self.current_open_step is not None:
            if at_step > self.current_open_step:
                total += at_step - self.current_open_step
        return total

    def was_ever_opened(self) -> bool:
        return len(self.periods) > 0 or self.is_open


class TimeSystem:
    """Symbolic time system for SF tasks with multi-strategy support."""

    def __init__(self, config: dict):
        self.config = config
        self.time_step: int = 0

        # Appliance door tracking
        self.oven_door = _DoorHistory()
        self.fridge_door = _DoorHistory()

        # Power state
        self.power_restored: bool = False
        self.water_available: bool = False
        self.oven_turned_on_at: Optional[int] = None

        # Cake location tracking
        self.cake_in_oven: bool = True
        self.cake_removed_at: Optional[int] = None

        # Cream location tracking
        self.cream_in_fridge: bool = True
        self.cream_removed_at: Optional[int] = None

        # --- Cream quality track ---
        # "liquid" (default) / "dirty_whipped" / "clean_whipped"
        self.cream_quality: str = "liquid"
        self.cream_applied: bool = False

        # --- Chocolate quality track ---
        # "raw" (default) / "pieces" (prepared) / "melted" (water bath)
        self.chocolate_quality: str = "raw"
        self.chocolate_prepared: bool = False
        self.chocolate_applied: bool = False

        # --- Whisk track ---
        self.whisk_clean: bool = False  # starts dirty

        # --- Kettle track ---
        # Kettle cools over time. Hot water needed for chocolate melting.
        self.bowl_has_hot_water: bool = False
        self.bowl_water_temp: Optional[float] = None
        self.bowl_water_poured_at: Optional[int] = None

        # --- Presentation track ---
        self.cabinet_opened: bool = False
        self.platter_retrieved: bool = False
        self.platter_used: bool = False

        # Snapshot for save/restore
        self._snapshot: Optional[dict] = None

    # ------------------------------------------------------------------
    # Time progression
    # ------------------------------------------------------------------
    def advance_time(self) -> Dict[str, Any]:
        self.time_step += 1
        events = {}

        restore_step = self.config.get("power_restore_step")
        if restore_step and self.time_step >= restore_step and not self.power_restored:
            self.power_restored = True
            self.water_available = True
            events["power_restored"] = True

        return events

    # ------------------------------------------------------------------
    # Temperature calculations
    # ------------------------------------------------------------------
    def get_oven_temp(self) -> float:
        t = self.time_step
        c = self.config
        room = c.get("room_temp", 23.0)
        base = max(room, c["oven_initial_temp"] - c["oven_cooling_closed"] * t)

        extra_rate = c["oven_cooling_opened"] - c["oven_cooling_closed"]
        open_steps = self.oven_door.total_open_steps(t)
        extra_loss = extra_rate * open_steps

        reheat = 0.0
        if self.oven_turned_on_at is not None:
            preheat_steps = c.get("oven_preheat_steps", 3)
            dt = t - self.oven_turned_on_at
            if dt >= preheat_steps:
                reheat = c["oven_initial_temp"]
            else:
                reheat = c["oven_initial_temp"] * (dt / preheat_steps)

        if reheat > 0:
            return min(c["oven_initial_temp"], max(room, reheat))

        return max(room, base - extra_loss)

    def get_fridge_temp(self) -> float:
        t = self.time_step
        c = self.config
        room = c.get("room_temp", 23.0)
        base = min(room, c["fridge_initial_temp"] + c["fridge_warming_closed"] * t)

        extra_rate = c["fridge_warming_opened"] - c["fridge_warming_closed"]
        open_steps = self.fridge_door.total_open_steps(t)
        extra_gain = extra_rate * open_steps

        return min(room, base + extra_gain)

    def get_kettle_temp(self) -> float:
        """Kettle temperature. Cools linearly from initial temp."""
        c = self.config
        room = c.get("room_temp", 23.0)
        initial = c.get("kettle_initial_temp", 75.0)
        rate = c.get("kettle_cooling_rate", 3.0)
        return max(room, initial - rate * self.time_step)

    def get_bowl_water_temp(self) -> Optional[float]:
        """Bowl water bath temperature. None if no water poured."""
        if not self.bowl_has_hot_water or self.bowl_water_poured_at is None:
            return None
        c = self.config
        room = c.get("room_temp", 23.0)
        dt = self.time_step - self.bowl_water_poured_at
        cooling = c.get("bowl_water_cooling_rate", 5.0)
        return max(room, self.bowl_water_temp - cooling * dt)

    def get_cake_doneness(self) -> float:
        c = self.config
        doneness = c["cake_initial_doneness"]
        threshold = c["cake_cooking_threshold"]
        coeff = c.get("cake_cooking_coeff", 0.02)

        bake_end = self.cake_removed_at if self.cake_removed_at else self.time_step

        for i in range(bake_end):
            temp_at_i = self._get_oven_temp_at_step(i)
            if temp_at_i > threshold:
                doneness += (temp_at_i - threshold) * coeff

        return min(100.0, doneness)

    def get_cake_temp(self) -> float:
        c = self.config
        room = c.get("room_temp", 23.0)

        if self.cake_in_oven:
            return c.get("cake_temp_when_removed", 93.0)

        if self.cake_removed_at is not None:
            dt = self.time_step - self.cake_removed_at
            cooling_rate = c.get("cake_cooling_rate", 9.0)
            return max(room, c["cake_temp_when_removed"] - cooling_rate * dt)

        return room

    def get_cream_temp(self) -> float:
        if self.cream_in_fridge:
            return self.get_fridge_temp()

        c = self.config
        room = c.get("room_temp", 23.0)
        if self.cream_removed_at is not None:
            fridge_temp_at_removal = self._get_fridge_temp_at_step(self.cream_removed_at)
            dt = self.time_step - self.cream_removed_at
            cream_warming = c.get("cream_warming_outside", 0.5)
            return min(room, fridge_temp_at_removal + cream_warming * dt)

        return room

    def is_cream_usable(self) -> bool:
        return self.get_cream_temp() <= self.config["cream_melt_threshold"]

    def can_apply_cream(self) -> bool:
        return (
            self.is_cream_usable()
            and self.get_cake_temp() < self.config["cream_apply_max_cake_temp"]
        )

    # ------------------------------------------------------------------
    # Actions — existing
    # ------------------------------------------------------------------
    def open_oven(self):
        self.oven_door.open(self.time_step)

    def close_oven(self):
        self.oven_door.close(self.time_step)

    def open_fridge(self):
        self.fridge_door.open(self.time_step)

    def close_fridge(self):
        self.fridge_door.close(self.time_step)

    def remove_cake_from_oven(self):
        self.cake_in_oven = False
        self.cake_removed_at = self.time_step

    def remove_cream_from_fridge(self):
        self.cream_in_fridge = False
        self.cream_removed_at = self.time_step

    def turn_on_oven(self) -> str:
        if not self.power_restored:
            return "FAILURE: Power is still out. Cannot turn on the oven."
        self.oven_turned_on_at = self.time_step
        return "SUCCESS: Oven is preheating."

    def apply_cream(self) -> tuple:
        cake_temp = self.get_cake_temp()
        cream_temp = self.get_cream_temp()

        if not self.is_cream_usable():
            return "FAILURE", f"Cream has melted (temperature: {cream_temp:.0f}\u00b0C > {self.config['cream_melt_threshold']}\u00b0C). Cannot apply."

        if cake_temp >= self.config["cream_apply_max_cake_temp"]:
            return "FAILURE", f"Cake is too hot ({cake_temp:.0f}\u00b0C \u2265 {self.config['cream_apply_max_cake_temp']}\u00b0C). Cream melts on contact."

        self.cream_applied = True
        quality_desc = {
            "clean_whipped": "Perfectly whipped cream applied beautifully",
            "dirty_whipped": "Whipped cream applied (slight discoloration from dirty whisk)",
            "liquid": "Liquid cream drizzled over the cake",
        }.get(self.cream_quality, "Cream applied")
        return "SUCCESS", f"{quality_desc} (cake: {cake_temp:.0f}\u00b0C, cream: {cream_temp:.0f}\u00b0C)."

    def prepare_decoration(self) -> tuple:
        """Chop/break chocolate into pieces (basic decoration)."""
        if self.chocolate_quality == "melted":
            # Already melted — chopping would ruin it; treat as no-op success
            self.chocolate_prepared = True
            return "SUCCESS", "Chocolate is already melted into a smooth glaze. No need to chop."
        self.chocolate_prepared = True
        self.chocolate_quality = "pieces"
        return "SUCCESS", "Chocolate broken into decorative pieces."

    def apply_chocolate(self) -> tuple:
        if not self.chocolate_prepared and self.chocolate_quality == "raw":
            return "FAILURE", "Chocolate has not been prepared. Use PREPARE_DECORATION or MELT_CHOCOLATE first."
        self.chocolate_applied = True
        quality_desc = {
            "melted": "Rich melted chocolate glaze applied smoothly",
            "pieces": "Chocolate pieces arranged on the cake",
        }.get(self.chocolate_quality, "Chocolate applied")
        return "SUCCESS", f"{quality_desc}."

    # ------------------------------------------------------------------
    # Actions — new bonus tracks
    # ------------------------------------------------------------------
    def wash_whisk(self) -> tuple:
        """Wash dirty whisk at sink. Requires water (pump needs power)."""
        if not self.water_available:
            return "FAILURE", "No water pressure. The pump needs electricity to operate."
        self.whisk_clean = True
        return "SUCCESS", "Whisk washed clean under running water."

    def whip_cream(self) -> tuple:
        """Whip cream with whisk. Quality depends on whisk cleanliness."""
        if self.whisk_clean:
            self.cream_quality = "clean_whipped"
            return "SUCCESS", "Cream whipped to stiff peaks with clean whisk. Perfect quality."
        else:
            self.cream_quality = "dirty_whipped"
            return "SUCCESS", "Cream whipped but whisk had residue. Usable but not pristine."

    def pour_hot_water(self) -> tuple:
        """Pour hot water from kettle into mixing bowl."""
        kettle_temp = self.get_kettle_temp()
        min_temp = self.config.get("kettle_min_useful_temp", 50.0)
        if kettle_temp < min_temp:
            return "FAILURE", f"Kettle water too cool ({kettle_temp:.0f}\u00b0C < {min_temp:.0f}\u00b0C). Cannot create effective water bath."
        self.bowl_has_hot_water = True
        self.bowl_water_temp = kettle_temp
        self.bowl_water_poured_at = self.time_step
        return "SUCCESS", f"Hot water ({kettle_temp:.0f}\u00b0C) poured into mixing bowl."

    def melt_chocolate(self) -> tuple:
        """Melt chocolate bar in the hot water bath."""
        if not self.bowl_has_hot_water:
            return "FAILURE", "No hot water in mixing bowl. Pour hot water first."
        water_temp = self.get_bowl_water_temp()
        melt_threshold = self.config.get("chocolate_melt_threshold", 45.0)
        if water_temp is None or water_temp < melt_threshold:
            temp_str = f"{water_temp:.0f}\u00b0C" if water_temp else "N/A"
            return "FAILURE", f"Water bath too cool ({temp_str} < {melt_threshold:.0f}\u00b0C). Chocolate won't melt."
        self.chocolate_prepared = True
        self.chocolate_quality = "melted"
        return "SUCCESS", f"Chocolate melted smoothly in {water_temp:.0f}\u00b0C water bath. Rich glossy consistency."

    def retrieve_platter(self) -> tuple:
        """Get platter from top cabinet."""
        self.cabinet_opened = True
        self.platter_retrieved = True
        return "SUCCESS", "Platter retrieved from top cabinet."

    def use_platter(self) -> tuple:
        """Place cake on platter for elegant presentation."""
        if not self.platter_retrieved:
            return "FAILURE", "No platter available. Retrieve it from the cabinet first."
        self.platter_used = True
        return "SUCCESS", "Cake placed on decorative platter. Elegant presentation."

    # ------------------------------------------------------------------
    # Observable state
    # ------------------------------------------------------------------
    def get_observable_state(self, target: str) -> str:
        c = self.config

        if target in ("oven_door", "oven_exterior"):
            internal = self.get_oven_temp()
            surface = internal * 0.95
            gradient = c["oven_cooling_closed"]
            if self.oven_door.is_open:
                gradient = c["oven_cooling_opened"]
            return (
                f"Surface temperature: {surface:.0f}\u00b0C. "
                f"Temperature gradient: -{gradient:.1f}\u00b0C per "
                f"{c.get('step_duration_minutes', 3)} minutes."
            )

        if target in ("fridge_door", "fridge_exterior"):
            internal = self.get_fridge_temp()
            surface = internal + 3.0
            gradient = c["fridge_warming_closed"]
            if self.fridge_door.is_open:
                gradient = c["fridge_warming_opened"]
            return (
                f"Surface temperature: {surface:.0f}\u00b0C. "
                f"Temperature gradient: +{gradient:.1f}\u00b0C per "
                f"{c.get('step_duration_minutes', 3)} minutes."
            )

        if target == "countertop":
            return f"Room temperature: {c.get('room_temp', 23.0):.0f}\u00b0C"

        if target in ("oven_interior", "oven_inside"):
            return f"Temperature: {self.get_oven_temp():.0f}\u00b0C"

        if target == "cake":
            cake_temp = self.get_cake_temp()
            doneness = self.get_cake_doneness()
            elasticity = doneness / 100.0
            stable_note = ""
            if elasticity >= 0.65:
                stable_note = " The cake is structurally stable and edible at this level."
            return (
                f"Internal temperature: {cake_temp:.0f}\u00b0C. "
                f"Surface elasticity coefficient: {elasticity:.2f} on 0-1 scale "
                f"(0=raw batter, 1=fully baked).{stable_note}"
            )

        if target == "cream":
            cream_temp = self.get_cream_temp()
            status = "solid, usable" if self.is_cream_usable() else "melting, unusable"
            return (
                f"Temperature: {cream_temp:.0f}\u00b0C. Status: {status}. "
                f"Form: liquid (not yet whipped). "
                f"Whipping would produce a much better frosting consistency."
            )

        if target == "kettle":
            temp = self.get_kettle_temp()
            if temp > 50:
                return f"Temperature: {temp:.0f}\u00b0C. Contains hot water. Cooling steadily."
            else:
                return f"Temperature: {temp:.0f}\u00b0C. Water is lukewarm \u2014 no longer hot enough to melt chocolate."

        if target == "whisk":
            if self.whisk_clean:
                return "Whisk is clean and ready to use."
            return "Whisk has dried food residue. Needs washing before use for best results."

        if target in ("mixing_bowl", "bowl"):
            if self.bowl_has_hot_water:
                wt = self.get_bowl_water_temp()
                return f"Contains water at {wt:.0f}\u00b0C."
            return "Empty mixing bowl."

        if target == "sink":
            if self.water_available:
                return "Running water available (pump powered)."
            return "No water pressure \u2014 electric pump is off due to power outage."

        if target in ("top_cabinet", "cabinet"):
            if self.cabinet_opened:
                if self.platter_retrieved:
                    return "Cabinet is open. Platter has been removed."
                return "Cabinet is open. A decorative platter is visible inside."
            return "Cabinet is closed. Through the glass door, a decorative platter is visible inside."

        if target == "platter":
            if self.platter_retrieved:
                return "Decorative platter on countertop. Ready for presentation."
            return "Platter is inside the top cabinet."

        if target == "chocolate":
            return f"Solid chocolate bar on countertop. Quality: {self.chocolate_quality}."

        return f"No sensor data available for '{target}'."

    # ------------------------------------------------------------------
    # Scoring — multi-track
    # ------------------------------------------------------------------
    def compute_score(self) -> dict:
        scoring = self.config.get("scoring", {})
        doneness = self.get_cake_doneness()

        score = 0
        breakdown = {}

        # Doneness
        if doneness >= 90:
            pts = scoring.get("doneness_90plus", 35)
        elif doneness >= 80:
            pts = scoring.get("doneness_80_90", 25)
        elif doneness >= 70:
            pts = scoring.get("doneness_70_80", 15)
        else:
            pts = 0
        score += pts
        breakdown["doneness"] = {"value": doneness, "points": pts}

        # Cream (quality-tiered)
        if self.cream_applied:
            if self.cream_quality == "clean_whipped":
                pts = scoring.get("cream_clean_whipped", 25)
            elif self.cream_quality == "dirty_whipped":
                pts = scoring.get("cream_dirty_whipped", 15)
            else:
                pts = scoring.get("cream_liquid", 10)
        else:
            pts = 0
        score += pts
        breakdown["cream"] = {
            "quality": self.cream_quality, "applied": self.cream_applied, "points": pts,
        }

        # Chocolate (quality-tiered)
        if self.chocolate_applied:
            if self.chocolate_quality == "melted":
                pts = scoring.get("chocolate_melted", 25)
            else:
                pts = scoring.get("chocolate_pieces", 10)
        else:
            pts = 0
        score += pts
        breakdown["chocolate"] = {
            "quality": self.chocolate_quality, "applied": self.chocolate_applied, "points": pts,
        }

        # Presentation
        pts = scoring.get("platter_presentation", 10) if self.platter_used else 0
        score += pts
        breakdown["presentation"] = {"platter_used": self.platter_used, "points": pts}

        # Time
        if self.time_step <= self.config.get("max_steps", 20):
            pts = scoring.get("completed_in_time", 15)
        else:
            pts = scoring.get("completed_in_time", 15) // 2
        score += pts
        breakdown["time"] = {"steps_used": self.time_step, "points": pts}

        return {
            "total_score": score,
            "max_score": scoring.get("max_score", 110),
            "breakdown": breakdown,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_oven_temp_at_step(self, step: int) -> float:
        c = self.config
        room = c.get("room_temp", 23.0)
        base = max(room, c["oven_initial_temp"] - c["oven_cooling_closed"] * step)

        extra_rate = c["oven_cooling_opened"] - c["oven_cooling_closed"]
        open_steps = self.oven_door.total_open_steps(step)
        extra_loss = extra_rate * open_steps

        if self.oven_turned_on_at is not None and step >= self.oven_turned_on_at:
            preheat_steps = c.get("oven_preheat_steps", 3)
            dt = step - self.oven_turned_on_at
            if dt >= preheat_steps:
                return c["oven_initial_temp"]
            else:
                return c["oven_initial_temp"] * (dt / preheat_steps)

        return max(room, base - extra_loss)

    def _get_fridge_temp_at_step(self, step: int) -> float:
        c = self.config
        room = c.get("room_temp", 23.0)
        base = min(room, c["fridge_initial_temp"] + c["fridge_warming_closed"] * step)

        extra_rate = c["fridge_warming_opened"] - c["fridge_warming_closed"]
        open_steps = self.fridge_door.total_open_steps(step)
        extra_gain = extra_rate * open_steps

        return min(room, base + extra_gain)

    # ------------------------------------------------------------------
    # Save / Restore
    # ------------------------------------------------------------------
    def save_state(self):
        self._snapshot = {
            "time_step": self.time_step,
            "oven_door": copy.deepcopy(self.oven_door),
            "fridge_door": copy.deepcopy(self.fridge_door),
            "power_restored": self.power_restored,
            "water_available": self.water_available,
            "oven_turned_on_at": self.oven_turned_on_at,
            "cake_in_oven": self.cake_in_oven,
            "cake_removed_at": self.cake_removed_at,
            "cream_in_fridge": self.cream_in_fridge,
            "cream_removed_at": self.cream_removed_at,
            "cream_quality": self.cream_quality,
            "cream_applied": self.cream_applied,
            "chocolate_quality": self.chocolate_quality,
            "chocolate_prepared": self.chocolate_prepared,
            "chocolate_applied": self.chocolate_applied,
            "whisk_clean": self.whisk_clean,
            "bowl_has_hot_water": self.bowl_has_hot_water,
            "bowl_water_temp": self.bowl_water_temp,
            "bowl_water_poured_at": self.bowl_water_poured_at,
            "cabinet_opened": self.cabinet_opened,
            "platter_retrieved": self.platter_retrieved,
            "platter_used": self.platter_used,
        }

    def restore_state(self):
        if self._snapshot is None:
            raise RuntimeError("No snapshot to restore.")
        s = self._snapshot
        self.time_step = s["time_step"]
        self.oven_door = copy.deepcopy(s["oven_door"])
        self.fridge_door = copy.deepcopy(s["fridge_door"])
        self.power_restored = s["power_restored"]
        self.water_available = s["water_available"]
        self.oven_turned_on_at = s["oven_turned_on_at"]
        self.cake_in_oven = s["cake_in_oven"]
        self.cake_removed_at = s["cake_removed_at"]
        self.cream_in_fridge = s["cream_in_fridge"]
        self.cream_removed_at = s["cream_removed_at"]
        self.cream_quality = s["cream_quality"]
        self.cream_applied = s["cream_applied"]
        self.chocolate_quality = s["chocolate_quality"]
        self.chocolate_prepared = s["chocolate_prepared"]
        self.chocolate_applied = s["chocolate_applied"]
        self.whisk_clean = s["whisk_clean"]
        self.bowl_has_hot_water = s["bowl_has_hot_water"]
        self.bowl_water_temp = s["bowl_water_temp"]
        self.bowl_water_poured_at = s["bowl_water_poured_at"]
        self.cabinet_opened = s["cabinet_opened"]
        self.platter_retrieved = s["platter_retrieved"]
        self.platter_used = s["platter_used"]

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def get_time_info(self) -> str:
        c = self.config
        minutes = self.time_step * c.get("step_duration_minutes", 3)
        max_min = c.get("max_steps", 20) * c.get("step_duration_minutes", 3)
        remaining = c.get("max_steps", 20) - self.time_step
        return (
            f"Current time: Step {self.time_step} "
            f"({minutes} minutes elapsed, {remaining} steps remaining of "
            f"{c.get('max_steps', 20)} total = {max_min} minutes)."
        )

    def __repr__(self):
        return (
            f"TimeSystem(step={self.time_step}, "
            f"oven={self.get_oven_temp():.0f}\u00b0C, "
            f"fridge={self.get_fridge_temp():.0f}\u00b0C, "
            f"kettle={self.get_kettle_temp():.0f}\u00b0C, "
            f"cake={self.get_cake_doneness():.1f}%, "
            f"cream_q={self.cream_quality}, "
            f"choc_q={self.chocolate_quality}, "
            f"platter={'Y' if self.platter_used else 'N'}, "
            f"power={'ON' if self.power_restored else 'OFF'})"
        )
