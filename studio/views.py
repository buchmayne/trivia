from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .access import studio_required
from .forms import (
    BlockForm,
    CategoryForm,
    ChallengeDraftForm,
    GameForm,
    ItemForm,
    PlacementForm,
    RoundForm,
    TaskForm,
)
from .models import (
    Category,
    Challenge,
    ContentBlock,
    Game,
    GameRound,
    Placement,
    ResponseItem,
    Task,
)
from .projections import challenge_preview, game_preview
from .services import (
    add_placement,
    add_round,
    create_category,
    delete_content,
    move_content,
    move_game_item,
    remove_game_item,
    save_block,
    save_draft,
    save_game,
    save_response_item,
    save_task,
    set_status,
)


def _form_error(form, exc):
    if hasattr(exc, "message_dict"):
        for field, errors in exc.message_dict.items():
            form.add_error(field if field in form.fields else None, errors)
    else:
        form.add_error(None, exc)


@studio_required
def library(request):
    challenges = Challenge.objects.select_related("category").annotate(
        last_used=Max("placements__created_at")
    )
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    category_id = request.GET.get("category", "")
    if query:
        challenges = challenges.filter(
            Q(working_title__icontains=query) | Q(rough_notes__icontains=query)
        )
    if status in Challenge.Status.values:
        challenges = challenges.filter(status=status)
    if category_id.isdecimal():
        challenges = challenges.filter(category_id=int(category_id))
    return render(
        request,
        "studio/library.html",
        {
            "challenges": challenges,
            "categories": Category.objects.all(),
            "draft_form": ChallengeDraftForm(),
            "category_form": CategoryForm(),
            "query": query,
            "selected_status": status,
            "selected_category": category_id,
        },
    )


@studio_required
@require_POST
def capture(request):
    form = ChallengeDraftForm(request.POST)
    if form.is_valid():
        try:
            challenge = save_draft(**form.cleaned_data)
        except ValidationError as exc:
            _form_error(form, exc)
        else:
            messages.success(request, "Idea saved as a draft.")
            return redirect("studio:edit", pk=challenge.pk)
    return render(request, "studio/draft.html", {"form": form}, status=400)


def _editor_context(challenge, **extra):
    tasks = []
    for task in challenge.tasks.all():
        tasks.append(
            {
                "task": task,
                "prompt": task.content_blocks.filter(phase=ContentBlock.Phase.PROMPT),
                "reveal": task.content_blocks.filter(phase=ContentBlock.Phase.REVEAL),
            }
        )
    return {
        "challenge": challenge,
        "tasks": tasks,
        "challenge_prompt": challenge.content_blocks.filter(
            phase=ContentBlock.Phase.PROMPT
        ),
        "challenge_reveal": challenge.content_blocks.filter(
            phase=ContentBlock.Phase.REVEAL
        ),
        **extra,
    }


@studio_required
@require_http_methods(["GET", "POST"])
def edit(request, pk):
    challenge = get_object_or_404(Challenge, pk=pk)
    form = ChallengeDraftForm(request.POST or None, instance=challenge)
    if request.method == "POST" and form.is_valid():
        try:
            save_draft(challenge=challenge, **form.cleaned_data)
        except ValidationError as exc:
            _form_error(form, exc)
        else:
            messages.success(request, "Challenge details saved.")
            return redirect("studio:edit", pk=challenge.pk)
    return render(
        request,
        "studio/draft.html",
        _editor_context(challenge, form=form),
        status=400 if request.method == "POST" and form.errors else 200,
    )


@studio_required
@require_POST
def add_category(request):
    form = CategoryForm(request.POST)
    if form.is_valid():
        try:
            create_category(**form.cleaned_data)
        except ValidationError as exc:
            _form_error(form, exc)
        else:
            messages.success(request, "Category added.")
            return redirect("studio:library")
    return render(request, "studio/category.html", {"form": form}, status=400)


@studio_required
@require_POST
def change_status(request, pk):
    challenge = get_object_or_404(Challenge, pk=pk)
    try:
        set_status(challenge, request.POST.get("status"))
    except ValidationError as exc:
        return render(
            request,
            "studio/draft.html",
            _editor_context(
                challenge,
                form=ChallengeDraftForm(instance=challenge),
                ready_errors=exc.messages,
            ),
            status=400,
        )
    messages.success(request, f"Challenge marked {challenge.get_status_display()}.")
    return redirect("studio:edit", pk=pk)


@studio_required
@require_http_methods(["GET", "POST"])
def task_form(request, pk, task_pk=None):
    challenge = get_object_or_404(Challenge, pk=pk)
    task = get_object_or_404(Task, pk=task_pk, challenge=challenge) if task_pk else None
    initial = (
        {
            "max_points": task.max_points,
            "reference_answer": (
                task.evaluation_key if isinstance(task.evaluation_key, dict) else {}
            ).get("reference_text", ""),
        }
        if task
        else None
    )
    if task:
        initial["format"] = task.format
        initial["correct_item"] = (
            task.evaluation_key.get("correct_item_id")
            if isinstance(task.evaluation_key, dict)
            else None
        )
    form = TaskForm(request.POST or None, initial=initial, task=task)
    if request.method == "POST" and form.is_valid():
        try:
            saved_task = save_task(challenge=challenge, task=task, **form.cleaned_data)
        except ValidationError as exc:
            _form_error(form, exc)
        else:
            if form.cleaned_data.get("format") == Task.Format.SINGLE_CHOICE:
                return redirect("studio:edit_task", pk=pk, task_pk=saved_task.pk)
            return redirect("studio:edit", pk=pk)
    return render(
        request,
        "studio/task.html",
        {
            "challenge": challenge,
            "task": task,
            "form": form,
            "selected_format": request.POST.get("format")
            or (task.format if task else Task.Format.FREE_TEXT),
            "items": (
                list(task.response_pool.items.all())
                if task and task.response_pool_id
                else []
            ),
            "item_form": ItemForm(),
        },
        status=400 if request.method == "POST" and form.errors else 200,
    )


@studio_required
@require_http_methods(["GET", "POST"])
def option_form(request, pk, task_pk, item_pk=None):
    challenge = get_object_or_404(Challenge, pk=pk)
    task = get_object_or_404(
        Task, pk=task_pk, challenge=challenge, format=Task.Format.SINGLE_CHOICE
    )
    if not task.response_pool_id:
        raise Http404
    item = (
        get_object_or_404(ResponseItem, pk=item_pk, pool=task.response_pool)
        if item_pk
        else None
    )
    initial = None
    if item:
        prompt = item.content_blocks.filter(phase=ContentBlock.Phase.PROMPT).first()
        reveal = item.content_blocks.filter(phase=ContentBlock.Phase.REVEAL).first()
        initial = {
            "prompt_text": prompt.text if prompt else "",
            "reveal_text": reveal.text if reveal else "",
        }
    form = ItemForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            save_response_item(task=task, item=item, **form.cleaned_data)
        except ValidationError as exc:
            _form_error(form, exc)
        else:
            return redirect("studio:edit_task", pk=pk, task_pk=task.pk)
    return render(
        request,
        "studio/option.html",
        {"challenge": challenge, "task": task, "item": item, "form": form},
        status=400 if request.method == "POST" and form.errors else 200,
    )


@studio_required
@require_http_methods(["GET", "POST"])
def block_form(request, pk, block_pk=None):
    challenge = get_object_or_404(Challenge, pk=pk)
    if block_pk is not None:
        block = get_object_or_404(
            ContentBlock.objects.filter(
                Q(challenge=challenge)
                | Q(task__challenge=challenge)
                | Q(item__pool__task__challenge=challenge)
            ),
            pk=block_pk,
        )
        task = block.task
        item = block.item
        phase = block.phase
    else:
        block = None
        task_id = request.POST.get("task", request.GET.get("task", ""))
        item_id = request.POST.get("item", request.GET.get("item", ""))
        if (
            task_id
            and item_id
            or task_id
            and not task_id.isdecimal()
            or item_id
            and not item_id.isdecimal()
        ):
            raise Http404
        task = (
            get_object_or_404(Task, pk=task_id, challenge=challenge)
            if task_id
            else None
        )
        item = (
            get_object_or_404(ResponseItem, pk=item_id, pool__task__challenge=challenge)
            if item_id
            else None
        )
        phase = request.POST.get("phase", request.GET.get("phase", ""))
        if phase not in ContentBlock.Phase.values:
            raise Http404
    form = BlockForm(
        request.POST or None, initial={"text": block.text} if block else None
    )
    if request.method == "POST" and form.is_valid():
        try:
            save_block(
                challenge=challenge,
                task=task,
                item=item,
                phase=phase,
                block=block,
                **form.cleaned_data,
            )
        except ValidationError as exc:
            _form_error(form, exc)
        else:
            if item:
                return redirect("studio:edit_task", pk=pk, task_pk=item.pool.task_id)
            return redirect("studio:edit", pk=pk)
    return render(
        request,
        "studio/block.html",
        {
            "challenge": challenge,
            "task": task,
            "item": item,
            "block": block,
            "phase": phase,
            "form": form,
        },
        status=400 if request.method == "POST" and form.errors else 200,
    )


@studio_required
@require_POST
def item_action(request, pk, kind, item_pk, action):
    challenge = get_object_or_404(Challenge, pk=pk)
    if kind == "tasks":
        item = get_object_or_404(Task, pk=item_pk, challenge=challenge)
    elif kind == "blocks":
        item = get_object_or_404(
            ContentBlock.objects.filter(
                Q(challenge=challenge)
                | Q(task__challenge=challenge)
                | Q(item__pool__task__challenge=challenge)
            ),
            pk=item_pk,
        )
    elif kind == "options":
        item = get_object_or_404(
            ResponseItem, pk=item_pk, pool__task__challenge=challenge
        )
        parent_task_id = item.pool.task_id
    else:
        raise Http404
    try:
        if action == "delete":
            delete_content(challenge=challenge, item=item)
        elif action in {"up", "down"}:
            move_content(challenge=challenge, item=item, direction=action)
        else:
            raise Http404
    except ValidationError as exc:
        return render(
            request,
            "studio/draft.html",
            _editor_context(
                challenge,
                form=ChallengeDraftForm(instance=challenge),
                ready_errors=exc.messages,
            ),
            status=400,
        )
    if kind == "options":
        return redirect("studio:edit_task", pk=pk, task_pk=parent_task_id)
    return redirect("studio:edit", pk=pk)


@studio_required
def preview(request, pk, mode):
    if mode not in {"question", "reveal"}:
        raise Http404
    challenge = get_object_or_404(Challenge, pk=pk)
    return render(
        request,
        "studio/preview.html",
        {
            "challenge": challenge_preview(challenge, reveal=mode == "reveal"),
            "mode": mode,
        },
    )


def _game_context(game, *, request=None, **extra):
    ready = Challenge.objects.filter(status=Challenge.Status.READY).select_related(
        "category"
    )
    query = request.GET.get("q", "").strip() if request else ""
    category_id = request.GET.get("category", "") if request else ""
    if query:
        ready = ready.filter(
            Q(working_title__icontains=query) | Q(rough_notes__icontains=query)
        )
    if category_id.isdecimal():
        ready = ready.filter(category_id=int(category_id))
    return {
        "game": game,
        "outline": game_preview(game),
        "categories": Category.objects.all(),
        "game_form": GameForm(instance=game),
        "round_form": RoundForm(),
        "placement_form": PlacementForm(challenges=ready),
        "ready_challenges": ready,
        "query": query,
        "selected_category": category_id,
        **extra,
    }


@studio_required
def games(request):
    return render(request, "studio/games.html", {"games": Game.objects.all()})


@studio_required
@require_http_methods(["GET", "POST"])
def new_game(request):
    form = GameForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            game = save_game(**form.cleaned_data)
        except ValidationError as exc:
            _form_error(form, exc)
        else:
            return redirect("studio:game_editor", pk=game.pk)
    return render(
        request,
        "studio/game_form.html",
        {"form": form},
        status=400 if request.method == "POST" and form.errors else 200,
    )


@studio_required
@require_http_methods(["GET", "POST"])
def game_editor(request, pk):
    game = get_object_or_404(Game, pk=pk)
    if request.method == "POST":
        form = GameForm(request.POST, instance=game)
        if form.is_valid():
            try:
                save_game(game=game, **form.cleaned_data)
            except ValidationError as exc:
                _form_error(form, exc)
            else:
                return redirect("studio:game_editor", pk=pk)
        return render(
            request,
            "studio/game_editor.html",
            _game_context(game, request=request, game_form=form),
            status=400,
        )
    return render(
        request, "studio/game_editor.html", _game_context(game, request=request)
    )


@studio_required
@require_POST
def game_add_round(request, pk):
    game = get_object_or_404(Game, pk=pk)
    form = RoundForm(request.POST)
    if form.is_valid():
        try:
            add_round(game=game, **form.cleaned_data)
        except ValidationError as exc:
            _form_error(form, exc)
        else:
            return redirect("studio:game_editor", pk=pk)
    return render(
        request,
        "studio/game_editor.html",
        _game_context(game, round_form=form),
        status=400,
    )


@studio_required
@require_POST
def game_add_placement(request, pk, round_pk):
    game = get_object_or_404(Game, pk=pk)
    round_ = get_object_or_404(GameRound, pk=round_pk, game=game)
    form = PlacementForm(request.POST)
    if form.is_valid():
        try:
            add_placement(round_=round_, **form.cleaned_data)
        except ValidationError as exc:
            _form_error(form, exc)
        else:
            return redirect("studio:game_editor", pk=pk)
    return render(
        request,
        "studio/game_editor.html",
        _game_context(game, placement_form=form),
        status=400,
    )


@studio_required
@require_POST
def game_item_action(request, pk, kind, item_pk, action):
    game = get_object_or_404(Game, pk=pk)
    if kind == "rounds":
        item = get_object_or_404(GameRound, pk=item_pk, game=game)
    elif kind == "placements":
        item = get_object_or_404(Placement, pk=item_pk, round__game=game)
    else:
        raise Http404
    if action == "delete":
        remove_game_item(game=game, item=item)
    elif action in {"up", "down"}:
        move_game_item(game=game, item=item, direction=action)
    else:
        raise Http404
    return redirect("studio:game_editor", pk=pk)


@studio_required
def game_preview_page(request, pk, mode):
    if mode not in {"question", "reveal"}:
        raise Http404
    game = get_object_or_404(Game, pk=pk)
    return render(
        request,
        "studio/game_preview.html",
        {"outline": game_preview(game, reveal=mode == "reveal"), "mode": mode},
    )
