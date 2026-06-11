"""
Frontend views for live game sessions.
Renders HTML pages for session interaction.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpRequest, HttpResponse
from django.contrib import messages
from .models import Game, GameSession
from .utils import has_verified_email


def session_landing(request: HttpRequest) -> HttpResponse:
    """Landing page with options: Host a Game or Join a Game."""
    return render(request, "quiz/sessions/landing.html")


def session_host(request: HttpRequest) -> HttpResponse:
    """Host page. Unauthenticated users see only example games."""

    # Count all public games for calculating locked count
    all_public_games = Game.objects.filter(is_public=True, is_draft=False)
    total_game_count = all_public_games.count()

    if not request.user.is_authenticated:
        # Unauthenticated: only example games
        games = Game.objects.filter(is_example_game=True, is_draft=False).order_by(
            "-game_order"
        )
        example_count = games.count()
        locked_count = total_game_count - example_count
    else:
        # Authenticated: check email verification
        if not has_verified_email(request.user):
            messages.warning(
                request,
                "Please verify your email address before hosting games. "
                "Check your inbox for a verification link.",
            )
            return redirect("account_email")

        # Authenticated users see all public games (or all if admin)
        games = Game.objects.filter(is_draft=False).order_by("-game_order")
        if hasattr(request.user, "profile") and not request.user.profile.is_game_admin:
            games = games.filter(is_public=True)
        locked_count = 0

    return render(
        request,
        "quiz/sessions/host.html",
        {
            "games": games,
            "is_authenticated": request.user.is_authenticated,
            "locked_game_count": locked_count,
        },
    )


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
