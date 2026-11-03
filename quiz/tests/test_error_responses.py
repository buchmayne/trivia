"""Public error messages must not expose unexpected exception details."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from quiz.models import (
    Category,
    Game,
    GameSession,
    Question,
    QuestionRound,
    QuestionType,
    SessionRound,
    SessionTeam,
    TeamAnswer,
)


class UnexpectedViewErrorsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(username="error-test-staff", is_staff=True)
        cls.game = Game.objects.create(subtitle="Error boundary test")
        cls.round = QuestionRound.objects.create(name="Round 1", round_number=1)
        cls.question = Question.objects.create(
            game=cls.game,
            game_round=cls.round,
            category=Category.objects.create(name="General"),
            question_type=QuestionType.objects.create(name="Multiple Choice"),
            text="Test question",
            question_number=1,
        )

    def setUp(self):
        self.client.force_login(self.staff)

    def test_unexpected_details_are_logged_but_never_returned(self):
        cases = [
            (
                reverse("quiz:first_question", args=[self.round.id]),
                {"game_id": self.game.id},
                "quiz.views.Question.objects.filter",
                400,
                "Unable to load question.",
            ),
            (
                reverse("quiz:first_question_info", args=[self.game.id, self.round.id]),
                {},
                "quiz.views.Question.objects.filter",
                400,
                "Unable to load question.",
            ),
            (
                reverse("quiz:next_question_number", args=[self.game.id]),
                {},
                "quiz.views.Question.objects.filter",
                500,
                "Unable to determine the next question number.",
            ),
            (
                reverse("quiz:next_game_order"),
                {},
                "quiz.views.Game.objects.exclude",
                500,
                "Unable to determine the next game order.",
            ),
        ]
        for debug in (False, True):
            for url, data, dependency, status, public_message in cases:
                with self.subTest(debug=debug, url=url), override_settings(DEBUG=debug):
                    error = RuntimeError("private-db.internal password=do-not-expose")
                    with (
                        patch(dependency, side_effect=error),
                        self.assertLogs("quiz.views", level="ERROR") as logs,
                    ):
                        response = self.client.get(url, data)
                    self.assertEqual(response.status_code, status)
                    self.assertEqual(response.json(), {"error": public_message})
                    self.assertNotIn(str(error), response.content.decode())
                    self.assertEqual(len(logs.records), 1)
                    self.assertIs(logs.records[0].exc_info[1], error)
                    self.assertIsNotNone(logs.records[0].exc_info[2])

    def test_missing_first_question_info_is_a_safe_not_found_response(self):
        self.question.delete()
        response = self.client.get(
            reverse("quiz:first_question_info", args=[self.game.id, self.round.id])
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"error": "No questions found"})

    def test_first_question_info_success_shape_is_unchanged(self):
        response = self.client.get(
            reverse("quiz:first_question_info", args=[self.game.id, self.round.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"id": self.question.id, "category_id": self.question.category_id},
        )

    def test_bad_game_id_does_not_echo_orm_exception(self):
        with self.assertLogs("quiz.views", level="ERROR"):
            response = self.client.get(
                reverse("quiz:first_question", args=[self.round.id]),
                {"game_id": "not-an-id"},
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Unable to load question."})


class LifecycleValidationErrorsTest(TestCase):
    """InvalidTransition contains deliberate public domain messages, not internals.

    Exercise the real Director and API, rather than mocking InvalidTransition.
    """

    def setUp(self):
        self.game = Game.objects.create(subtitle="Lifecycle error test")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.question = Question.objects.create(
            game=self.game,
            game_round=self.round,
            category=Category.objects.create(name="General"),
            question_type=QuestionType.objects.create(name="Multiple Choice"),
            text="Test question",
            question_number=1,
        )
        self.session = GameSession.objects.create(
            game=self.game, admin_name="Test host", current_round=self.round
        )
        self.session_round = SessionRound.objects.create(
            session=self.session, round=self.round
        )

    def assert_domain_error(self, endpoint, message, data=None):
        response = self.client.post(
            reverse(endpoint, kwargs={"code": self.session.code}),
            data=data or {},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": message})

    def test_start_without_teams_keeps_actionable_message(self):
        self.assert_domain_error("quiz:session_admin_start", "Need at least 1 team")

    def test_question_in_pending_round_keeps_actionable_message(self):
        self.assert_domain_error(
            "quiz:session_admin_question",
            "Question not in active round",
            {"question_id": self.question.id},
        )

    def test_lock_inactive_round_keeps_actionable_message(self):
        self.assert_domain_error("quiz:session_admin_lock", "Round not active")

    def test_complete_with_unscored_answer_keeps_numeric_validation(self):
        team = SessionTeam.objects.create(session=self.session, name="Test team")
        TeamAnswer.objects.create(
            team=team,
            question=self.question,
            session_round=self.session_round,
            answer_text="Pending score",
            is_locked=True,
        )
        self.assert_domain_error(
            "quiz:session_admin_complete", "1 answers still need scoring"
        )

    def test_advance_outside_review_keeps_actionable_message(self):
        self.assert_domain_error(
            "quiz:session_admin_start_next", "Not in review or leaderboard mode"
        )

    def test_leaderboard_outside_review_keeps_actionable_message(self):
        self.assert_domain_error(
            "quiz:session_admin_show_leaderboard", "Not in review mode"
        )
