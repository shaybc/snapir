"""Collect the approval policy for migration gates."""


def collect_gate_configuration(prompt_text) -> dict:
    """Choose human or automatic approval, defaulting to human control."""
    title = "Gate control (human or automatic)"
    policy = prompt_text(title, "human")
    while policy not in {"human", "automatic"}:
        print("Choose human or automatic")
        policy = prompt_text(title, "human")
    return {
        "plan_approval_policy": policy,
        "gate_policies": {str(number): policy for number in range(1, 6)},
    }
