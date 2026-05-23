"""
API endpoints for live game sessions.
Token-based authentication for admin and team actions.
"""

import json
from functools import wraps
from datetime import timedelta
from typing import Callable, Optional

from django.shortcuts import get_object_or_404
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import models, transaction
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited

from .models import (
    Answer,
    Game,
    Question,
    QuestionRound,
    GameSession,
    SessionTeam,
    SessionRound,
    TeamAnswer,
)
from .scoring import scorer_for
from .utils import has_verified_email


def ratelimit_error(request: HttpRequest, exception: Exception) -> JsonResponse:
    """Handler for rate limit exceeded errors."""
    return JsonResponse(
        {"error": "Rate limit exceeded. Please wait before trying again."}, status=429
    )


# Configuration
ADMIN_TIMEOUT_SECONDS = 30  # Pause if admin not seen for this long


# ============================================================================
# AUTHENTICATION DECORATORS
# ============================================================================


def require_admin_token(view_func: Callable) -> Callable:
    """Validates admin token and updates last_seen timestamp."""

    @wraps(view_func)
    def wrapper(request: HttpRequest, code: str, *args, **kwargs) -> JsonResponse:
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


def require_team_token(view_func: Callable) -> Callable:
    """Validates team token and updates last_seen timestamp."""

    @wraps(view_func)
    def wrapper(request: HttpRequest, code: str, *args, **kwargs) -> JsonResponse:
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


def check_admin_timeout(session: GameSession) -> bool:
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
@ratelimit(key="ip", rate="10/m", method="POST", block=True)
@transaction.atomic
def create_session(request: HttpRequest) -> JsonResponse:
    """Create new session. Unauthenticated users can only create sessions for example games."""
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

    # Permission check
    if not request.user.is_authenticated:
        # Unauthenticated: only example games allowed
        if not game.is_example_game:
            return JsonResponse(
                {"error": "Please sign up to host this game"},
                status=401,
            )
        host_user = None
    else:
        # Authenticated: check email verification
        if not has_verified_email(request.user):
            return JsonResponse(
                {"error": "Please verify your email address before hosting games."},
                status=403,
            )

        # Check if user can host this game (public or owned by user)
        is_game_admin = (
            hasattr(request.user, "profile") and request.user.profile.is_game_admin
        )
        if not game.is_public and game.owner != request.user and not is_game_admin:
            return JsonResponse(
                {"error": "You do not have permission to host this game."}, status=403
            )
        host_user = request.user

    session = GameSession.objects.create(
        game=game,
        admin_name=admin_name,
        max_teams=data.get("max_teams", 16),
        host_user=host_user,
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
@ratelimit(key="ip", rate="20/m", method="POST", block=True)
@transaction.atomic
def join_session(request: HttpRequest, code: str) -> JsonResponse:
    """Team joins session. Supports late joins during active rounds."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    team_name = data.get("team_name", "").strip()

    # Validate team name
    if len(team_name) < 2 or len(team_name) > 100:
        return JsonResponse({"error": "Team name must be 2-100 characters"}, status=400)

    # Lock session row to prevent race conditions when checking team count
    try:
        session = GameSession.objects.select_for_update().get(code=code)
    except GameSession.DoesNotExist:
        return JsonResponse({"error": "Session not found"}, status=404)

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
def get_session_state(request: HttpRequest, code: str) -> JsonResponse:
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

    # Bulk query: Get set of team IDs that have answered current question
    answered_team_ids = set()
    if session.current_question:
        answered_team_ids = set(
            TeamAnswer.objects.filter(
                team__session=session,
                question=session.current_question,
                answer_text__gt="",
            ).values_list("team_id", flat=True)
        )

    teams = list(session.teams.order_by("id"))
    teams_data = [
        {
            "id": t.id,
            "name": t.name,
            "score": t.score,
            "joined_late": t.joined_late,
            "has_answered_current": t.id in answered_team_ids,
        }
        for t in teams
    ]

    # Get round progress: submission counts for each question in current round
    round_progress = []
    if session.current_round:
        questions_in_round = list(
            session.game.questions.filter(game_round=session.current_round).order_by(
                "question_number"
            )
        )

        total_teams = len(teams)

        # Bulk query: Get submission counts per question
        submission_counts = dict(
            TeamAnswer.objects.filter(
                question__in=questions_in_round,
                team__session=session,
                answer_text__gt="",
            )
            .values("question_id")
            .annotate(count=models.Count("id"))
            .values_list("question_id", "count")
        )

        for question in questions_in_round:
            round_progress.append(
                {
                    "question_id": question.id,
                    "question_number": question.question_number,
                    "submitted_count": submission_counts.get(question.id, 0),
                    "total_teams": total_teams,
                }
            )

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
            "round_progress": round_progress,
        }
    )


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================


@csrf_exempt
@require_http_methods(["POST"])
@require_admin_token
def admin_start_game(request: HttpRequest, code: str) -> JsonResponse:
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
def admin_set_question(request: HttpRequest, code: str) -> JsonResponse:
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
            return JsonResponse(
                {"error": "Can only navigate within current round in review mode"},
                status=400,
            )

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
def admin_toggle_team_navigation(request: HttpRequest, code: str) -> JsonResponse:
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
@transaction.atomic
def admin_lock_round(request: HttpRequest, code: str) -> JsonResponse:
    """Lock current round for scoring. All team answers become locked.
    For multi-part questions, splits answers into per-part records.
    Auto-scores Ranking and Matching questions.
    Auto-creates TeamAnswer objects with 0 points for unanswered questions."""
    session = request.session_obj
    session_round = session.session_rounds.get(round=session.current_round)

    if session_round.status != SessionRound.Status.ACTIVE:
        return JsonResponse({"error": "Round not active"}, status=400)

    # Get all questions in the current round
    questions_in_round = session.game.questions.filter(
        game_round=session.current_round
    ).prefetch_related("answers", "question_type")

    teams = list(session.teams.order_by("id"))

    for question in questions_in_round:
        scorer = scorer_for(question)
        is_multi_part = scorer.is_multi_part(question)

        for team in teams:
            # Get existing answer for this team/question (without answer_part)
            existing_answer = TeamAnswer.objects.filter(
                team=team, question=question, answer_part__isnull=True
            ).first()

            if is_multi_part:
                if existing_answer:
                    # Split into per-part records, then let the scorer apply
                    # auto-scoring where the rule is mechanical (Ranking,
                    # Matching). Manual-only types are a no-op here.
                    part_answers = scorer.split_submission(existing_answer)
                    scorer.auto_score(part_answers, question)

                    # Delete the original combined answer (parts are now separate)
                    existing_answer.delete()
                else:
                    # No answer submitted - create per-part records with 0 points
                    for answer_part in question.answers.order_by("display_order"):
                        TeamAnswer.objects.create(
                            team=team,
                            question=question,
                            answer_part=answer_part,
                            session_round=session_round,
                            answer_text="",
                            is_locked=True,
                            points_awarded=0,
                            scored_at=timezone.now(),
                        )
            else:
                # Single-answer question
                if existing_answer:
                    existing_answer.is_locked = True
                    existing_answer.save(update_fields=["is_locked"])
                else:
                    # Create TeamAnswer with 0 points for unanswered questions
                    TeamAnswer.objects.create(
                        team=team,
                        question=question,
                        session_round=session_round,
                        answer_text="",
                        is_locked=True,
                        points_awarded=0,
                        scored_at=timezone.now(),
                    )

    session_round.status = SessionRound.Status.LOCKED
    session_round.locked_at = timezone.now()
    session_round.save()

    session.status = GameSession.Status.SCORING
    session.save()

    return JsonResponse({"status": "locked"})


@require_http_methods(["GET"])
@require_admin_token
def admin_get_scoring_data(request: HttpRequest, code: str) -> JsonResponse:
    """Get all answers for current round for scoring UI.
    Returns per-part structure for multi-part questions."""
    session = request.session_obj
    session_round = session.session_rounds.get(round=session.current_round)

    questions = (
        session.game.questions.filter(game_round=session.current_round)
        .order_by("question_number")
        .prefetch_related("answers", "question_type")
    )

    teams = list(session.teams.order_by("id"))
    data = []

    for question in questions:
        is_multi_part = scorer_for(question).is_multi_part(question)
        answer_parts = list(question.answers.order_by("display_order"))

        q_data = {
            "id": question.id,
            "number": question.question_number,
            "text": question.text,
            "total_points": question.total_points,
            "category_name": question.category.name if question.category else None,
            "question_type": (
                question.question_type.name if question.question_type else None
            ),
            "is_multi_part": is_multi_part,
            "correct_answers": [
                {
                    "id": a.id,
                    "sub_question": a.text,
                    "answer_text": a.answer_text,
                    "correct_rank": a.correct_rank,
                    "points": a.points,
                    "display_order": a.display_order,
                }
                for a in answer_parts
            ],
            "team_answers": [],
        }

        for team in teams:
            if is_multi_part:
                # Get per-part TeamAnswer records
                part_answers = TeamAnswer.objects.filter(
                    team=team, question=question, answer_part__isnull=False
                ).select_related("answer_part")

                # Build lookup by answer_part_id
                part_lookup = {pa.answer_part_id: pa for pa in part_answers}

                parts = []
                total_points_awarded = 0
                all_scored = True

                for answer_part in answer_parts:
                    part_answer = part_lookup.get(answer_part.id)
                    if part_answer:
                        parts.append(
                            {
                                "answer_part_id": answer_part.id,
                                "team_answer_id": part_answer.id,
                                "answer_text": part_answer.answer_text,
                                "points_awarded": part_answer.points_awarded,
                                "max_points": answer_part.points,
                                "is_scored": part_answer.points_awarded is not None,
                            }
                        )
                        if part_answer.points_awarded is not None:
                            total_points_awarded += part_answer.points_awarded
                        else:
                            all_scored = False
                    else:
                        parts.append(
                            {
                                "answer_part_id": answer_part.id,
                                "team_answer_id": None,
                                "answer_text": "",
                                "points_awarded": None,
                                "max_points": answer_part.points,
                                "is_scored": False,
                            }
                        )
                        all_scored = False

                q_data["team_answers"].append(
                    {
                        "team_id": team.id,
                        "team_name": team.name,
                        "parts": parts,
                        "total_points_awarded": (
                            total_points_awarded if all_scored else None
                        ),
                        "is_scored": all_scored,
                    }
                )
            else:
                # Single-answer question (backwards compatible)
                answer = TeamAnswer.objects.filter(
                    team=team, question=question, answer_part__isnull=True
                ).first()

                q_data["team_answers"].append(
                    {
                        "team_id": team.id,
                        "team_name": team.name,
                        "answer_id": answer.id if answer else None,
                        "answer_text": answer.answer_text if answer else "",
                        "points_awarded": answer.points_awarded if answer else None,
                        "is_scored": (
                            answer.points_awarded is not None if answer else False
                        ),
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
@transaction.atomic
def admin_score_answer(request: HttpRequest, code: str) -> JsonResponse:
    """Award points for an answer or answer part.
    For per-part scoring, use team_answer_id (the TeamAnswer record ID).
    For single-answer questions, use answer_id or team_id + question_id."""
    session = request.session_obj

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # Support multiple ways to identify the answer to score
    team_answer_id = data.get("team_answer_id")  # Per-part scoring (TeamAnswer.id)
    answer_id = data.get("answer_id")  # Legacy: TeamAnswer.id
    team_id = data.get("team_id")
    question_id = data.get("question_id")
    answer_part_id = data.get("answer_part_id")  # Optional: Answer.id for per-part
    points = data.get("points")

    if points is None:
        return JsonResponse({"error": "points required"}, status=400)

    try:
        points = int(points)
    except (ValueError, TypeError):
        return JsonResponse({"error": "points must be an integer"}, status=400)

    if points < 0:
        return JsonResponse({"error": "Points cannot be negative"}, status=400)

    # Find the TeamAnswer to score
    answer = None

    if team_answer_id:
        # Per-part scoring via team_answer_id
        answer = get_object_or_404(TeamAnswer, id=team_answer_id)
    elif answer_id:
        # Legacy: answer_id is TeamAnswer.id
        answer = get_object_or_404(TeamAnswer, id=answer_id)
    elif team_id and question_id:
        team = get_object_or_404(SessionTeam, id=team_id, session=session)
        question = get_object_or_404(Question, id=question_id)
        session_round = session.session_rounds.get(round=question.game_round)

        if answer_part_id:
            # Per-part scoring via team_id + question_id + answer_part_id
            answer_part = get_object_or_404(Answer, id=answer_part_id)
            answer, _ = TeamAnswer.objects.get_or_create(
                team=team,
                question=question,
                answer_part=answer_part,
                defaults={"session_round": session_round, "is_locked": True},
            )
        else:
            # Single-answer question
            answer, _ = TeamAnswer.objects.get_or_create(
                team=team,
                question=question,
                answer_part=None,
                defaults={"session_round": session_round, "is_locked": True},
            )
    else:
        return JsonResponse(
            {"error": "Provide team_answer_id, answer_id, or (team_id + question_id)"},
            status=400,
        )

    # Validate points range based on whether this is per-part or full question
    if answer.answer_part:
        # Per-part scoring: max is the Answer.points value
        max_points = answer.answer_part.points
    else:
        # Full question scoring: max is question.total_points
        max_points = answer.question.total_points

    if points > max_points:
        return JsonResponse({"error": f"Points cannot exceed {max_points}"}, status=400)

    answer.points_awarded = points
    answer.scored_at = timezone.now()
    answer.save()

    # Recalculate team total score
    team = answer.team
    team.score = (
        team.answers.filter(points_awarded__isnull=False).aggregate(
            total=models.Sum("points_awarded")
        )["total"]
        or 0
    )
    team.save()

    # Calculate question total for this team (sum of all parts)
    question_total = (
        TeamAnswer.objects.filter(
            team=team, question=answer.question, points_awarded__isnull=False
        ).aggregate(total=models.Sum("points_awarded"))["total"]
        or 0
    )

    return JsonResponse(
        {
            "status": "scored",
            "team_answer_id": answer.id,
            "answer_id": answer.id,  # Legacy compatibility
            "answer_part_id": answer.answer_part_id,
            "points_awarded": points,
            "max_points": max_points,
            "question_total": question_total,
            "team_score": team.score,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
@require_admin_token
def admin_complete_round(request: HttpRequest, code: str) -> JsonResponse:
    """Mark round as scored, transition to REVIEWING state."""
    session = request.session_obj
    session_round = session.session_rounds.get(round=session.current_round)

    # Verify all answers are scored (including auto-scored unanswered questions)
    unscored = TeamAnswer.objects.filter(
        session_round=session_round,
        points_awarded__isnull=True,
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
def admin_start_next_round(request: HttpRequest, code: str) -> JsonResponse:
    """Exit review/leaderboard mode and start next round or end game."""
    session = request.session_obj

    if session.status not in [
        GameSession.Status.REVIEWING,
        GameSession.Status.LEADERBOARD,
    ]:
        return JsonResponse({"error": "Not in review or leaderboard mode"}, status=400)

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


@csrf_exempt
@require_http_methods(["POST"])
@require_admin_token
def admin_show_leaderboard(request: HttpRequest, code: str) -> JsonResponse:
    """Transition from REVIEWING to LEADERBOARD state."""
    session = request.session_obj

    if session.status != GameSession.Status.REVIEWING:
        return JsonResponse({"error": "Not in review mode"}, status=400)

    session.status = GameSession.Status.LEADERBOARD
    session.save()

    return JsonResponse({"status": "leaderboard"})


@require_http_methods(["GET"])
def get_leaderboard_data(request: HttpRequest, code: str) -> JsonResponse:
    """Get leaderboard data with team rankings, per-round scores, and upcoming rounds."""
    session = get_object_or_404(GameSession, code=code)

    # Get all teams ordered by score
    teams = list(session.teams.order_by("-score", "joined_at"))

    # Get scored rounds
    scored_rounds = list(
        session.session_rounds.filter(status=SessionRound.Status.SCORED)
        .select_related("round")
        .order_by("round__round_number")
    )

    # Get upcoming rounds (pending status)
    upcoming_rounds = list(
        session.session_rounds.filter(status=SessionRound.Status.PENDING)
        .select_related("round")
        .order_by("round__round_number")
    )

    # Pre-calculate max points per round with a single aggregated query
    round_max_points = dict(
        Question.objects.filter(game=session.game)
        .values("game_round_id")
        .annotate(max_points=models.Sum("total_points"))
        .values_list("game_round_id", "max_points")
    )

    # Pre-calculate team scores per round with a single aggregated query
    team_round_scores = {}
    score_data = (
        TeamAnswer.objects.filter(team__session=session, points_awarded__isnull=False)
        .values("team_id", "session_round_id")
        .annotate(total=models.Sum("points_awarded"))
    )
    for row in score_data:
        key = (row["team_id"], row["session_round_id"])
        team_round_scores[key] = row["total"]

    # Build completed rounds info
    total_game_points = 0
    points_played = 0
    completed_rounds = []
    for sr in scored_rounds:
        max_pts = round_max_points.get(sr.round_id, 0)
        points_played += max_pts
        total_game_points += max_pts
        completed_rounds.append(
            {
                "round_number": sr.round.round_number,
                "round_name": sr.round.name,
                "max_points": max_pts,
            }
        )

    # Build upcoming rounds info
    upcoming_rounds_data = []
    for sr in upcoming_rounds:
        available_points = round_max_points.get(sr.round_id, 0)
        total_game_points += available_points
        upcoming_rounds_data.append(
            {
                "round_number": sr.round.round_number,
                "round_name": sr.round.name,
                "available_points": available_points,
            }
        )

    points_remaining = total_game_points - points_played

    # Build leaderboard with per-round scores (no additional queries needed)
    leaderboard = []
    for rank, team in enumerate(teams, start=1):
        round_scores = []
        for sr in scored_rounds:
            points_scored = team_round_scores.get((team.id, sr.id), 0)
            max_points = round_max_points.get(sr.round_id, 0)
            round_scores.append(
                {
                    "round_number": sr.round.round_number,
                    "points_scored": points_scored,
                    "max_points": max_points,
                }
            )

        leaderboard.append(
            {
                "rank": rank,
                "team_name": team.name,
                "total_score": team.score,
                "round_scores": round_scores,
            }
        )

    # Determine if this is the final round
    is_final_round = len(upcoming_rounds_data) == 0

    return JsonResponse(
        {
            "leaderboard": leaderboard,
            "completed_rounds": completed_rounds,
            "upcoming_rounds": upcoming_rounds_data,
            "total_game_points": total_game_points,
            "points_played": points_played,
            "points_remaining": points_remaining,
            "is_final_round": is_final_round,
        }
    )


# ============================================================================
# TEAM ENDPOINTS
# ============================================================================


@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key="ip", rate="60/m", method="POST", block=True)
@require_team_token
def team_submit_answer(request: HttpRequest, code: str) -> JsonResponse:
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
def team_get_answers(request: HttpRequest, code: str) -> JsonResponse:
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
        # Check for per-part answers first (new format)
        part_answers = team.answers.filter(
            question=question, answer_part__isnull=False
        ).order_by("answer_part__display_order")

        if part_answers.exists():
            # Aggregate per-part answers into JSON array format for frontend
            answer_texts = [pa.answer_text or "" for pa in part_answers]
            combined_answer_text = json.dumps(answer_texts)
            # Sum up points from all parts
            total_points = sum(
                pa.points_awarded
                for pa in part_answers
                if pa.points_awarded is not None
            )
            all_scored = all(pa.points_awarded is not None for pa in part_answers)
            any_locked = any(pa.is_locked for pa in part_answers)

            answers_data.append(
                {
                    "question_id": question.id,
                    "question_number": question.question_number,
                    "question_text": question.text,
                    "answer_text": combined_answer_text,
                    "is_locked": any_locked,
                    "points_awarded": total_points if all_scored else None,
                }
            )
        else:
            # Fall back to single answer (old format or simple questions)
            answer = team.answers.filter(
                question=question, answer_part__isnull=True
            ).first()
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
def team_get_question_details(request: HttpRequest, code: str) -> JsonResponse:
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
def team_get_results(request: HttpRequest, code: str) -> JsonResponse:
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


# ============================================================================
# SESSION VALIDATION & RE-AUTHENTICATION ENDPOINTS
# ============================================================================


@csrf_exempt
@require_http_methods(["POST"])
def validate_session_access(request: HttpRequest, code: str) -> JsonResponse:
    """
    Validates admin and/or team tokens for a session.
    Returns which roles the user has valid access to.
    This is the SOURCE OF TRUTH for role determination on page load.
    """
    session = get_object_or_404(GameSession, code=code)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    admin_token = data.get("admin_token")
    team_token = data.get("team_token")

    response = {
        "is_valid_admin": False,
        "is_valid_team": False,
        "team_id": None,
        "team_name": None,
    }

    # Validate admin token
    if admin_token and session.admin_token == admin_token:
        response["is_valid_admin"] = True
        # Update admin heartbeat
        session.admin_last_seen = timezone.now()
        session.save(update_fields=["admin_last_seen"])

    # Validate team token
    if team_token:
        try:
            team = session.teams.get(token=team_token)
            response["is_valid_team"] = True
            response["team_id"] = team.id
            response["team_name"] = team.name
            # Update team heartbeat
            team.last_seen = timezone.now()
            team.save(update_fields=["last_seen"])
        except SessionTeam.DoesNotExist:
            pass

    return JsonResponse(response)


@csrf_exempt
@require_http_methods(["POST"])
def rejoin_session(request: HttpRequest, code: str) -> JsonResponse:
    """
    Allows a team to rejoin a session by providing their team name.
    Returns existing team token if team name matches, allowing recovery from token loss.
    This preserves all team progress, answers, and state.
    """
    session = get_object_or_404(GameSession, code=code)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    team_name = data.get("team_name", "").strip()

    # Validate team name
    if len(team_name) < 2 or len(team_name) > 100:
        return JsonResponse({"error": "Team name must be 2-100 characters"}, status=400)

    # Check if session is still active
    if session.status == GameSession.Status.COMPLETED:
        return JsonResponse({"error": "Game has ended"}, status=400)

    # Try to find existing team with this name
    try:
        team = session.teams.get(name__iexact=team_name)
        # Team found - return their existing token
        return JsonResponse(
            {
                "team_id": team.id,
                "team_token": team.token,
                "team_name": team.name,
                "score": team.score,
                "rejoined": True,
            }
        )
    except SessionTeam.DoesNotExist:
        # Team name not found in this session
        return JsonResponse(
            {"error": f"No team named '{team_name}' found in this session"}, status=404
        )
