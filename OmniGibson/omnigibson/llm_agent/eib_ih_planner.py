import json
import re
import yaml

from omnigibson.llm_agent.eib_base_planner import BasePlanner
from omnigibson.envs.common.eib_remote_model import RemoteVLM


class IHPlanner(BasePlanner):
    def __init__(self, prompt_config_path, vlm=None):
        super().__init__()
        with open(prompt_config_path) as f:
            self.prompts = yaml.load(f, Loader=yaml.FullLoader)
        self.vlm = vlm or RemoteVLM()

    def plan(self, instruction, image_path, skill_set, receptacle_names=None):
        system_template = self.prompts["system"]
        user_prompts = self.prompts["user"]
        decision_format = user_prompts["decision_format"]

        action_str = "\n".join(f"  - {s}" for s in skill_set)
        receptacle_str = "\n".join(f"  - {name}" for name in (receptacle_names or []))

        system_prompt = system_template.format(action_types=action_str)

        if not self.history:
            user_prompt = user_prompts["first_step"].format(
                instruction=instruction,
                receptacles=receptacle_str,
                decision_format=decision_format,
            )
        else:
            user_prompt = user_prompts["subsequent_step"].format(
                instruction=instruction,
                receptacles=receptacle_str,
                action_history=self.format_history(),
                decision_format=decision_format,
            )

        raw = self.vlm.query(system_prompt, user_prompt, image_path=image_path)
        return self._parse_response(raw)

    def _parse_response(self, raw):
        """Parse VLM JSON response into structured plan."""
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        else:
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            text = json_match.group(0) if json_match else raw

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            if any(kw in raw.lower() for kw in ["cannot", "unable", "not possible", "abstain", "refuse"]):
                return {"action": "abstain", "target": None, "reasoning": raw}
            return {"action": None, "target": None, "reasoning": raw}

        return {
            "action": data.get("action"),
            "target": data.get("target"),
            "target2": data.get("target2"),
            "reasoning": data.get("reasoning", ""),
        }
