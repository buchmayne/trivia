"""Studio content writes live here, independent of the HTTP form widgets."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from .models import (
    Category,
    Challenge,
    ContentBlock,
    Game,
    GameRound,
    Placement,
    ResponseItem,
    ResponsePool,
    Task,
)


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
        if task.format == Task.Format.FREE_TEXT:
            if (
                not isinstance(key, dict)
                or set(key) != {"reference_text"}
                or not isinstance(key["reference_text"], str)
                or not key["reference_text"].strip()
            ):
                errors.append(f"Task {task.order}: enter a reference answer.")
        elif task.format == Task.Format.SINGLE_CHOICE:
            pool = task.response_pool
            if pool is None or pool.task_id != task.pk:
                errors.append(
                    f"Task {task.order}: create an option pool for this task."
                )
                continue
            items = list(pool.items.all())
            if len(items) < 2:
                errors.append(f"Task {task.order}: add at least two options.")
            for item in items:
                if not item.content_blocks.filter(
                    phase=ContentBlock.Phase.PROMPT
                ).exists():
                    errors.append(
                        f"Task {task.order}: option {item.order} needs prompt text."
                    )
            if (
                not isinstance(key, dict)
                or set(key) != {"correct_item_id"}
                or type(key["correct_item_id"]) is not int
                or key["correct_item_id"] not in {item.pk for item in items}
            ):
                errors.append(
                    f"Task {task.order}: choose a correct option from this task's pool."
                )
        else:
            errors.append(f"Task {task.order}: unsupported response format.")
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
def save_task(
    *, challenge, max_points, reference_answer, task=None, format="", correct_item=None
):
    if task is None:
        position = challenge.tasks.aggregate(last=Max("order"))["last"] or 0
        task = Task(challenge=challenge, order=position + 1)
    elif task.challenge_id != challenge.pk:
        raise ValidationError("This task belongs to another challenge.")
    task.format = format or task.format
    if task.format not in Task.Format.values:
        raise ValidationError("Unknown task format.")
    task.max_points = max_points
    if task.format == Task.Format.FREE_TEXT:
        task.response_pool = None
        task.evaluation_key = {"reference_text": reference_answer.strip()}
        task.full_clean()
        task.save()
    else:
        # Save first so the local pool can point at a real task ID.
        task.evaluation_key = {"correct_item_id": None}
        task.full_clean()
        task.save()
        pool, _ = ResponsePool.objects.get_or_create(task=task)
        if correct_item is not None:
            item_id = (
                correct_item.pk
                if isinstance(correct_item, ResponseItem)
                else correct_item
            )
            if type(item_id) is not int or not pool.items.filter(pk=item_id).exists():
                raise ValidationError("Choose an option belonging to this task.")
            task.evaluation_key = {"correct_item_id": item_id}
        task.response_pool = pool
        task.full_clean()
        task.save(update_fields=["response_pool", "evaluation_key"])
    if challenge.status == Challenge.Status.READY:
        validate_ready(challenge)
    return task


@transaction.atomic
def save_block(*, challenge, phase, text, task=None, item=None, block=None):
    if phase not in ContentBlock.Phase.values:
        raise ValidationError("Unknown content phase.")
    if task is not None and item is not None:
        raise ValidationError("Content cannot belong to both a task and an item.")
    if task is not None and task.challenge_id != challenge.pk:
        raise ValidationError("This task belongs to another challenge.")
    if item is not None and item.pool.task.challenge_id != challenge.pk:
        raise ValidationError("This item belongs to another challenge.")
    if block is None:
        owner_blocks = (
            item.content_blocks
            if item
            else task.content_blocks if task else challenge.content_blocks
        )
        position = (
            owner_blocks.filter(phase=phase).aggregate(last=Max("order"))["last"] or 0
        )
        block = ContentBlock(
            order=position + 1,
            task=task,
            item=item,
            challenge=None if task or item else challenge,
        )
    elif (
        block.challenge_id != (None if task or item else challenge.pk)
        or block.task_id != (task.pk if task else None)
        or block.item_id != (item.pk if item else None)
    ):
        raise ValidationError("This content belongs to another scope.")
    block.phase = phase
    block.text = text.strip()
    block.full_clean()
    block.save()
    if challenge.status == Challenge.Status.READY:
        validate_ready(challenge)
    return block


def _block_belongs_to_challenge(block, challenge):
    return (
        block.challenge_id == challenge.pk
        or (block.task_id is not None and block.task.challenge_id == challenge.pk)
        or (
            block.item_id is not None
            and block.item.pool.task.challenge_id == challenge.pk
        )
    )


@transaction.atomic
def save_response_item(*, task, prompt_text, reveal_text="", item=None):
    if (
        task.format != Task.Format.SINGLE_CHOICE
        or not task.response_pool_id
        or task.response_pool.task_id != task.pk
    ):
        raise ValidationError("Create a choose-one task before adding options.")
    pool = task.response_pool
    if item is None:
        position = pool.items.aggregate(last=Max("order"))["last"] or 0
        item = ResponseItem(pool=pool, order=position + 1)
        item.full_clean()
        item.save()
    elif item.pool_id != pool.pk:
        raise ValidationError("This option belongs to another task.")
    prompt = item.content_blocks.filter(phase=ContentBlock.Phase.PROMPT).first()
    save_block(
        challenge=task.challenge,
        item=item,
        phase=ContentBlock.Phase.PROMPT,
        text=prompt_text,
        block=prompt,
    )
    reveal = item.content_blocks.filter(phase=ContentBlock.Phase.REVEAL).first()
    if reveal_text.strip():
        save_block(
            challenge=task.challenge,
            item=item,
            phase=ContentBlock.Phase.REVEAL,
            text=reveal_text,
            block=reveal,
        )
    elif reveal:
        reveal.delete()
    if task.challenge.status == Challenge.Status.READY:
        validate_ready(task.challenge)
    return item


@transaction.atomic
def delete_content(*, challenge, item):
    if isinstance(item, Task):
        if item.challenge_id != challenge.pk:
            raise ValidationError("This task belongs to another challenge.")
    elif isinstance(item, ResponseItem):
        if item.pool.task.challenge_id != challenge.pk:
            raise ValidationError("This item belongs to another challenge.")
    elif isinstance(item, ContentBlock):
        if not _block_belongs_to_challenge(item, challenge):
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
    elif isinstance(item, ResponseItem):
        if item.pool.task.challenge_id != challenge.pk:
            raise ValidationError("This item belongs to another challenge.")
        siblings = item.pool.items
    elif isinstance(item, ContentBlock):
        if not _block_belongs_to_challenge(item, challenge):
            raise ValidationError("This content belongs to another challenge.")
        owner = item.item if item.item_id else item.task if item.task_id else challenge
        siblings = owner.content_blocks.filter(phase=item.phase)
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


@transaction.atomic
def save_game(*, name, description="", game=None):
    if game is None:
        game = Game()
    game.name = name.strip()
    game.description = description.strip()
    if not game.name:
        raise ValidationError({"name": "Enter a game name."})
    game.full_clean()
    game.save()
    return game


@transaction.atomic
def add_round(*, game, name):
    name = name.strip()
    if not name:
        raise ValidationError({"name": "Enter a round name."})
    Game.objects.select_for_update().get(pk=game.pk)
    position = game.rounds.aggregate(last=Max("order"))["last"] or 0
    round_ = GameRound(game=game, name=name, order=position + 1)
    round_.full_clean()
    round_.save()
    return round_


@transaction.atomic
def add_placement(*, round_, challenge):
    """Ready is checked at placement time, not enforced on later library edits."""
    if challenge.status != Challenge.Status.READY:
        raise ValidationError("Only Ready challenges can be added to a game.")
    validate_ready(challenge)
    GameRound.objects.select_for_update().get(pk=round_.pk)
    position = round_.placements.aggregate(last=Max("order"))["last"] or 0
    placement = Placement(round=round_, challenge=challenge, order=position + 1)
    placement.full_clean()
    placement.save()
    return placement


@transaction.atomic
def remove_game_item(*, game, item):
    if isinstance(item, GameRound):
        if item.game_id != game.pk:
            raise ValidationError("Round belongs to another game.")
    elif isinstance(item, Placement):
        if item.round.game_id != game.pk:
            raise ValidationError("Placement belongs to another game.")
    else:
        raise ValidationError("Unknown game item.")
    item.delete()


@transaction.atomic
def move_game_item(*, game, item, direction):
    if direction not in {"up", "down"}:
        raise ValidationError("Unknown direction.")
    if isinstance(item, GameRound):
        if item.game_id != game.pk:
            raise ValidationError("Round belongs to another game.")
        siblings = game.rounds
    elif isinstance(item, Placement):
        if item.round.game_id != game.pk:
            raise ValidationError("Placement belongs to another game.")
        siblings = item.round.placements
    else:
        raise ValidationError("Unknown game item.")
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
