class BasePlanner:
    """Base planner with action history tracking."""

    def __init__(self):
        self.history = []

    def reset(self):
        self.history = []

    def update(self, action, target, success, feedback):
        entry = f"{action} {target}" if target else action
        self.history.append({
            "step": len(self.history),
            "action": entry,
            "success": success,
            "feedback": feedback,
        })

    def format_history(self):
        if not self.history:
            return ""
        lines = []
        for h in self.history:
            if h["success"]:
                lines.append(f"  Step {h['step']}: {h['action']} → OK")
            else:
                lines.append(f"  Step {h['step']}: {h['action']} → FAILED: {h['feedback']}")
        return "\n".join(lines)
