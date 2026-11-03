"""Integration checks run with `uv run python -m studio_sandbox.manage test studio_sandbox`."""

import subprocess
import sys
from unittest import skipUnless

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse

from studio.models import Category, Challenge, Game, Task
from studio.projections import challenge_preview


@skipUnless(settings.ROOT_URLCONF == "studio_sandbox.urls", "Requires sandbox settings")
@override_settings(DEBUG=True, ENABLE_V2_STUDIO=True)
class SandboxWorkflowTests(TestCase):
    def test_site_has_only_local_sqlite_and_studio_apps(self):
        self.assertEqual(connection.vendor, "sqlite")
        self.assertEqual(
            settings.DATABASES["default"]["ENGINE"], "django.db.backends.sqlite3"
        )
        # TestCase replaces the on-disk database name with an in-memory URI.
        self.assertEqual(settings.MEDIA_ROOT, settings.SANDBOX_DIR / "media")
        self.assertFalse(apps.is_installed("quiz"))
        self.assertFalse(apps.is_installed("django.contrib.admin"))
        self.assertNotIn("postgres", str(settings.DATABASES).lower())
        self.assertEqual(
            settings.STORAGES["default"]["BACKEND"],
            "django.core.files.storage.FileSystemStorage",
        )

    def test_login_capture_choose_one_preview_and_game_in_sqlite(self):
        self.assertRedirects(
            self.client.get("/studio/"),
            "/accounts/login/?next=/studio/",
            fetch_redirect_response=False,
        )
        self.assertContains(self.client.get("/accounts/login/"), "Studio sandbox login")
        get_user_model().objects.create_user(
            username="sandbox-author", password="sandbox-password", is_staff=True
        )
        self.assertRedirects(
            self.client.post(
                "/accounts/login/",
                {"username": "sandbox-author", "password": "sandbox-password"},
            ),
            "/studio/",
        )
        self.assertContains(self.client.get("/studio/"), "Studio")
        self.assertEqual(
            self.client.post(
                reverse("studio:add_category"), {"name": "Language"}
            ).status_code,
            302,
        )
        category = Category.objects.get(name="Language")
        self.assertEqual(
            self.client.post(
                reverse("studio:capture"),
                {
                    "working_title": "Selling like hot cakes",
                    "rough_notes": "",
                    "category": category.pk,
                },
            ).status_code,
            302,
        )
        challenge = Challenge.objects.get(working_title="Selling like hot cakes")
        self.assertEqual(
            self.client.post(
                reverse("studio:new_block", args=[challenge.pk]),
                {"phase": "prompt", "text": "Where does this idiom come from?"},
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(
                reverse("studio:new_task", args=[challenge.pk]),
                {"format": "single_choice", "max_points": 1},
            ).status_code,
            302,
        )
        task = Task.objects.get(challenge=challenge)
        for option in ("Gold Rush", "Village fairs", "London vendors"):
            self.assertEqual(
                self.client.post(
                    reverse("studio:new_option", args=[challenge.pk, task.pk]),
                    {
                        "prompt_text": option,
                        "reveal_text": (
                            "Historical context" if option == "London vendors" else ""
                        ),
                    },
                ).status_code,
                302,
            )
        correct = task.response_pool.items.order_by("order").last()
        self.assertEqual(
            self.client.post(
                reverse("studio:edit_task", args=[challenge.pk, task.pk]),
                {
                    "format": "single_choice",
                    "max_points": 1,
                    "correct_item": correct.pk,
                },
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(
                reverse("studio:change_status", args=[challenge.pk]),
                {"status": "ready"},
            ).status_code,
            302,
        )
        self.assertNotContains(
            self.client.get(reverse("studio:preview", args=[challenge.pk, "question"])),
            "Historical context",
        )
        self.assertContains(
            self.client.get(reverse("studio:preview", args=[challenge.pk, "reveal"])),
            "Historical context",
        )
        self.assertEqual(
            self.client.post(
                reverse(
                    "studio:item_action",
                    args=[challenge.pk, "options", correct.pk, "up"],
                ),
            ).status_code,
            302,
        )
        task.refresh_from_db()
        self.assertEqual(task.evaluation_key, {"correct_item_id": correct.pk})
        self.assertEqual(
            [
                item["label"]
                for item in challenge_preview(challenge, reveal=True)["tasks"][0][
                    "options"
                ]
                if item["correct"]
            ],
            ["B"],
        )
        self.assertEqual(
            self.client.post(
                reverse("studio:new_game"), {"name": "Test night"}
            ).status_code,
            302,
        )
        game = Game.objects.get(name="Test night")
        self.assertEqual(
            self.client.post(
                reverse("studio:game_add_round", args=[game.pk]),
                {"name": "First round"},
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(
                reverse(
                    "studio:game_add_placement", args=[game.pk, game.rounds.get().pk]
                ),
                {"challenge": challenge.pk},
            ).status_code,
            302,
        )
        self.assertContains(
            self.client.get(reverse("studio:game_preview", args=[game.pk, "question"])),
            "Where does this idiom come from?",
        )
        self.assertEqual(self.client.get("/quiz/").status_code, 404)
        self.assertEqual(self.client.get("/admin/").status_code, 404)

    def test_sandbox_does_not_require_quiz_profiles_and_rejects_nonstaff(self):
        visitor = get_user_model().objects.create_user(
            username="visitor", password="visitor-password"
        )
        self.client.force_login(visitor)
        self.assertEqual(self.client.get("/studio/").status_code, 403)
        self.assertEqual(Challenge.objects.count(), 0)

    def test_sandbox_entry_point_rejects_settings_override(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "studio_sandbox.manage",
                "check",
                "--settings=pub_trivia.settings",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not accept a settings override", result.stderr)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "studio_sandbox.manage",
                "runserver",
                "0.0.0.0:8765",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must bind to 127.0.0.1", result.stderr)
