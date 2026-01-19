"""
Frontend views for live game sessions.
Renders HTML pages for session interaction.
"""

from django.shortcuts import render, get_object_or_404
from django.http import HttpRequest, HttpResponse
from .models import Game, GameSession


def session_landing(request: HttpRequest) -> HttpResponse:
    """Landing page with options: Host a Game or Join a Game."""
    return render(request, "quiz/sessions/landing.html")


def session_host(request: HttpRequest) -> HttpResponse:
    """Admin creates sessions. Lists available games."""
    games = Game.objects.exclude(name="Future Games").order_by("-game_order")
    return render(request, "quiz/sessions/host.html", {"games": games})


def session_join(request: HttpRequest) -> HttpResponse:
    """Teams enter code to join sessions."""
    return render(request, "quiz/sessions/join.html")


def session_play(request: HttpRequest, code: str) -> HttpResponse:
    """
    Live session view. Single page that renders differently based on role.
    JS determines admin vs team based on stored token in localStorage.
    """
    session = get_object_or_404(GameSession, code=code)

    # Prefetch data for initial render - get all rounds and their questions
    from .models import QuestionRound

    rounds_data = {}
    # Get all unique rounds for this game's questions
    round_ids = session.game.questions.values_list(
        "game_round_id", flat=True
    ).distinct()

    for round_id in round_ids:
        if round_id:  # Only if round exists
            round_obj = QuestionRound.objects.get(id=round_id)
            questions = list(
                session.game.questions.filter(game_round_id=round_id)
                .order_by("question_number")
                .values("id", "question_number", "text", "total_points")
            )
            rounds_data[round_id] = {
                "round_number": round_obj.round_number,
                "round_name": round_obj.name,
                "questions": questions,
            }

    return render(
        request,
        "quiz/sessions/play.html",
        {
            "session": session,
            "game": session.game,
            "rounds_data": rounds_data,
        },
    )
