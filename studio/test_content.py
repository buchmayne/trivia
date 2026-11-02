from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Category, Challenge, ContentBlock, Task
from .projections import challenge_preview
from .services import (
    delete_content,
    move_content,
    save_block,
    save_draft,
    save_task,
    set_status,
)


@override_settings(ROOT_URLCONF="studio.test_urls", DEBUG=True, ENABLE_V2_STUDIO=True)
class FreeTextEditorTests(TestCase):
    def setUp(self):
        author = User.objects.create_user(username="author", password="testpass123")
        author.profile.is_game_admin = True
        author.profile.save()
        self.client.force_login(author)
        self.category = Category.objects.create(name="Language")
        self.challenge = save_draft(
            working_title="Origins of idioms", rough_notes="", category=self.category
        )

    def test_draft_can_be_incomplete_but_ready_needs_prompt_task_answer_and_points(
        self,
    ):
        self.assertEqual(
            self.client.get(
                reverse("studio:preview", args=[self.challenge.pk, "question"])
            ).status_code,
            200,
        )
        response = self.client.post(
            reverse("studio:change_status", args=[self.challenge.pk]),
            {"status": "ready"},
        )
        self.assertContains(response, "Add at least one task", status_code=400)
        self.assertEqual(self.challenge.status, Challenge.Status.DRAFT)
        task = save_task(challenge=self.challenge, max_points=2, reference_answer="")
        response = self.client.post(
            reverse("studio:change_status", args=[self.challenge.pk]),
            {"status": "ready"},
        )
        self.assertContains(response, "add prompt text", status_code=400)
        self.assertContains(response, "enter a reference answer", status_code=400)
        save_block(
            challenge=self.challenge, phase="prompt", text="Where does this come from?"
        )
        save_task(
            challenge=self.challenge,
            task=task,
            max_points=2,
            reference_answer="Hot cakes",
        )
        response = self.client.post(
            reverse("studio:change_status", args=[self.challenge.pk]),
            {"status": "ready"},
        )
        self.assertEqual(response.status_code, 302)
        self.challenge.refresh_from_db()
        self.assertEqual(self.challenge.status, Challenge.Status.READY)
        self.assertEqual(self.challenge.total_points, 2)

    def test_add_task_and_blocks_through_editor_and_hide_answer_from_question(self):
        task_response = self.client.post(
            reverse("studio:new_task", args=[self.challenge.pk]),
            {"max_points": "1", "reference_answer": "Correct origin"},
        )
        self.assertRedirects(
            task_response, reverse("studio:edit", args=[self.challenge.pk])
        )
        task = self.challenge.tasks.get()
        self.client.post(
            reverse("studio:new_block", args=[self.challenge.pk]),
            {"phase": "prompt", "task": task.pk, "text": "Which origin is correct?"},
        )
        self.client.post(
            reverse("studio:new_block", args=[self.challenge.pk]),
            {"phase": "reveal", "task": task.pk, "text": "An illuminating fact."},
        )
        self.client.post(
            reverse("studio:new_block", args=[self.challenge.pk]),
            {"phase": "prompt", "task": "", "text": "Common idioms"},
        )
        self.assertEqual(self.challenge.content_blocks.count(), 1)
        question = challenge_preview(self.challenge)
        self.assertEqual(
            question["tasks"][0]["prompt"][0]["text"], "Which origin is correct?"
        )
        self.assertNotIn("correct_result", question["tasks"][0])
        self.assertNotIn("reveal", question["tasks"][0])
        html = self.client.get(
            reverse("studio:preview", args=[self.challenge.pk, "question"])
        )
        self.assertContains(html, "Which origin is correct?")
        self.assertNotContains(html, "Correct origin")
        self.assertNotContains(html, "An illuminating fact")
        reveal = challenge_preview(self.challenge, reveal=True)
        self.assertEqual(reveal["tasks"][0]["correct_result"], "Correct origin")
        self.assertEqual(
            reveal["tasks"][0]["reveal"][0]["text"], "An illuminating fact."
        )
        reveal_html = self.client.get(
            reverse("studio:preview", args=[self.challenge.pk, "reveal"])
        )
        self.assertContains(reveal_html, "Correct origin")
        self.assertContains(reveal_html, "An illuminating fact")

    def test_draft_editing_reorders_tasks_and_blocks(self):
        first = save_task(challenge=self.challenge, max_points=1, reference_answer="A")
        second = save_task(challenge=self.challenge, max_points=2, reference_answer="B")
        one = save_block(challenge=self.challenge, phase="prompt", text="One")
        two = save_block(challenge=self.challenge, phase="prompt", text="Two")
        self.client.post(
            reverse(
                "studio:item_action", args=[self.challenge.pk, "tasks", second.pk, "up"]
            )
        )
        self.client.post(
            reverse(
                "studio:item_action", args=[self.challenge.pk, "blocks", two.pk, "up"]
            )
        )
        self.assertEqual(
            list(self.challenge.tasks.values_list("pk", flat=True)),
            [second.pk, first.pk],
        )
        self.assertEqual(
            list(self.challenge.content_blocks.values_list("pk", flat=True)),
            [two.pk, one.pk],
        )
        self.assertEqual(self.challenge.total_points, 3)
        updated = self.client.post(
            reverse("studio:edit_task", args=[self.challenge.pk, second.pk]),
            {"max_points": "3", "reference_answer": "B2"},
        )
        self.assertEqual(updated.status_code, 302)
        self.assertEqual(self.challenge.total_points, 4)
        block_edit = self.client.post(
            reverse("studio:edit_block", args=[self.challenge.pk, two.pk]),
            {"text": "Changed"},
        )
        self.assertEqual(block_edit.status_code, 302)
        two.refresh_from_db()
        self.assertEqual(two.text, "Changed")

    def test_ready_edits_must_remain_valid_and_failed_delete_rolls_back(self):
        task = save_task(
            challenge=self.challenge, max_points=1, reference_answer="Answer"
        )
        save_block(challenge=self.challenge, phase="prompt", text="Prompt")
        set_status(self.challenge, Challenge.Status.READY)
        invalid = self.client.post(
            reverse("studio:edit_task", args=[self.challenge.pk, task.pk]),
            {"max_points": "1", "reference_answer": ""},
        )
        self.assertContains(invalid, "enter a reference answer", status_code=400)
        task.refresh_from_db()
        self.assertEqual(task.evaluation_key, {"reference_text": "Answer"})
        response = self.client.post(
            reverse(
                "studio:item_action",
                args=[self.challenge.pk, "tasks", task.pk, "delete"],
            )
        )
        self.assertContains(response, "Add at least one task", status_code=400)
        self.assertEqual(self.challenge.tasks.count(), 1)
        self.client.post(
            reverse("studio:change_status", args=[self.challenge.pk]),
            {"status": "draft"},
        )
        self.assertEqual(self.challenge.tasks.count(), 1)
        self.assertEqual(
            self.client.post(
                reverse(
                    "studio:item_action",
                    args=[self.challenge.pk, "tasks", task.pk, "delete"],
                )
            ).status_code,
            302,
        )
        self.assertEqual(self.challenge.tasks.count(), 0)

    def test_cross_challenge_blocks_and_wrong_owner_are_rejected(self):
        other = save_draft(working_title="Other", rough_notes="")
        block = save_block(challenge=other, phase="prompt", text="Private")
        self.assertEqual(
            self.client.get(
                reverse("studio:edit_block", args=[self.challenge.pk, block.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse(
                    "studio:item_action",
                    args=[self.challenge.pk, "blocks", block.pk, "delete"],
                )
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("studio:new_block", args=[self.challenge.pk]),
                {"phase": "prompt", "task": "invalid"},
            ).status_code,
            404,
        )
        with self.assertRaises(ValidationError):
            save_block(
                challenge=self.challenge,
                task=save_task(challenge=other, max_points=1, reference_answer="A"),
                phase="prompt",
                text="Wrong",
            )
        with self.assertRaises(ValidationError):
            ContentBlock(
                challenge=self.challenge,
                task=other.tasks.first(),
                order=1,
                phase="prompt",
                text="Both",
            ).full_clean()

    def test_validation_of_category_points_key_and_escaped_preview(self):
        no_category = save_draft(working_title="No category", rough_notes="")
        task = save_task(challenge=no_category, max_points=1, reference_answer="Fact")
        save_block(challenge=no_category, phase="prompt", text="<script>bad()</script>")
        with self.assertRaisesMessage(ValidationError, "Select a category"):
            set_status(no_category, Challenge.Status.READY)
        task.max_points = 0
        task.evaluation_key = {"reference_text": " "}
        task.save()
        with self.assertRaisesMessage(ValidationError, "points must be greater"):
            set_status(no_category, Challenge.Status.READY)
        response = self.client.get(
            reverse("studio:preview", args=[no_category.pk, "question"])
        )
        self.assertContains(response, "&lt;script&gt;bad()&lt;/script&gt;")
        self.assertNotContains(response, "<script>bad()</script>")

    def test_database_rejects_duplicate_block_order(self):
        save_block(challenge=self.challenge, phase="prompt", text="One")
        with self.assertRaises(IntegrityError), transaction.atomic():
            ContentBlock.objects.create(
                challenge=self.challenge, phase="prompt", order=1, text="Two"
            )

    def test_preview_unknown_mode_returns_404(self):
        self.assertEqual(
            self.client.get(
                reverse("studio:preview", args=[self.challenge.pk, "other"])
            ).status_code,
            404,
        )
