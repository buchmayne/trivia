"""
Tests for quiz/serializers.py - Django REST Framework serializers
"""
from django.test import TestCase
from quiz.models import (
    Game,
    Question,
    Answer,
    QuestionType,
    QuestionRound,
    Category,
    GameSession,
    SessionTeam,
)
from quiz.serializers import (
    AnswerSerializer,
    QuestionSerializer,
    GameSerializer,
    GameDetailSerializer,
    QuestionWithAnswersSerializer,
    SessionCreateSerializer,
    SessionTeamSerializer,
    GameSessionSerializer,
    TeamAnswerSubmissionSerializer,
    GameRoundSerializer,
)


class AnswerSerializerTest(TestCase):
    """Test the AnswerSerializer"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.question = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            text="Test Question",
            question_number=1,
        )
        self.answer = Answer.objects.create(
            question=self.question,
            text="Paris",
            points=10,
            answer_text="The capital of France",
            display_order=1,
        )

    def test_answer_serialization(self):
        """Test serializing an answer"""
        serializer = AnswerSerializer(self.answer)
        data = serializer.data

        self.assertEqual(data["text"], "Paris")
        self.assertEqual(data["points"], 10)
        self.assertEqual(data["answer_text"], "The capital of France")
        self.assertEqual(data["display_order"], 1)

    def test_answer_serializer_fields(self):
        """Test that all expected fields are present"""
        serializer = AnswerSerializer(self.answer)
        data = serializer.data

        expected_fields = [
            "id",
            "text",
            "points",
            "answer_text",
            "question_image_url",
            "answer_image_url",
            "question_video_url",
            "answer_video_url",
            "display_order",
            "correct_rank",
        ]

        for field in expected_fields:
            self.assertIn(field, data)


class QuestionSerializerTest(TestCase):
    """Test the QuestionSerializer"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.question = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            text="What is the capital of France?",
            question_number=1,
            total_points=10,
        )

    def test_question_serialization(self):
        """Test serializing a question"""
        serializer = QuestionSerializer(self.question)
        data = serializer.data

        self.assertEqual(data["text"], "What is the capital of France?")
        self.assertEqual(data["question_number"], 1)
        self.assertEqual(data["total_points"], 10)

    def test_question_with_answers(self):
        """Test that answers are included in question serialization"""
        Answer.objects.create(
            question=self.question, text="Paris", points=10, display_order=1
        )
        Answer.objects.create(
            question=self.question, text="London", points=0, display_order=2
        )

        serializer = QuestionSerializer(self.question)
        data = serializer.data

        self.assertEqual(len(data["answers"]), 2)
        self.assertEqual(data["answers"][0]["text"], "Paris")


class GameSerializerTest(TestCase):
    """Test the GameSerializer"""

    def setUp(self):
        self.game = Game.objects.create(
            name="Trivia Night", description="Fun trivia game"
        )
        self.round1 = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.round2 = QuestionRound.objects.create(name="Round 2", round_number=2)

    def test_game_serialization(self):
        """Test serializing a game"""
        serializer = GameSerializer(self.game)
        data = serializer.data

        self.assertEqual(data["name"], "Trivia Night")
        self.assertEqual(data["description"], "Fun trivia game")
        self.assertIn("created_at", data)

    def test_game_serializer_fields(self):
        """Test that all expected fields are present"""
        serializer = GameSerializer(self.game)
        data = serializer.data

        expected_fields = ["id", "name", "description", "created_at", "rounds"]
        for field in expected_fields:
            self.assertIn(field, data)


class GameDetailSerializerTest(TestCase):
    """Test the GameDetailSerializer"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)

        # Create some questions
        for i in range(3):
            Question.objects.create(
                game=self.game,
                question_type=self.question_type,
                game_round=self.round,
                text=f"Question {i+1}",
                question_number=i + 1,
            )

    def test_total_questions_count(self):
        """Test that total_questions field returns correct count"""
        serializer = GameDetailSerializer(self.game)
        data = serializer.data

        self.assertEqual(data["total_questions"], 3)

    def test_game_detail_fields(self):
        """Test that all expected fields are present"""
        serializer = GameDetailSerializer(self.game)
        data = serializer.data

        expected_fields = ["id", "name", "description", "total_questions"]
        for field in expected_fields:
            self.assertIn(field, data)


class QuestionWithAnswersSerializerTest(TestCase):
    """Test the QuestionWithAnswersSerializer"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.question = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            text="Test Question",
            question_number=1,
            total_points=10,
        )
        Answer.objects.create(
            question=self.question, text="Answer 1", points=5, display_order=1
        )
        Answer.objects.create(
            question=self.question, text="Answer 2", points=5, display_order=2
        )

    def test_question_type_as_string(self):
        """Test that question_type returns name instead of ID"""
        serializer = QuestionWithAnswersSerializer(self.question)
        data = serializer.data

        self.assertEqual(data["question_type"], "Multiple Choice")
        self.assertNotIsInstance(data["question_type"], int)

    def test_answers_included(self):
        """Test that all answers are included"""
        serializer = QuestionWithAnswersSerializer(self.question)
        data = serializer.data

        self.assertEqual(len(data["answers"]), 2)


class SessionCreateSerializerTest(TestCase):
    """Test the SessionCreateSerializer"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")

    def test_create_session_valid_data(self):
        """Test creating a session with valid data"""
        data = {"game": self.game.id, "host_name": "John Doe"}

        serializer = SessionCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        session = serializer.save(session_code="ABC123")
        self.assertEqual(session.game, self.game)
        self.assertEqual(session.host_name, "John Doe")
        self.assertEqual(session.session_code, "ABC123")

    def test_create_session_missing_game(self):
        """Test validation fails without game"""
        data = {"host_name": "John Doe"}

        serializer = SessionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("game", serializer.errors)

    def test_create_session_missing_host_name(self):
        """Test validation fails without host_name"""
        data = {"game": self.game.id}

        serializer = SessionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("host_name", serializer.errors)


class SessionTeamSerializerTest(TestCase):
    """Test the SessionTeamSerializer"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(
            game=self.game, host_name="Host", session_code="ABC123"
        )
        self.team = SessionTeam.objects.create(
            session=self.session, team_name="Team A", total_score=50
        )

    def test_team_serialization(self):
        """Test serializing a team"""
        serializer = SessionTeamSerializer(self.team)
        data = serializer.data

        self.assertEqual(data["team_name"], "Team A")
        self.assertEqual(data["total_score"], 50)
        self.assertIn("joined_at", data)

    def test_team_serializer_fields(self):
        """Test that all expected fields are present"""
        serializer = SessionTeamSerializer(self.team)
        data = serializer.data

        expected_fields = ["id", "team_name", "total_score", "is_connected", "joined_at"]
        for field in expected_fields:
            self.assertIn(field, data)


class GameSessionSerializerTest(TestCase):
    """Test the GameSessionSerializer"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(
            game=self.game,
            host_name="Host",
            session_code="ABC123",
            status="active",
            current_question_number=5,
        )
        SessionTeam.objects.create(
            session=self.session, team_name="Team A", total_score=50
        )
        SessionTeam.objects.create(
            session=self.session, team_name="Team B", total_score=45
        )

    def test_session_serialization(self):
        """Test serializing a game session"""
        serializer = GameSessionSerializer(self.session)
        data = serializer.data

        self.assertEqual(data["session_code"], "ABC123")
        self.assertEqual(data["status"], "active")
        self.assertEqual(data["current_question_number"], 5)
        self.assertEqual(data["game_name"], "Test Game")

    def test_session_includes_teams(self):
        """Test that teams are included in session serialization"""
        serializer = GameSessionSerializer(self.session)
        data = serializer.data

        self.assertEqual(len(data["teams"]), 2)

    def test_session_game_name_readonly(self):
        """Test that game_name is correctly derived from game"""
        serializer = GameSessionSerializer(self.session)
        data = serializer.data

        self.assertEqual(data["game_name"], self.game.name)


class TeamAnswerSubmissionSerializerTest(TestCase):
    """Test the TeamAnswerSubmissionSerializer"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.question = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            text="Test Question",
            question_number=1,
        )
        self.session = GameSession.objects.create(
            game=self.game, host_name="Host", session_code="ABC123"
        )
        self.team = SessionTeam.objects.create(
            session=self.session, team_name="Team A"
        )

    def test_create_team_answer(self):
        """Test creating a team answer through serializer"""
        data = {
            "team_id": self.team.id,
            "question_id": self.question.id,
            "submitted_answer": "Paris",
            "points_awarded": 10,
        }

        serializer = TeamAnswerSubmissionSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        answer = serializer.save()
        self.assertEqual(answer.team, self.team)
        self.assertEqual(answer.question, self.question)
        self.assertEqual(answer.submitted_answer, "Paris")
        self.assertEqual(answer.points_awarded, 10)

    def test_team_answer_missing_fields(self):
        """Test validation with missing required fields"""
        data = {"team_id": self.team.id}

        serializer = TeamAnswerSubmissionSerializer(data=data)
        self.assertFalse(serializer.is_valid())


class GameRoundSerializerTest(TestCase):
    """Test the GameRoundSerializer"""

    def setUp(self):
        self.round = QuestionRound.objects.create(
            name="Final Round", round_number=3, description="The final showdown"
        )

    def test_round_serialization(self):
        """Test serializing a question round"""
        serializer = GameRoundSerializer(self.round)
        data = serializer.data

        self.assertEqual(data["name"], "Final Round")
        self.assertEqual(data["round_number"], 3)
        self.assertEqual(data["description"], "The final showdown")

    def test_round_serializer_fields(self):
        """Test that all expected fields are present"""
        serializer = GameRoundSerializer(self.round)
        data = serializer.data

        expected_fields = ["id", "name", "round_number", "description"]
        for field in expected_fields:
            self.assertIn(field, data)
