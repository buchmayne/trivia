from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from .models import Game, GameSession


def host_dashboard(request):
    """Page where hosts create and manage game sessions"""
    games = Game.objects.all().order_by("name")
    return render(request, "quiz/host_dashboard.html", {"games": games})


def team_join(request):
    """Page where teams join existing sessions"""
    return render(request, "quiz/team_join.html")


def live_session(request, session_code):
    """Live game page for both hosts and teams"""
    session = get_object_or_404(GameSession, session_code=session_code)

    # Determine if this is likely a host or team view
    is_host = request.GET.get("host") == "true"

    context = {
        "session": session,
        "is_host": is_host,
        "session_code": session_code,
        "game": session.game,
    }

    if is_host:
        return render(request, "quiz/host_live_session.html", context)
    else:
        return render(request, "quiz/team_live_session.html", context)
