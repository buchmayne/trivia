"""HttpOnly cookie storage for team session credentials.

A team's identity is its ``SessionTeam.token``. The play page reads that token
from localStorage, but localStorage is easily lost - cleared browsing data, a
closed private tab, a browser that evicts script-writable storage - and losing
it locks a player out of their own team: they cannot simply join again, because
their own team name is now taken.

This module keeps a parallel copy of those tokens in one HttpOnly cookie so the
server can recognise a returning player with no client-side state at all.

It is a *durability* mechanism, not a secrecy one. The same token still lives in
localStorage for the play page's Bearer-header calls, so HttpOnly buys survival
of storage loss rather than protection from XSS. Deliberately, the cookie is
only ever read by server-rendered views (the play page and the rejoin page):
state-changing API endpoints keep their Bearer-only authentication, so no
CSRF-able cookie authentication is introduced.

Cookie shape: ``{"<CODE>": "<token>", ...}``, most recently used first, capped
at MAX_TRACKED entries to keep it small - it is sent on every ``/quiz/``
request. The cap also means stale entries age out on their own, so nothing has
to prune them.
"""

from __future__ import annotations

import json
from typing import Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from .models import GameSession, SessionTeam

COOKIE_NAME = "tw_team_tokens"

# Scoped to /quiz/ so it is not sent with static asset requests.
COOKIE_PATH = "/quiz/"

# Long enough to cover a game night and any reasonable return to a session,
# short enough that a shared or public browser doesn't carry it indefinitely.
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

# How many sessions to remember. A player only needs their recent games, and
# the cookie travels with every request, so this stays small.
MAX_TRACKED = 5


def read_team_tokens(request: HttpRequest) -> dict[str, str]:
    """Return the {code: token} map from the cookie.

    Tolerates anything malformed - a cookie is client-supplied data, and a
    corrupted one should read as "no remembered sessions" rather than raise.
    """
    raw = request.COOKIES.get(COOKIE_NAME)
    if not raw:
        return {}

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}

    if not isinstance(parsed, dict):
        return {}

    return {
        str(code): value
        for code, value in parsed.items()
        if isinstance(code, str) and isinstance(value, str) and code and value
    }


def get_team_token(request: HttpRequest, code: str) -> Optional[str]:
    """The remembered team token for one session code, if any."""
    return read_team_tokens(request).get(code)


def remember_team_token(
    response: HttpResponse, request: HttpRequest, code: str, token: str
) -> None:
    """Record a team token on the response, newest first, oldest dropped."""
    tokens = read_team_tokens(request)
    tokens.pop(code, None)

    updated = {code: token}
    for existing_code, existing_token in tokens.items():
        if len(updated) >= MAX_TRACKED:
            break
        updated[existing_code] = existing_token

    response.set_cookie(
        COOKIE_NAME,
        json.dumps(updated, separators=(",", ":")),
        max_age=COOKIE_MAX_AGE,
        path=COOKIE_PATH,
        httponly=True,
        # Lax still sends the cookie on the top-level navigation to
        # /quiz/play/<code>/, which is the recovery path that matters.
        samesite="Lax",
        secure=settings.SESSION_COOKIE_SECURE,
    )


def find_team_by_cookie(request: HttpRequest, code: str) -> Optional[SessionTeam]:
    """Resolve the remembered token for `code` to a live team in that session.

    Returns None unless the token still belongs to a team in the session with
    this exact code, so a token remembered under one code can never recover a
    seat in another.
    """
    token = get_team_token(request, code)
    if not token:
        return None

    return SessionTeam.objects.filter(token=token, session__code=code).first()


def resumable_sessions(request: HttpRequest) -> list[dict]:
    """Sessions this browser is remembered as a team in, newest first.

    Completed games are left out - there is nothing to return to.
    """
    tokens = read_team_tokens(request)
    if not tokens:
        return []

    teams = (
        SessionTeam.objects.filter(token__in=tokens.values())
        .exclude(session__status=GameSession.Status.COMPLETED)
        .select_related("session", "session__game")
    )

    # Key by code so a token remembered under the wrong code is discarded, and
    # so the cookie's ordering (most recent first) is what we render.
    teams_by_code = {team.session.code: team for team in teams}

    resumable = []
    for code, token in tokens.items():
        team = teams_by_code.get(code)
        if team is None or team.token != token:
            continue
        resumable.append(
            {
                "code": code,
                "team_name": team.name,
                "game_name": team.session.game.name,
                "status": team.session.status,
            }
        )
    return resumable
