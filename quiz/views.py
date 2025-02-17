from typing import Optional, Dict, Any, List, Union
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect, JsonResponse, HttpRequest, HttpResponse
from django.db import models
from .models import Game, Category, Question, QuestionRound, GameResult, PlayerStats


def get_first_question(request: HttpRequest, round_id: int) -> JsonResponse:
    try:
        game_id = request.GET.get("game_id")
        first_question = (
            Question.objects.filter(game_id=game_id, game_round_id=round_id)
            .order_by("question_number")
            .first()
        )

        if first_question:
            return JsonResponse(
                {"id": first_question.id, "category_id": first_question.category.id}
            )
        else:
            return JsonResponse({"error": "No questions found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


def game_list_view(request: HttpRequest) -> HttpResponse:
    """View to list available trivia games."""
    games = Game.objects.all().order_by("-game_order")
    return render(request, "quiz/game_list.html", {"games": games})


def get_first_question_info(
    request: HttpRequest, game_id: int, round_id: int
) -> JsonResponse:
    try:
        first_question = (
            Question.objects.filter(game_id=game_id, game_round_id=round_id)
            .order_by("question_number")
            .first()
        )

        return JsonResponse(
            {"id": first_question.id, "category_id": first_question.category.id}
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


def get_next_question(question: Question) -> Optional[Question]:
    """Get the next question in the same round"""
    return (
        Question.objects.filter(
            game=question.game,
            game_round=question.game_round,
            question_number__gt=question.question_number,
        )
        .order_by("question_number")
        .first()
    )


def question_view(
    request: HttpRequest,
    game_id: int,
    round_id: int,
    category_id: int,
    question_id: int,
) -> HttpResponse:
    game = Game.objects.get(id=game_id)
    question = Question.objects.get(id=question_id)
    rounds = (
        QuestionRound.objects.filter(questions__game=game)
        .distinct()
        .order_by("round_number")
    )
    round_questions = question.game_round.questions.filter(game=game).order_by(
        "question_number"
    )

    # Get next question
    next_question = (
        Question.objects.filter(
            game=game,
            game_round=question.game_round,
            question_number__gt=question.question_number,
        )
        .order_by("question_number")
        .first()
    )

    return render(
        request,
        "quiz/question_view.html",
        {
            "game": game,
            "question": question,
            "rounds": rounds,
            "round_questions": round_questions,
            "next_question": next_question,
        },
    )


def answer_view(
    request: HttpRequest,
    game_id: int,
    round_id: int,
    category_id: int,
    question_id: int,
) -> HttpResponse:
    game = get_object_or_404(Game, pk=game_id)
    question = get_object_or_404(Question, pk=question_id)

    rounds = (
        QuestionRound.objects.filter(questions__game=game)
        .distinct()
        .order_by("round_number")
    )
    round_questions = question.game_round.questions.filter(game=game).order_by(
        "question_number"
    )

    next_question = (
        Question.objects.filter(
            game=game,
            game_round=question.game_round,
            question_number__gt=question.question_number,
        )
        .order_by("question_number")
        .first()
    )

    return render(
        request,
        "quiz/answer_view.html",
        {
            "game": game,
            "question": question,
            "rounds": rounds,  # Added
            "round_questions": round_questions,  # Added
            "next_question": next_question,
        },
    )


def get_round_questions(
    request: HttpRequest, game_id: int, round_id: int
) -> JsonResponse:
    questions = (
        Question.objects.filter(game_id=game_id, game_round_id=round_id)
        .order_by("question_number")
        .values("id", "question_number", "category_id")
    )

    return JsonResponse({"questions": list(questions)})


def game_overview(request: HttpRequest, game_id: int) -> HttpResponse:
    game = Game.objects.get(id=game_id)
    rounds = (
        QuestionRound.objects.filter(questions__game=game)
        .distinct()
        .order_by("round_number")
    )

    # Check if game is password protected
    if game.is_password_protected:
        # Check if password has been validated for this game
        if f"game_password_verified_{game_id}" not in request.session:
            return render(
                request,
                "quiz/verify_password.html",
                {"game": game, "error_message": request.GET.get("error")},
            )

    # Calculate stats for each round
    rounds_stats = []
    total_questions = 0
    total_points = 0

    for round in rounds:
        round_questions = Question.objects.filter(game=game, game_round=round)
        question_count = round_questions.count()
        points = (
            round_questions.aggregate(total_points=models.Sum("total_points"))[
                "total_points"
            ]
            or 0
        )

        # Get the first question for this round (if any)
        first_question = round_questions.order_by("question_number").first()

        rounds_stats.append(
            {
                "round": round,
                "question_count": question_count,
                "total_points": points,
                "first_question": first_question,
            }
        )
        total_questions += question_count
        total_points += points

    return render(
        request,
        "quiz/game_overview.html",
        {
            "game": game,
            "rounds_stats": rounds_stats,
            "total_questions": total_questions,
            "total_points": total_points,
        },
    )


def verify_game_password(request: HttpRequest, game_id: int) -> HttpResponse:
    if request.method == "POST":
        game = Game.objects.get(id=game_id)
        password = request.POST.get("password")

        if password == game.password:
            # Store password verification in session
            request.session[f"game_password_verified_{game_id}"] = True
            return redirect("quiz:game_overview", game_id=game_id)
        else:
            return redirect("quiz:game_overview", game_id=game_id)

    return redirect("quiz:game_list")


def analytics_view(request):
    # Get filter parameters from request
    player_search = request.GET.get("player_search", "").strip()
    multiple_games_only = (
        True if not request.GET else request.GET.get("multiple_games") == "on"
    )
    selected_date = request.GET.get("game_date")

    # Get all unique game dates for the dropdown
    game_dates = (
        GameResult.objects.values_list("game_date", flat=True)
        .distinct()
        .order_by("-game_date")
    )

    # Get all results, ordered by date descending
    game_results = GameResult.objects.all().order_by("game_date", "place")

    # Apply game date filter if selected
    if selected_date:
        game_results = game_results.filter(game_date=selected_date)

    # Get player stats with optional filters
    player_stats = PlayerStats.objects.all()

    # Apply player search filter if provided
    if player_search:
        player_stats = player_stats.filter(player__icontains=player_search)
        game_results = game_results.filter(players__icontains=player_search)

    # Filter for multiple games if requested
    if multiple_games_only:
        player_stats = player_stats.filter(games_played__gt=1)

    # Order player stats by games played and average z-score
    player_stats = player_stats.order_by("avg_final_place", "-avg_zscore_total_points")

    for result in game_results:
        result.pct_rd1 *= 100
        result.pct_rd2 *= 100
        result.pct_final *= 100
        result.pct_total *= 100

    for stat in player_stats:
        stat.avg_pct_total_points *= 100
        stat.avg_pct_rd1_points *= 100
        stat.avg_pct_rd2_points *= 100
        stat.avg_pct_final_rd_points *= 100

    context = {
        "game_results": game_results,
        "player_stats": player_stats,
        "player_search": player_search,
        "multiple_games_only": multiple_games_only,
        "game_dates": game_dates,
        "selected_date": selected_date,
    }

    return render(request, "quiz/analytics.html", context)
