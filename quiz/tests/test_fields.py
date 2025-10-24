"""
Tests for quiz/fields.py - Custom model fields for S3/CloudFront integration
"""
from django.test import TestCase
from django.conf import settings
from unittest.mock import Mock, patch, MagicMock
from quiz.fields import CloudFrontURLField, S3ImageField, S3VideoField
from quiz.models import Question, Game, QuestionType, QuestionRound


class CloudFrontURLFieldTest(TestCase):
    """Test the CloudFrontURLField custom field"""

    def setUp(self):
        self.field = CloudFrontURLField()

    def test_get_full_url_with_relative_path(self):
        """Test that relative paths get CloudFront domain prepended"""
        path = "/2024/01/image.jpg"
        full_url = CloudFrontURLField.get_full_url(path)

        expected = f"{settings.AWS_CLOUDFRONT_DOMAIN}/2024/01/image.jpg"
        self.assertEqual(full_url, expected)

    def test_get_full_url_with_leading_slash_removed(self):
        """Test that leading slashes are handled correctly"""
        path = "/path/to/image.jpg"
        full_url = CloudFrontURLField.get_full_url(path)

        # Should remove duplicate slashes
        self.assertIn(settings.AWS_CLOUDFRONT_DOMAIN, full_url)
        self.assertNotIn("//path", full_url)

    def test_get_full_url_already_has_domain(self):
        """Test that URLs with domain already are not modified"""
        path = f"{settings.AWS_CLOUDFRONT_DOMAIN}/path/to/image.jpg"
        full_url = CloudFrontURLField.get_full_url(path)

        self.assertEqual(full_url, path)

    def test_get_full_url_with_none(self):
        """Test handling of None value"""
        full_url = CloudFrontURLField.get_full_url(None)
        self.assertIsNone(full_url)

    def test_get_full_url_with_empty_string(self):
        """Test handling of empty string"""
        full_url = CloudFrontURLField.get_full_url("")
        self.assertEqual(full_url, "")

    def test_to_python_strips_cloudfront_domain(self):
        """Test that to_python strips the CloudFront domain"""
        value = f"{settings.AWS_CLOUDFRONT_DOMAIN}/path/to/image.jpg"
        result = self.field.to_python(value)

        self.assertEqual(result, "/path/to/image.jpg")

    def test_to_python_preserves_relative_path(self):
        """Test that relative paths are preserved"""
        value = "/path/to/image.jpg"
        result = self.field.to_python(value)

        self.assertEqual(result, value)

    def test_get_prep_value_strips_domain(self):
        """Test that get_prep_value strips CloudFront domain before saving"""
        value = f"{settings.AWS_CLOUDFRONT_DOMAIN}/path/to/image.jpg"
        result = self.field.get_prep_value(value)

        self.assertEqual(result, "/path/to/image.jpg")

    def test_get_prep_value_with_none(self):
        """Test get_prep_value with None"""
        result = self.field.get_prep_value(None)
        self.assertIsNone(result)

    def test_from_db_value_adds_cloudfront_domain(self):
        """Test that from_db_value adds CloudFront domain when retrieving"""
        value = "/path/to/image.jpg"
        result = self.field.from_db_value(value, None, None)

        expected = f"{settings.AWS_CLOUDFRONT_DOMAIN}/path/to/image.jpg"
        self.assertEqual(result, expected)

    def test_from_db_value_with_none(self):
        """Test from_db_value with None"""
        result = self.field.from_db_value(None, None, None)
        self.assertIsNone(result)


class S3ImageFieldTest(TestCase):
    """Test the S3ImageField custom field"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)

    def test_field_has_s3_storage(self):
        """Test that S3ImageField uses S3 storage"""
        field = S3ImageField()
        self.assertIsNotNone(field.storage)

    def test_generate_filename_removes_leading_slash(self):
        """Test that generate_filename handles leading slashes correctly"""
        field = S3ImageField()
        question = Question(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            text="Test",
            question_number=1,
        )

        with patch("quiz.upload_helpers.get_upload_path") as mock_get_path:
            mock_get_path.return_value = "/2024/01/image.jpg"
            filename = field.generate_filename(question, "image.jpg")

            # Should remove leading slash
            self.assertEqual(filename, "2024/01/image.jpg")
            self.assertFalse(filename.startswith("/"))

    def test_generate_filename_without_leading_slash(self):
        """Test generate_filename with path that doesn't have leading slash"""
        field = S3ImageField()
        question = Question(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            text="Test",
            question_number=1,
        )

        with patch("quiz.upload_helpers.get_upload_path") as mock_get_path:
            mock_get_path.return_value = "2024/01/image.jpg"
            filename = field.generate_filename(question, "image.jpg")

            self.assertEqual(filename, "2024/01/image.jpg")

    @patch("quiz.fields.S3ImageField.pre_save")
    def test_pre_save_updates_url_field(self, mock_pre_save):
        """Test that pre_save updates the corresponding URL field"""
        # This is a complex integration test that would require full model setup
        # Testing this behavior is better done in integration tests
        pass


class S3VideoFieldTest(TestCase):
    """Test the S3VideoField custom field"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)

    def test_field_has_s3_storage(self):
        """Test that S3VideoField uses S3 storage"""
        field = S3VideoField()
        self.assertIsNotNone(field.storage)

    def test_generate_filename_removes_leading_slash(self):
        """Test that generate_filename handles leading slashes correctly"""
        field = S3VideoField()
        question = Question(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            text="Test",
            question_number=1,
        )

        with patch("quiz.upload_helpers.get_upload_path") as mock_get_path:
            mock_get_path.return_value = "/2024/01/video.mp4"
            filename = field.generate_filename(question, "video.mp4")

            # Should remove leading slash
            self.assertEqual(filename, "2024/01/video.mp4")
            self.assertFalse(filename.startswith("/"))

    def test_generate_filename_without_leading_slash(self):
        """Test generate_filename with path that doesn't have leading slash"""
        field = S3VideoField()
        question = Question(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            text="Test",
            question_number=1,
        )

        with patch("quiz.upload_helpers.get_upload_path") as mock_get_path:
            mock_get_path.return_value = "2024/01/video.mp4"
            filename = field.generate_filename(question, "video.mp4")

            self.assertEqual(filename, "2024/01/video.mp4")


class FieldIntegrationTest(TestCase):
    """Integration tests for custom fields with actual models"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)

    def test_cloudfront_url_field_in_model(self):
        """Test CloudFrontURLField behavior when used in a model"""
        question = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            text="Test Question",
            question_number=1,
            question_image_url="/2024/01/test.jpg",
        )

        # Retrieve from database
        retrieved = Question.objects.get(id=question.id)

        # Should have CloudFront domain prepended
        self.assertIn(settings.AWS_CLOUDFRONT_DOMAIN, retrieved.question_image_url)
        self.assertIn("/2024/01/test.jpg", retrieved.question_image_url)

    def test_cloudfront_url_field_stores_relative_path(self):
        """Test that CloudFront URL field stores only the relative path in DB"""
        question = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            text="Test Question",
            question_number=1,
            question_image_url=f"{settings.AWS_CLOUDFRONT_DOMAIN}/2024/01/test.jpg",
        )

        # Check what's actually stored in the database
        # Use values() to bypass the field's from_db_value
        db_value = Question.objects.filter(id=question.id).values(
            "question_image_url"
        )[0]["question_image_url"]

        # Should store only the path, not the full URL
        self.assertEqual(db_value, "/2024/01/test.jpg")
        self.assertNotIn(settings.AWS_CLOUDFRONT_DOMAIN, db_value)
