"""
Frontend views for live game sessions.
Renders HTML pages for session interaction.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Game, GameSession


def has_verified_email(user):
    """Check if user has at least one verified email address."""
    if not user.is_authenticated:
        return False
    return user.emailaddress_set.filter(verified=True).exists()


def session_landing(request: HttpRequest) -> HttpResponse:
    """Landing page with options: Host a Game or Join a Game."""
    return render(request, "quiz/sessions/landing.html")


@login_required
def session_host(request: HttpRequest) -> HttpResponse:
    """Admin creates sessions. Lists available games. Requires verified email."""
    # Check for verified email
    if not has_verified_email(request.user):
        messages.warning(
            request,
            "Please verify your email address before hosting games. "
            "Check your inbox for a verification link.",
        )
        return redirect("account_email")

    # Show only public games for regular users, all games for admins
    games = Game.objects.exclude(name="Future-Game").order_by("-game_order")

    # Filter to public games only for non-admin users
    if hasattr(request.user, "profile") and not request.user.profile.is_game_admin:
        games = games.filter(is_public=True)

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
