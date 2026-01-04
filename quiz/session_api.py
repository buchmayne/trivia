"""
API endpoints for live game sessions.
Token-based authentication for admin and team actions.
"""

import json
from functools import wraps
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import models

from .models import (
    Game,
    Question,
    QuestionRound,
    GameSession,
    SessionTeam,
    SessionRound,
    TeamAnswer,
)

# Configuration
ADMIN_TIMEOUT_SECONDS = 30  # Pause if admin not seen for this long


# ============================================================================
# AUTHENTICATION DECORATORS
# ============================================================================


def require_admin_token(view_func):
    """Validates admin token and updates last_seen timestamp."""

    @wraps(view_func)
    def wrapper(request, code, *args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        try:
            session = GameSession.objects.get(code=code)
            if session.admin_token != token:
                return JsonResponse({"error": "Invalid admin token"}, status=403)

            # Update admin heartbeat
            session.admin_last_seen = timezone.now()

            # Auto-resume if was paused
            if session.status == GameSession.Status.PAUSED:
                session.resume()
            else:
                session.save(update_fields=["admin_last_seen"])

            request.session_obj = session
        except GameSession.DoesNotExist:
            return JsonResponse({"error": "Session not found"}, status=404)
        return view_func(request, code, *args, **kwargs)

    return wrapper


def require_team_token(view_func):
    """Validates team token and updates last_seen timestamp."""

    @wraps(view_func)
    def wrapper(request, code, *args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        try:
            session = GameSession.objects.get(code=code)
            team = session.teams.get(token=token)
            team.last_seen = timezone.now()
            team.save(update_fields=["last_seen"])
            request.session_obj = session
            request.team = team
        except (GameSession.DoesNotExist, SessionTeam.DoesNotExist):
            return JsonResponse({"error": "Invalid session or team"}, status=403)
        return view_func(request, code, *args, **kwargs)

    return wrapper


def check_admin_timeout(session):
    """Check if admin has timed out and pause if needed."""
    if session.status in [GameSession.Status.PLAYING, GameSession.Status.SCORING]:
        timeout_threshold = timezone.now() - timedelta(seconds=ADMIN_TIMEOUT_SECONDS)
        if session.admin_last_seen < timeout_threshold:
            session.pause()
            return True
    return False


# ============================================================================
# PUBLIC ENDPOINTS
# ============================================================================


@csrf_exempt
@require_http_methods(["POST"])
def create_session(request):
    """Create new session. Returns admin_token (client must save it!)."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    game_id = data.get("game_id")
    admin_name = data.get("admin_name")

    if not game_id or not admin_name:
        return JsonResponse(
            {"error": "game_id and admin_name are required"}, status=400
        )

    game = get_object_or_404(Game, id=game_id)

    session = GameSession.objects.create(
        game=game, admin_name=admin_name, max_teams=data.get("max_teams", 16)
    )

    # Create SessionRound for each round in the game
    rounds = (
        QuestionRound.objects.filter(questions__game=game)
        .distinct()
        .order_by("round_number")
    )
    for round_obj in rounds:
        SessionRound.objects.create(session=session, round=round_obj)

    return JsonResponse(
        {
            "code": session.code,
            "admin_token": session.admin_token,
            "game_name": game.name,
            "game_id": game.id,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def join_session(request, code):
    """Team joins session. Supports late joins during active rounds."""
    session = get_object_or_404(GameSession, code=code)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    team_name = data.get("team_name", "").strip()

    # Validate team name
    if len(team_name) < 2 or len(team_name) > 100:
        return JsonResponse({"error": "Team name must be 2-100 characters"}, status=400)

    # Check if session accepts joins
    if session.status == GameSession.Status.COMPLETED:
        return JsonResponse({"error": "Game has ended"}, status=400)
    if session.status == GameSession.Status.SCORING:
        return JsonResponse({"error": "Cannot join during scoring"}, status=400)
    if not session.allow_late_joins and session.status != GameSession.Status.LOBBY:
        return JsonResponse({"error": "Late joins not allowed"}, status=400)
    if session.teams.count() >= session.max_teams:
        return JsonResponse({"error": "Session full"}, status=400)
    if session.teams.filter(name__iexact=team_name).exists():
        return JsonResponse({"error": "Team name taken"}, status=400)

    # Determine if this is a late join
    is_late_join = session.status != GameSession.Status.LOBBY

    team = SessionTeam.objects.create(
        session=session, name=team_name, joined_late=is_late_join
    )

    return JsonResponse(
        {
            "team_id": team.id,
            "team_token": team.token,
            "team_name": team.name,
            "joined_late": is_late_join,
            "current_round": (
                session.current_round.round_number if session.current_round else None
            ),
        }
    )


@require_http_methods(["GET"])
def get_session_state(request, code):
    """Poll endpoint for current state. No auth required for basic info."""
    session = get_object_or_404(GameSession, code=code)

    # Check for admin timeout
    is_paused = check_admin_timeout(session)
    if is_paused:
        session.refresh_from_db()

    # Get current round info
    current_round_info = None
    if session.current_round:
        session_round = session.session_rounds.filter(
            round=session.current_round
        ).first()
        if session_round:
            current_round_info = {
                "round_number": session.current_round.round_number,
                "round_name": session.current_round.name,
                "status": session_round.status,
            }

    # Get question info
    current_question_info = None
    if session.current_question:
        question = session.current_question
        current_question_info = {
            "id": question.id,
            "number": question.question_number,
            "text": question.text,
            "total_points": question.total_points,
            "image_url": question.question_image_url,
            "video_url": question.question_video_url,
            "answer_image_url": question.answer_image_url,
            "answer_video_url": question.answer_video_url,
            "answer_bank": question.answer_bank,
            "category_name": question.category.name if question.category else None,
            "question_type": (
                question.question_type.name if question.question_type else None
            ),
            "answers": [
                {
                    "id": a.id,
                    "text": a.text,
                    "answer_text": a.answer_text,
                    "display_order": a.display_order,
                    "image_url": a.question_image_url,
                    "answer_image_url": a.answer_image_url,
                    "video_url": a.question_video_url,
                    "answer_video_url": a.answer_video_url,
                    "points": a.points,
                    "correct_rank": a.correct_rank,
                }
                for a in question.answers.all().order_by("display_order")
            ],
        }

    teams_data = [
        {
            "id": t.id,
            "name": t.name,
            "score": t.score,
            "joined_late": t.joined_late,
            "has_answered_current": (
                TeamAnswer.objects.filter(
                    team=t, question=session.current_question, answer_text__gt=""
                ).exists()
                if session.current_question
                else False
            ),
        }
        for t in session.teams.all()
    ]

    return JsonResponse(
        {
            "status": session.status,
            "game_name": session.game.name,
            "game_id": session.game.id,
            "admin_name": session.admin_name,
            "current_round": current_round_info,
            "current_question": current_question_info,
            "teams": teams_data,
            "team_count": len(teams_data),
            "max_teams": session.max_teams,
            "allow_team_navigation": session.allow_team_navigation,
        }
    )


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================


@csrf_exempt
@require_http_methods(["POST"])
@require_admin_token
def admin_start_game(request, code):
    """Start the game from lobby."""
    session = request.session_obj

    if session.status != GameSession.Status.LOBBY:
        return JsonResponse({"error": "Game already started"}, status=400)
    if session.teams.count() < 1:
        return JsonResponse({"error": "Need at least 1 team"}, status=400)

    # Set to first question of first round
    first_session_round = session.session_rounds.first()
    if not first_session_round:
        return JsonResponse({"error": "No rounds found in game"}, status=400)

    first_question = (
        session.game.questions.filter(game_round=first_session_round.round)
        .order_by("question_number")
        .first()
    )

    session.status = GameSession.Status.PLAYING
    session.current_round = first_session_round.round
    session.current_question = first_question
    session.started_at = timezone.now()
    session.save()

    first_session_round.status = SessionRound.Status.ACTIVE
    first_session_round.started_at = timezone.now()
    first_session_round.save()

    return JsonResponse(
        {
            "status": "started",
            "current_question_id": first_question.id if first_question else None,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
@require_admin_token
def admin_set_question(request, code):
    """Set current question. Admin can navigate within active round."""
    session = request.session_obj

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    question_id = data.get("question_id")
    if not question_id:
        return JsonResponse({"error": "question_id required"}, status=400)

    question = get_object_or_404(Question, id=question_id, game=session.game)

    # Verify question is in an accessible round
    session_round = session.session_rounds.filter(round=question.game_round).first()
    if not session_round or session_round.status == SessionRound.Status.PENDING:
        return JsonResponse({"error": "Question not in active round"}, status=400)

    # In REVIEWING mode, only allow navigation within current round
    if session.status == GameSession.Status.REVIEWING:
        if question.game_round != session.current_round:
            return JsonResponse({"error": "Can only navigate within current round in review mode"}, status=400)

    session.current_question = question
    session.current_round = question.game_round
    session.save()

    return JsonResponse(
        {
            "status": "ok",
            "question_id": question.id,
            "question_number": question.question_number,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
@require_admin_token
def admin_toggle_team_navigation(request, code):
    """Toggle whether teams can navigate between questions in the round."""
    session = request.session_obj

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    allow_navigation = data.get("allow_team_navigation")
    if allow_navigation is None:
        return JsonResponse({"error": "allow_team_navigation required"}, status=400)

    session.allow_team_navigation = bool(allow_navigation)
    session.save(update_fields=["allow_team_navigation"])

    return JsonResponse(
        {
            "status": "ok",
            "allow_team_navigation": session.allow_team_navigation,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
@require_admin_token
def admin_lock_round(request, code):
    """Lock current round for scoring. All team answers become locked."""
    session = request.session_obj
    session_round = session.session_rounds.get(round=session.current_round)

    if session_round.status != SessionRound.Status.ACTIVE:
        return JsonResponse({"error": "Round not active"}, status=400)

    # Lock all answers in this round
    TeamAnswer.objects.filter(session_round=session_round).update(is_locked=True)

    session_round.status = SessionRound.Status.LOCKED
    session_round.locked_at = timezone.now()
    session_round.save()

    session.status = GameSession.Status.SCORING
    session.save()

    return JsonResponse({"status": "locked"})


@require_http_methods(["GET"])
@require_admin_token
def admin_get_scoring_data(request, code):
    """Get all answers for current round for scoring UI."""
    session = request.session_obj
    session_round = session.session_rounds.get(round=session.current_round)

    questions = (
        session.game.questions.filter(game_round=session.current_round)
        .order_by("question_number")
        .prefetch_related("answers")
    )

    data = []
    for question in questions:
        q_data = {
            "id": question.id,
            "number": question.question_number,
            "text": question.text,
            "total_points": question.total_points,
            "category_name": question.category.name if question.category else None,
            "question_type": (
                question.question_type.name if question.question_type else None
            ),
            "correct_answers": [
                {
                    "sub_question": a.text,
                    "answer_text": a.answer_text,
                    "correct_rank": a.correct_rank,
                    "points": a.points,
                }
                for a in question.answers.all().order_by("display_order")
            ],
            "team_answers": [],
        }

        for team in session.teams.all():
            answer = TeamAnswer.objects.filter(team=team, question=question).first()

            q_data["team_answers"].append(
                {
                    "team_id": team.id,
                    "team_name": team.name,
                    "answer_id": answer.id if answer else None,
                    "answer_text": answer.answer_text if answer else "",
                    "points_awarded": answer.points_awarded if answer else None,
                    "is_scored": answer.points_awarded is not None if answer else False,
                }
            )

        data.append(q_data)

    return JsonResponse(
        {
            "round_number": session.current_round.round_number,
            "round_name": session.current_round.name,
            "questions": data,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
@require_admin_token
def admin_score_answer(request, code):
    """Award points for an answer. Admin can set any value from 0 to question max."""
    session = request.session_obj

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    answer_id = data.get("answer_id")
    team_id = data.get("team_id")
    question_id = data.get("question_id")
    points = data.get("points")

    if points is None:
        return JsonResponse({"error": "points required"}, status=400)

    try:
        points = int(points)
    except (ValueError, TypeError):
        return JsonResponse({"error": "points must be an integer"}, status=400)

    # Support scoring by answer_id or by team_id + question_id
    if answer_id:
        answer = get_object_or_404(TeamAnswer, id=answer_id)
    else:
        if not team_id or not question_id:
            return JsonResponse(
                {"error": "Either answer_id or (team_id + question_id) required"},
                status=400,
            )
        team = get_object_or_404(SessionTeam, id=team_id, session=session)
        question = get_object_or_404(Question, id=question_id)
        session_round = session.session_rounds.get(round=question.game_round)
        answer, _ = TeamAnswer.objects.get_or_create(
            team=team,
            question=question,
            defaults={"session_round": session_round, "is_locked": True},
        )

    # Validate points range
    max_points = answer.question.total_points
    if points < 0:
        return JsonResponse({"error": "Points cannot be negative"}, status=400)
    if points > max_points:
        return JsonResponse({"error": f"Points cannot exceed {max_points}"}, status=400)

    answer.points_awarded = points
    answer.scored_at = timezone.now()
    answer.save()

    # Recalculate team total
    team = answer.team
    team.score = (
        team.answers.filter(points_awarded__isnull=False).aggregate(
            total=models.Sum("points_awarded")
        )["total"]
        or 0
    )
    team.save()

    return JsonResponse(
        {
            "status": "scored",
            "answer_id": answer.id,
            "points_awarded": points,
            "team_score": team.score,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
@require_admin_token
def admin_complete_round(request, code):
    """Mark round as scored, transition to REVIEWING state."""
    session = request.session_obj
    session_round = session.session_rounds.get(round=session.current_round)

    # Verify all answers are scored
    unscored = TeamAnswer.objects.filter(
        session_round=session_round,
        points_awarded__isnull=True,
        answer_text__gt="",  # Only count answers that were submitted
    ).count()

    if unscored > 0:
        return JsonResponse(
            {"error": f"{unscored} answers still need scoring"}, status=400
        )

    session_round.status = SessionRound.Status.SCORED
    session_round.scored_at = timezone.now()
    session_round.save()

    # Transition to REVIEWING state
    session.status = GameSession.Status.REVIEWING
    # Reset to first question of the round for review
    first_question = (
        session.game.questions.filter(game_round=session.current_round)
        .order_by("question_number")
        .first()
    )
    session.current_question = first_question
    session.save()

    return JsonResponse(
        {
            "status": "reviewing",
            "round_number": session.current_round.round_number,
            "round_name": session.current_round.name,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
@require_admin_token
def admin_start_next_round(request, code):
    """Exit review mode and start next round or end game."""
    session = request.session_obj

    if session.status != GameSession.Status.REVIEWING:
        return JsonResponse({"error": "Not in review mode"}, status=400)

    # Check for next round
    next_session_round = (
        session.session_rounds.filter(
            round__round_number__gt=session.current_round.round_number,
            status=SessionRound.Status.PENDING,
        )
        .order_by("round__round_number")
        .first()
    )

    if next_session_round:
        # Advance to next round
        next_session_round.status = SessionRound.Status.ACTIVE
        next_session_round.started_at = timezone.now()
        next_session_round.save()

        first_question = (
            session.game.questions.filter(game_round=next_session_round.round)
            .order_by("question_number")
            .first()
        )

        session.status = GameSession.Status.PLAYING
        session.current_round = next_session_round.round
        session.current_question = first_question
        session.save()

        return JsonResponse(
            {
                "status": "next_round",
                "round_number": next_session_round.round.round_number,
                "round_name": next_session_round.round.name,
            }
        )
    else:
        # Game complete
        session.status = GameSession.Status.COMPLETED
        session.completed_at = timezone.now()
        session.save()

        # Return final standings
        final_standings = [
            {"rank": i + 1, "name": t.name, "score": t.score}
            for i, t in enumerate(session.teams.order_by("-score"))
        ]

        return JsonResponse({"status": "game_complete", "standings": final_standings})


# ============================================================================
# TEAM ENDPOINTS
# ============================================================================


@csrf_exempt
@require_http_methods(["POST"])
@require_team_token
def team_submit_answer(request, code):
    """Submit or update answer. Only works for active rounds."""
    session = request.session_obj
    team = request.team

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    question_id = data.get("question_id")
    if not question_id:
        return JsonResponse({"error": "question_id required"}, status=400)

    question = get_object_or_404(Question, id=question_id, game=session.game)
    session_round = session.session_rounds.get(round=question.game_round)

    # Validate round is active
    if session_round.status != SessionRound.Status.ACTIVE:
        return JsonResponse({"error": "Round not active for answers"}, status=400)

    # Late joiners can only answer current round
    if team.joined_late:
        first_accessible_round = (
            session.session_rounds.filter(started_at__gte=team.joined_at)
            .order_by("round__round_number")
            .first()
        )

        if (
            first_accessible_round
            and session_round.round.round_number
            < first_accessible_round.round.round_number
        ):
            return JsonResponse(
                {"error": "Cannot answer questions from earlier rounds"}, status=400
            )

    answer, created = TeamAnswer.objects.get_or_create(
        team=team, question=question, defaults={"session_round": session_round}
    )

    if answer.is_locked:
        return JsonResponse({"error": "Answer is locked"}, status=400)

    answer.answer_text = data.get("answer_text", "")
    answer.save()

    return JsonResponse(
        {"status": "saved", "answer_id": answer.id, "question_id": question.id}
    )


@require_http_methods(["GET"])
@require_team_token
def team_get_answers(request, code):
    """Get team's answers for current round."""
    session = request.session_obj
    team = request.team

    round_id = request.GET.get("round_id")
    if round_id:
        target_round = get_object_or_404(QuestionRound, id=round_id)
    else:
        target_round = session.current_round

    if not target_round:
        return JsonResponse({"answers": []})

    session_round = session.session_rounds.get(round=target_round)

    # Get all questions in round with team's answers
    questions = session.game.questions.filter(game_round=target_round).order_by(
        "question_number"
    )

    answers_data = []
    for question in questions:
        answer = team.answers.filter(question=question).first()
        answers_data.append(
            {
                "question_id": question.id,
                "question_number": question.question_number,
                "question_text": question.text,
                "answer_text": answer.answer_text if answer else "",
                "is_locked": answer.is_locked if answer else False,
                "points_awarded": answer.points_awarded if answer else None,
            }
        )

    return JsonResponse(
        {
            "round_number": target_round.round_number,
            "round_status": session_round.status,
            "answers": answers_data,
        }
    )


@require_http_methods(["GET"])
@require_team_token
def team_get_question_details(request, code):
    """Get full details for a specific question (for team navigation)."""
    session = request.session_obj
    team = request.team

    question_id = request.GET.get("question_id")
    if not question_id:
        return JsonResponse({"error": "question_id required"}, status=400)

    question = get_object_or_404(Question, id=question_id, game=session.game)
    session_round = session.session_rounds.filter(round=question.game_round).first()

    # Verify question is in current or completed round (not future rounds)
    if not session_round or session_round.status == SessionRound.Status.PENDING:
        return JsonResponse({"error": "Question not accessible yet"}, status=400)

    question_data = {
        "id": question.id,
        "number": question.question_number,
        "text": question.text,
        "total_points": question.total_points,
        "image_url": question.question_image_url,
        "video_url": question.question_video_url,
        "answer_image_url": question.answer_image_url,
        "answer_video_url": question.answer_video_url,
        "answer_bank": question.answer_bank,
        "category_name": question.category.name if question.category else None,
        "question_type": (
            question.question_type.name if question.question_type else None
        ),
        "answers": [
            {
                "id": a.id,
                "text": a.text,
                "answer_text": a.answer_text,
                "display_order": a.display_order,
                "image_url": a.question_image_url,
                "answer_image_url": a.answer_image_url,
                "video_url": a.question_video_url,
                "answer_video_url": a.answer_video_url,
                "points": a.points,
                "correct_rank": a.correct_rank,
            }
            for a in question.answers.all().order_by("display_order")
        ],
    }

    return JsonResponse({"question": question_data})


@require_http_methods(["GET"])
@require_team_token
def team_get_results(request, code):
    """Get team's results across all scored rounds."""
    session = request.session_obj
    team = request.team

    rounds_data = []
    for session_round in session.session_rounds.filter(
        status=SessionRound.Status.SCORED
    ):
        round_answers = team.answers.filter(session_round=session_round)
        round_score = (
            round_answers.aggregate(total=models.Sum("points_awarded"))["total"] or 0
        )

        rounds_data.append(
            {
                "round_number": session_round.round.round_number,
                "round_name": session_round.round.name,
                "score": round_score,
            }
        )

    # Get current standings
    standings = list(session.teams.order_by("-score").values("id", "name", "score"))
    team_rank = next(
        (i + 1 for i, t in enumerate(standings) if t["id"] == team.id), None
    )

    return JsonResponse(
        {
            "team_name": team.name,
            "total_score": team.score,
            "rank": team_rank,
            "total_teams": len(standings),
            "rounds": rounds_data,
            "standings": standings,
        }
    )
