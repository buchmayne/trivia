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
        key = task.evaluation_key if isinstance(task.evaluation_key, dict) else {}
        if task.format == "single_choice":
            options = []
            pool = task.response_pool
            if pool and pool.task_id == task.pk:
                items = list(pool.items.all().order_by("order"))
                valid_ids = {item.pk for item in items}
                correct_id = key.get("correct_item_id") if reveal else None
                if correct_id not in valid_ids:
                    correct_id = None
                for index, item in enumerate(items):
                    option = {
                        "id": item.pk,
                        "label": chr(65 + index) if index < 26 else str(index + 1),
                        "prompt": _blocks(item, ContentBlock.Phase.PROMPT),
                    }
                    if reveal:
                        option["correct"] = item.pk == correct_id
                        option["reveal"] = _blocks(item, ContentBlock.Phase.REVEAL)
                    options.append(option)
                if reveal and correct_id is not None:
                    correct_item = next(item for item in items if item.pk == correct_id)
                    part["correct_result"] = " ".join(
                        block["text"]
                        for block in _blocks(correct_item, ContentBlock.Phase.PROMPT)
                    )
            part["options"] = options
        if reveal:
            if task.format == "free_text":
                part["correct_result"] = key.get("reference_text", "")
            part["reveal"] = _blocks(task, ContentBlock.Phase.REVEAL)
        result["tasks"].append(part)
    return result


def game_preview(game, *, reveal=False):
    """Flatten placements for game-wide numbering while retaining round boundaries."""
    rounds = []
    coverage = {}
    number = 0
    for round_ in game.rounds.all().order_by("order"):
        entries = []
        for placement in round_.placements.select_related(
            "challenge__category"
        ).order_by("order"):
            number += 1
            challenge = placement.challenge
            if challenge.category:
                name = challenge.category.name
                coverage[name] = coverage.get(name, 0) + 1
            entries.append(
                {
                    "number": number,
                    "placement_id": placement.pk,
                    "challenge": challenge_preview(challenge, reveal=reveal),
                    "category": challenge.category.name if challenge.category else None,
                    "incomplete": challenge.status != challenge.Status.READY,
                    "round_id": round_.pk,
                }
            )
        rounds.append({"id": round_.pk, "name": round_.name, "entries": entries})
    return {
        "id": game.pk,
        "name": game.name,
        "description": game.description,
        "rounds": rounds,
        "category_coverage": sorted(coverage.items()),
    }
