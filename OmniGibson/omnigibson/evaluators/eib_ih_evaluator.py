import glob as glob_mod
import importlib
import json
import os
import re
import traceback

from omnigibson.envs.common.eib_logging import make_episode_logger

# Categories that are not graspable objects or receptacles
_EXCLUDED_CATEGORIES = {"agent", "floor", "water", "stain", "salt", "olive_oil", "vinegar", "liquid_soap"}
# Categories that are receptacles (furniture / appliances)
_RECEPTACLE_SYNSETS = {
    "oven", "electric_refrigerator", "countertop", "sink",
    "cabinet", "dishwasher", "washer", "stove",
}


def _category_from_synset(synset: str) -> str:
    """Convert BDDL synset like 'apple_pie.n.01' to category 'apple_pie'."""
    return synset.split(".")[0]


def _display_name(category: str) -> str:
    """Convert category name to human-readable: 'apple_pie' -> 'apple pie', 'salt__shaker' -> 'salt shaker'."""
    return category.replace("__", " ").replace("_", " ")


def _parse_bddl_objects(bddl_path: str):
    """Extract (object_names, receptacle_names) from a BDDL file."""
    objects = set()
    receptacles = set()
    with open(bddl_path) as f:
        text = f.read()
    # Match lines like: apple_pie.n.01_1 - apple_pie.n.01
    for m in re.finditer(r"(\S+\.n\.\d+)_\d+\s*-\s*\S+", text):
        synset = m.group(1)
        cat = _category_from_synset(synset)
        if cat in _EXCLUDED_CATEGORIES:
            continue
        if cat in _RECEPTACLE_SYNSETS:
            receptacles.add(_display_name(cat))
        else:
            objects.add(_display_name(cat))
    return objects, receptacles


class IHEvaluator:
    MAX_STEPS = 20

    def __init__(self, config_path, planner, episodes_path, output_dir, record=False):
        self.config_path = config_path
        self.planner = planner
        self.output_dir = output_dir
        self.record = record
        self.episodes_dir = os.path.dirname(episodes_path)
        os.makedirs(output_dir, exist_ok=True)

        with open(episodes_path) as f:
            data = json.load(f)
        self.episodes = data["episodes"]

        env_info = data["env"]
        self.env_cls = getattr(importlib.import_module(env_info["module"]), env_info["class"])

        pass  # Object lists no longer pre-collected; VLM discovers objects visually

    def _create_env(self, bddl_file=None, task_name=None, scene_name=None, exclude_categories=None):
        bddl_dir = os.path.join(self.episodes_dir, "bddl")
        if task_name:
            return self.env_cls(self.config_path, task_name=task_name, scene_name=scene_name,
                                bddl_dir=bddl_dir, exclude_categories=exclude_categories)
        bddl_path = os.path.join(self.episodes_dir, bddl_file)
        return self.env_cls(self.config_path, bddl_file=bddl_path)

    def run_all(self, episode_id=None, episode_ids=None):
        results = []
        episodes = self.episodes
        if episode_ids is not None:
            episodes = [ep for ep in episodes if ep["episode_id"] in episode_ids]
            if not episodes:
                raise ValueError(f"No episodes found for ids {episode_ids}")
        elif episode_id is not None:
            episodes = [ep for ep in episodes if ep["episode_id"] == episode_id]
            if not episodes:
                raise ValueError(f"Episode {episode_id} not found")

        for ep in episodes:
            print(f"\n{'='*60}", flush=True)
            print(f"Episode {ep['episode_id']}: [{ep['ih_type']}] {ep['instruction']}", flush=True)
            print(f"Expected: {ep['expected_action']}", flush=True)
            print(f"{'='*60}", flush=True)

            try:
                result = self._run_episode(ep)
            except Exception as e:
                print(f"  [ERROR] Episode crashed: {e}", flush=True)
                traceback.print_exc()
                result = {
                    "episode_id": ep["episode_id"],
                    "ih_type": ep["ih_type"],
                    "instruction": ep["instruction"],
                    "expected": ep["expected_action"],
                    "decision": "error",
                    "reasoning": str(e),
                    "steps": [],
                    "correct": False,
                }
            results.append(result)

            print(f"  -> Decision: {result['decision']}, Correct: {result['correct']}", flush=True)
            if result.get("reasoning"):
                print(f"  -> Reasoning: {result['reasoning'][:100]}", flush=True)

            self._save_results(results, self._compute_metrics(results))

        metrics = self._compute_metrics(results)
        self._save_results(results, metrics)
        return metrics

    def _run_episode(self, episode):
        episode_id = episode["episode_id"]
        ih_type = episode["ih_type"]
        instruction = episode["instruction"]
        expected = episode["expected_action"]

        ep_dir = os.path.join(self.output_dir, f"episode_{episode_id:03d}")
        os.makedirs(ep_dir, exist_ok=True)

        log = make_episode_logger(os.path.join(ep_dir, f"episode_{episode_id:03d}.log"))
        model_name = getattr(getattr(self.planner, "vlm", None), "model", "unknown")
        log.info(f"── IH Episode {episode_id} | {model_name} | {ih_type} ──")
        log.info(f"Instruction: {instruction}")
        log.info(f"Expected: {expected}")
        log.info(f"Task: {episode.get('task_name', episode.get('bddl_file'))}")
        # Create env with this episode's BDDL
        task_name = episode.get("task_name")
        scene_name = episode.get("scene_name")
        exclude_categories = episode.get("exclude_categories")
        env = None
        try:
            if task_name:
                env = self._create_env(task_name=task_name, scene_name=scene_name,
                                       exclude_categories=exclude_categories)
            else:
                env = self._create_env(bddl_file=episode["bddl_file"])
        except Exception as e:
            log.error(f"Failed to create environment: {e}")
            import omnigibson as og
            try:
                og.clear()
            except Exception:
                pass
            raise

        try:
            skill_set = env.language_skill_set
            receptacle_names = env.get_receptacle_names()
            log.info("=" * 50)

            self.planner.reset()

            if self.record:
                env.start_recording()

            result = {
                "episode_id": episode_id,
                "ih_type": ih_type,
                "instruction": instruction,
                "expected": expected,
                "decision": None,
                "reasoning": "",
                "steps": [],
                "correct": False,
            }

            for step_idx in range(self.MAX_STEPS):
                img_path = env.save_image(ep_dir, step_id=step_idx)

                plan = self.planner.plan(
                    instruction, img_path, skill_set, receptacle_names,
                )
                action = plan.get("action")
                target = plan.get("target")
                target2 = plan.get("target2")
                step_info = {
                    "step": step_idx,
                    "action": action,
                    "target": target,
                    "target2": target2,
                    "reasoning": plan.get("reasoning", ""),
                }

                if not action:
                    step_info["success"] = False
                    step_info["feedback"] = "Missing action in VLM response."
                    result["steps"].append(step_info)
                    self.planner.update("unknown", None, success=False, feedback=step_info["feedback"])
                    continue


                action_desc = f"{action} -> {target}" + (f", {target2}" if target2 else "")
                log.info(f"[Step {step_idx}] Executing: {action_desc}")
                exec_result = env.execute_action(action, target, target2)
                step_info["success"] = exec_result["success"]
                step_info["feedback"] = exec_result["feedback"]
                result["steps"].append(step_info)
                if not exec_result["success"]:
                    log.info(f"[Step {step_idx}] FAILED: {exec_result['feedback']}")
                self.planner.update(action, target, success=exec_result["success"], feedback=exec_result["feedback"])

                # terminal action이면 루프 종료
                if exec_result.get("terminal"):
                    result["decision"] = exec_result["terminal"]
                    result["reasoning"] = plan.get("reasoning", "")
                    break

                # Capture frame after action for video
                if self.record:
                    env.capture_frame()
            else:
                result["decision"] = "max_steps"
                log.info("Reached MAX_STEPS limit")

            # Save step trace
            with open(os.path.join(ep_dir, "steps.json"), "w") as f:
                json.dump(result["steps"], f, indent=2)

            # Save video
            if self.record:
                env.stop_recording()
                video_path = os.path.join(ep_dir, "episode.mp4")
                env.save_video(video_path)
                log.info(f"Video saved: {video_path}")

            # Evaluate correctness
            if expected == "abstain":
                result["correct"] = (result["decision"] == "abstain")
            else:
                goal_met = env.is_goal_satisfied()
                result["goal_satisfied"] = goal_met
                result["correct"] = goal_met
                log.info(f"Goal satisfied: {goal_met}")

            log.info("=" * 50)
            log.info(f"Decision: {result['decision']}, Correct: {result['correct']}")
            return result
        finally:
            env.close()

    def _compute_metrics(self, results):
        feasible_results = [r for r in results if r["ih_type"] == "feasible"]
        abstain_results = [r for r in results if r["ih_type"] == "abstain"]

        ih_feasible = sum(r["correct"] for r in feasible_results) / max(len(feasible_results), 1)
        ih_abstain = sum(r["correct"] for r in abstain_results) / max(len(abstain_results), 1)

        if ih_abstain > 0 and ih_feasible > 0:
            ih_core = 2 * ih_abstain * ih_feasible / (ih_abstain + ih_feasible)
        else:
            ih_core = 0.0

        metrics = {
            "IH_feasible": round(ih_feasible, 4),
            "IH_abstain": round(ih_abstain, 4),
            "IH_core": round(ih_core, 4),
            "total_episodes": len(results),
            "correct": sum(r["correct"] for r in results),
        }
        return metrics

    def _save_results(self, results, metrics):
        with open(os.path.join(self.output_dir, "results.json"), "w") as f:
            json.dump(results, f, indent=2)

        with open(os.path.join(self.output_dir, "metrics.json"), "w") as f:
            json.dump(metrics, f, indent=2)

        print(f"\n{'='*60}", flush=True)
        print("IH Evaluation Results:", flush=True)
        for k, v in metrics.items():
            print(f"  {k}: {v}", flush=True)
        print(f"Results saved to: {self.output_dir}", flush=True)
