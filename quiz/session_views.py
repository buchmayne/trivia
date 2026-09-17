"""
Frontend views for live game sessions.
Renders HTML pages for session interaction.
"""

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpRequest, HttpResponse
from django.contrib import messages
from django.utils import timezone
from .models import Game, GameSession
from .session_cookies import find_team_by_cookie, resumable_sessions
from .utils import has_verified_email

# A team is considered "currently active" if they've been seen within this
# window - teams poll roughly every 2s while their browser tab is open.
PRESENCE_WINDOW_SECONDS = 60
HISTORY_PAGE_SIZE = 20


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


def session_rejoin(request: HttpRequest) -> HttpResponse:
    """Recovery page for a team that lost its way back into a session.

    Sessions this browser is still remembered in (via the HttpOnly cookie) are
    rendered server-side as one-tap resume links. The page also scans
    localStorage client-side, which covers players whose cookie expired or who
    joined before the cookie existed. Failing both, the form takes a code and
    team name.
    """
    return render(
        request,
        "quiz/sessions/rejoin.html",
        {"resumable_sessions": resumable_sessions(request)},
    )


def _session_presence(session: GameSession, now) -> dict:
    """Compute display-time presence info for a session's teams.

    Does not hit the database - expects session.teams to already be
    prefetched.
    """
    teams = list(session.teams.all())
    presence_cutoff = now - timedelta(seconds=PRESENCE_WINDOW_SECONDS)
    active_team_count = sum(1 for team in teams if team.last_seen >= presence_cutoff)

    last_activity = session.created_at
    if teams:
        last_activity = max(team.last_seen for team in teams)
    if session.admin_last_seen and session.admin_last_seen > last_activity:
        last_activity = session.admin_last_seen

    return {
        "team_count": len(teams),
        "active_team_count": active_team_count,
        "last_activity": last_activity,
    }


@login_required
def my_games(request: HttpRequest) -> HttpResponse:
    """Portal listing every session the logged-in user has hosted.

    Non-completed ("active") sessions are always shown in full, regardless of
    how long ago they were touched, so a host can always find their way back
    in - teams can late-join even after a long gap. Completed sessions are
    paginated history.
    """
    now = timezone.now()

    sessions = (
        GameSession.objects.filter(host_user=request.user)
        .select_related("game")
        .prefetch_related("teams")
    )

    active_sessions = []
    completed_sessions = []
    for session in sessions:
        presence = _session_presence(session, now)
        session.presence = presence
        if session.status == GameSession.Status.COMPLETED:
            completed_sessions.append(session)
        else:
            active_sessions.append(session)

    active_sessions.sort(key=lambda s: s.presence["last_activity"], reverse=True)
    completed_sessions.sort(key=lambda s: s.completed_at or s.created_at, reverse=True)

    paginator = Paginator(completed_sessions, HISTORY_PAGE_SIZE)
    page_number = request.GET.get("page")
    history_page = paginator.get_page(page_number)

    return render(
        request,
        "quiz/sessions/my_games.html",
        {
            "active_sessions": active_sessions,
            "history_page": history_page,
            "presence_window_seconds": PRESENCE_WINDOW_SECONDS,
        },
    )


def session_play(request: HttpRequest, code: str) -> HttpResponse:
    """
    Live session view. Single page that renders differently based on role.
    JS determines admin vs team based on stored token in localStorage.

    A team token remembered in the HttpOnly cookie is passed to the template so
    a player whose localStorage was cleared is put straight back on their team,
    with no rejoin form and nothing to type.
    """
    session = get_object_or_404(GameSession, code=code)

    cookie_team = find_team_by_cookie(request, code)

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
            "cookie_team_token": cookie_team.token if cookie_team else "",
        },
    )
