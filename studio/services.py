"""Studio content writes live here, independent of the HTTP form widgets."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from .models import Category, Challenge, ContentBlock, Task


@transaction.atomic
def save_draft(*, working_title, rough_notes, category=None, challenge=None):
    """Capture an idea or update an existing draft without requiring finished content."""
    if challenge is None:
        challenge = Challenge()
    challenge.working_title = working_title.strip()
    challenge.rough_notes = rough_notes.strip()
    challenge.category = category
    challenge.full_clean()
    if challenge.status == Challenge.Status.READY:
        validate_ready(challenge)
    challenge.save()
    return challenge


@transaction.atomic
def create_category(*, name):
    category = Category(name=name.strip())
    category.full_clean()
    category.save()
    return category


def validate_ready(challenge):
    """Check the complete challenge, not only the fields on the challenge row."""
    errors = []
    if not challenge.category_id:
        errors.append("Select a category before marking this challenge Ready.")
    tasks = list(challenge.tasks.all().order_by("order"))
    if not tasks:
        errors.append("Add at least one task before marking this challenge Ready.")
    shared_prompt = challenge.content_blocks.filter(
        phase=ContentBlock.Phase.PROMPT
    ).exists()
    for task in tasks:
        if task.max_points < 1:
            errors.append(f"Task {task.order}: points must be greater than zero.")
        if (
            not shared_prompt
            and not task.content_blocks.filter(phase=ContentBlock.Phase.PROMPT).exists()
        ):
            errors.append(
                f"Task {task.order}: add prompt text to the challenge or task."
            )
        key = task.evaluation_key
        if task.format != Task.Format.FREE_TEXT:
            errors.append(f"Task {task.order}: unsupported response format.")
        elif (
            not isinstance(key, dict)
            or set(key) != {"reference_text"}
            or not isinstance(key["reference_text"], str)
            or not key["reference_text"].strip()
        ):
            errors.append(f"Task {task.order}: enter a reference answer.")
    if errors:
        raise ValidationError(errors)


@transaction.atomic
def set_status(challenge, status):
    if status not in Challenge.Status.values:
        raise ValidationError("Unknown challenge status.")
    if status == Challenge.Status.READY:
        validate_ready(challenge)
    challenge.status = status
    challenge.full_clean()
    challenge.save(update_fields=["status", "updated_at"])
    return challenge


@transaction.atomic
def save_task(*, challenge, max_points, reference_answer, task=None):
    if task is None:
        position = challenge.tasks.aggregate(last=Max("order"))["last"] or 0
        task = Task(challenge=challenge, order=position + 1)
    elif task.challenge_id != challenge.pk:
        raise ValidationError("This task belongs to another challenge.")
    task.max_points = max_points
    task.evaluation_key = {"reference_text": reference_answer.strip()}
    task.full_clean()
    task.save()
    if challenge.status == Challenge.Status.READY:
        validate_ready(challenge)
    return task


@transaction.atomic
def save_block(*, challenge, phase, text, task=None, block=None):
    if phase not in ContentBlock.Phase.values:
        raise ValidationError("Unknown content phase.")
    if task is not None and task.challenge_id != challenge.pk:
        raise ValidationError("This task belongs to another challenge.")
    if block is None:
        owner_blocks = task.content_blocks if task else challenge.content_blocks
        position = (
            owner_blocks.filter(phase=phase).aggregate(last=Max("order"))["last"] or 0
        )
        block = ContentBlock(
            order=position + 1, task=task, challenge=None if task else challenge
        )
    elif block.challenge_id != (None if task else challenge.pk) or block.task_id != (
        task.pk if task else None
    ):
        raise ValidationError("This content belongs to another scope.")
    block.phase = phase
    block.text = text.strip()
    block.full_clean()
    block.save()
    if challenge.status == Challenge.Status.READY:
        validate_ready(challenge)
    return block


@transaction.atomic
def delete_content(*, challenge, item):
    if isinstance(item, Task):
        if item.challenge_id != challenge.pk:
            raise ValidationError("This task belongs to another challenge.")
    elif isinstance(item, ContentBlock):
        if item.challenge_id != challenge.pk and (
            not item.task or item.task.challenge_id != challenge.pk
        ):
            raise ValidationError("This content belongs to another challenge.")
    else:
        raise ValidationError("Unknown content item.")
    item.delete()
    if challenge.status == Challenge.Status.READY:
        validate_ready(challenge)


@transaction.atomic
def move_content(*, challenge, item, direction):
    if direction not in {"up", "down"}:
        raise ValidationError("Unknown direction.")
    if isinstance(item, Task):
        if item.challenge_id != challenge.pk:
            raise ValidationError("This task belongs to another challenge.")
        siblings = challenge.tasks
    elif isinstance(item, ContentBlock):
        if item.challenge_id != challenge.pk and (
            not item.task or item.task.challenge_id != challenge.pk
        ):
            raise ValidationError("This content belongs to another challenge.")
        siblings = (
            item.task.content_blocks if item.task_id else challenge.content_blocks
        ).filter(phase=item.phase)
    else:
        raise ValidationError("Unknown content item.")
    siblings = siblings.select_for_update()
    adjacent = (
        siblings.filter(order__lt=item.order).order_by("-order").first()
        if direction == "up"
        else siblings.filter(order__gt=item.order).order_by("order").first()
    )
    if adjacent is None:
        return
    old_order, new_order = item.order, adjacent.order
    spare = (siblings.aggregate(last=Max("order"))["last"] or 0) + 1
    type(item).objects.filter(pk=item.pk).update(order=spare)
    type(item).objects.filter(pk=adjacent.pk).update(order=old_order)
    type(item).objects.filter(pk=item.pk).update(order=new_order)
