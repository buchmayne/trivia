"""Separate question and reveal projections; hidden answers never enter question data."""

from .models import ContentBlock


def _blocks(owner, phase):
    return [
        {"kind": "text", "text": block.text}
        for block in owner.content_blocks.filter(phase=phase).order_by("order")
    ]


def challenge_preview(challenge, *, reveal=False):
    result = {
        "id": challenge.pk,
        "title": challenge.working_title or challenge.rough_notes[:60],
        "total_points": challenge.total_points,
        "prompt": _blocks(challenge, ContentBlock.Phase.PROMPT),
        "tasks": [],
    }
    if reveal:
        result["reveal"] = _blocks(challenge, ContentBlock.Phase.REVEAL)
    for task in challenge.tasks.all().order_by("order"):
        part = {
            "id": task.pk,
            "number": task.order,
            "format": task.format,
            "max_points": task.max_points,
            "prompt": _blocks(task, ContentBlock.Phase.PROMPT),
        }
        if reveal:
            key = task.evaluation_key if isinstance(task.evaluation_key, dict) else {}
            part["correct_result"] = key.get("reference_text", "")
            part["reveal"] = _blocks(task, ContentBlock.Phase.REVEAL)
        result["tasks"].append(part)
    return result
