"""Safety tests: no live S3 calls; originals must never be changed or deleted."""

import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from botocore.exceptions import ClientError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from PIL import Image

from quiz.image_processing import optimize_image
from quiz.models import Answer, Game, Question, QuestionRound, QuestionType


def png_bytes(color="red"):
    buf = BytesIO()
    Image.new("RGB", (100, 80), color).save(buf, format="PNG")
    return buf.getvalue()


class MemoryClient:
    def __init__(self):
        self.objects = {}
        self.calls = []
        self.corrupt_read = False
        self.content_type = "image/webp"
        self.after_read = None

    def put_object(self, **params):
        self.calls.append(("put", params["Key"]))
        assert params["IfNoneMatch"] == "*"
        if params["Key"] in self.objects:
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        self.objects[params["Key"]] = params["Body"]

    def get_object(self, **params):
        self.calls.append(("get", params["Key"]))
        data = self.objects[params["Key"]]
        if self.corrupt_read:
            data = b"x" * len(data)
        if self.after_read:
            self.after_read()
        return {
            "ContentLength": len(data),
            "ContentType": self.content_type,
            "Body": BytesIO(data),
        }


class MemoryStorage:
    bucket_name = "test-media-bucket"
    location = ""

    def __init__(self):
        self.sources = {"game-1/Category/shot.png": png_bytes()}
        self.reads = []
        self.client = MemoryClient()
        self.connection = SimpleNamespace(meta=SimpleNamespace(client=self.client))

    def open(self, key, mode="rb"):
        self.reads.append(key)
        return BytesIO(self.sources[key])

    def get_object_parameters(self, key):
        return {"CacheControl": "max-age=86400"}

    def delete(self, *args, **kwargs):
        raise AssertionError("Backfill must never delete an original")


class BackfillTest(TestCase):
    def setUp(self):
        self.game = Game.objects.create(subtitle="Test Game")
        self.kind = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.key = "game-1/Category/shot.png"
        self.question = Question.objects.create(
            game=self.game,
            question_type=self.kind,
            game_round=self.round,
            text="Test",
            question_number=1,
            # Legacy URL-only rows must work, too.
            question_image_url=self.key,
        )
        self.storage = MemoryStorage()
        patcher = patch(
            "quiz.management.commands.optimize_existing_images.S3MediaStorage",
            return_value=self.storage,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        data, _ = optimize_image(png_bytes(), self.key)
        self.optimized = data
        self.new_key = f"optimized/{hashlib.sha256(data).hexdigest()}.webp"

    def run_command(self, **kwargs):
        out = StringIO()
        call_command(
            "optimize_existing_images", stdout=out, stderr=StringIO(), **kwargs
        )
        return out.getvalue()

    def assert_path(self, expected, model=Question, field="question_image", pk=None):
        current = model.objects.get(pk=pk or self.question.pk)
        self.assertEqual(getattr(current, field).name, expected)
        self.assertTrue(getattr(current, f"{field}_url").endswith(expected))

    def test_dry_run_never_reads_or_writes_s3_or_changes_db(self):
        out = self.run_command()
        self.assertIn(f"would convert: {self.key}", out)
        self.assertIn("1 distinct sources", out)
        self.assertEqual(self.storage.reads, [])
        self.assertEqual(self.storage.client.calls, [])
        self.question.refresh_from_db()
        self.assertTrue(self.question.question_image_url.endswith(self.key))
        self.assertFalse(self.question.question_image)

    def test_apply_without_versioning_is_additive_and_verified_before_db_write(self):
        def before_db_write():
            self.question.refresh_from_db()
            self.assertTrue(self.question.question_image_url.endswith(self.key))

        self.storage.client.after_read = before_db_write
        self.run_command(apply=True)
        self.assertEqual(
            self.storage.client.calls, [("put", self.new_key), ("get", self.new_key)]
        )
        self.assert_path(self.new_key)
        self.assertEqual(self.storage.sources[self.key], png_bytes())

    def test_external_urls_are_left_unchanged(self):
        external = "https://github.com/example/repo/blob/main/image.png?raw=true"
        Question.objects.filter(pk=self.question.pk).update(question_image_url=external)
        out = self.run_command(apply=True)
        self.assertIn("1 external references", out)
        self.assertEqual(self.storage.reads, [])
        self.question.refresh_from_db()
        self.assertIn(external, self.question.question_image_url)

    def test_shared_sources_converted_once_and_all_references_updated(self):
        answer = Answer.objects.create(
            question=self.question, answer_image=self.key, answer_image_url=self.key
        )
        self.run_command(apply=True)
        self.assertEqual(self.storage.reads, [self.key])
        self.assert_path(self.new_key)
        self.assert_path(self.new_key, model=Answer, field="answer_image", pk=answer.pk)

    def test_repeat_run_is_noop(self):
        self.run_command(apply=True)
        self.storage.client.calls.clear()
        self.storage.reads.clear()
        self.run_command(apply=True)
        self.assertEqual(self.storage.reads, [])
        self.assertEqual(self.storage.client.calls, [])

    def test_preexisting_identical_copy_is_verified_and_reused(self):
        self.storage.client.objects[self.new_key] = self.optimized
        self.run_command(apply=True)
        self.assert_path(self.new_key)
        self.assertEqual(self.storage.client.objects[self.new_key], self.optimized)

    def test_checksum_mismatch_leaves_database_and_original_untouched(self):
        self.storage.client.corrupt_read = True
        with self.assertRaises(CommandError):
            self.run_command(apply=True)
        self.question.refresh_from_db()
        self.assertTrue(self.question.question_image_url.endswith(self.key))
        self.assertEqual(self.storage.sources[self.key], png_bytes())

    def test_wrong_content_type_leaves_database_unchanged(self):
        self.storage.client.content_type = "application/octet-stream"
        with self.assertRaises(CommandError):
            self.run_command(apply=True)
        self.question.refresh_from_db()
        self.assertTrue(self.question.question_image_url.endswith(self.key))

    def test_existing_different_copy_is_never_overwritten(self):
        self.storage.client.objects[self.new_key] = b"different bytes"
        with self.assertRaises(CommandError):
            self.run_command(apply=True)
        self.assertEqual(self.storage.client.objects[self.new_key], b"different bytes")
        self.question.refresh_from_db()
        self.assertTrue(self.question.question_image_url.endswith(self.key))

    def test_concurrent_edit_is_not_overwritten(self):
        def edit_during_verification():
            Question.objects.filter(pk=self.question.pk).update(
                question_image_url="other.png"
            )

        self.storage.client.after_read = edit_during_verification
        with self.assertRaises(CommandError):
            self.run_command(apply=True)
        self.question.refresh_from_db()
        self.assertTrue(self.question.question_image_url.endswith("other.png"))

    def test_missing_source_failure_does_not_stop_other_sources(self):
        answer = Answer.objects.create(
            question=self.question, answer_image_url="other.png"
        )
        del self.storage.sources[self.key]
        self.storage.sources["other.png"] = png_bytes()
        with self.assertRaises(CommandError):
            self.run_command(apply=True)
        self.assert_path(self.new_key, model=Answer, field="answer_image", pk=answer.pk)

    def test_limit_counts_failed_attempts_too(self):
        Answer.objects.create(question=self.question, answer_image_url="other.png")
        del self.storage.sources[self.key]
        self.storage.sources["other.png"] = png_bytes()
        with self.assertRaises(CommandError):
            self.run_command(apply=True, limit=1)
        self.assertEqual(self.storage.reads, [self.key])

    def test_invalid_limit_fails_before_any_work(self):
        with self.assertRaises(CommandError):
            self.run_command(apply=True, limit=0)
        self.assertEqual(self.storage.reads, [])

    def test_undecodable_original_passes_through(self):
        self.storage.sources[self.key] = b"not an image"
        out = self.run_command(apply=True)
        self.assertIn("1 passed through", out)
        self.assertEqual(self.storage.client.calls, [])

    def test_report_records_keys_hashes_and_sizes(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            self.run_command(apply=True, report=str(path))
            report = json.loads(path.read_text())
        self.assertEqual(report["status"], "complete")
        self.assertTrue(report["originals_retained"])
        self.assertEqual(report["results"][0]["old_key"], self.key)
        self.assertEqual(report["results"][0]["new_key"], self.new_key)
        self.assertEqual(report["results"][0]["optimized_bytes"], len(self.optimized))

    def test_same_basename_different_sources_do_not_collide(self):
        answer = Answer.objects.create(
            question=self.question, answer_image_url="game-1/Category/shot.jpg"
        )
        self.storage.sources["game-1/Category/shot.jpg"] = png_bytes("blue")
        self.run_command(apply=True)
        answer.refresh_from_db()
        self.assertNotEqual(answer.answer_image.name, self.new_key)
        self.assertEqual(len(self.storage.client.objects), 2)

    def test_mirror_preserves_even_undecodable_originals_and_never_overwrites(self):
        self.storage.sources[self.key] = b"corrupt but must be backed up"
        with TemporaryDirectory() as directory:
            # Patch only the mirror's root, not pathlib used for other operations.
            with patch(
                "quiz.management.commands.optimize_existing_images.Path", wraps=Path
            ) as path_class:
                path_class.return_value = Path(directory)
                self.run_command(download_originals=True)
                dest = Path(directory) / self.key
                self.assertEqual(dest.read_bytes(), self.storage.sources[self.key])
                self.storage.sources[self.key] = b"changed"
                with self.assertRaises(CommandError):
                    self.run_command(download_originals=True)
                self.assertEqual(dest.read_bytes(), b"corrupt but must be backed up")
