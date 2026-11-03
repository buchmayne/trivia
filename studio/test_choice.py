from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Category, Challenge, ContentBlock, ResponseItem, Task
from .projections import challenge_preview, game_preview
from .services import (
    add_placement,
    add_round,
    delete_content,
    move_content,
    save_block,
    save_draft,
    save_game,
    save_response_item,
    save_task,
    set_status,
)


@override_settings(ROOT_URLCONF="studio.test_urls", DEBUG=True, ENABLE_V2_STUDIO=True)
class ChooseOneTests(TestCase):
    def setUp(self):
        author = User.objects.create_user(username="author", password="testpass123")
        author.profile.is_game_admin = True
        author.profile.save()
        self.client.force_login(author)
        self.category = Category.objects.create(name="Language")
        self.challenge = save_draft(
            working_title="Origins of idioms", rough_notes="", category=self.category
        )
        save_block(
            challenge=self.challenge,
            phase="prompt",
            text="Identify the correct origin for each idiom. (1 point each)",
        )

    def add_choice_task(self, idiom, option_texts):
        response = self.client.post(
            reverse("studio:new_task", args=[self.challenge.pk]),
            {"format": "single_choice", "max_points": 1},
        )
        task = self.challenge.tasks.order_by("order").last()
        self.assertRedirects(
            response, reverse("studio:edit_task", args=[self.challenge.pk, task.pk])
        )
        self.assertEqual(task.response_pool.task_id, task.pk)
        save_block(challenge=self.challenge, task=task, phase="prompt", text=idiom)
        for index, text in enumerate(option_texts):
            option = self.client.post(
                reverse("studio:new_option", args=[self.challenge.pk, task.pk]),
                {
                    "prompt_text": text,
                    "reveal_text": "Background details" if index == 2 else "",
                },
            )
            self.assertRedirects(
                option, reverse("studio:edit_task", args=[self.challenge.pk, task.pk])
            )
        items = list(task.response_pool.items.all())
        response = self.client.post(
            reverse("studio:edit_task", args=[self.challenge.pk, task.pk]),
            {"format": "single_choice", "max_points": 1, "correct_item": items[2].pk},
        )
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.evaluation_key, {"correct_item_id": items[2].pk})
        return task, items

    def test_idiom_challenge_has_local_options_separate_keys_and_reveal(self):
        first, first_items = self.add_choice_task(
            "Selling like hot cakes",
            ["Gold Rush cooks", "Fairs and socials", "London vendors"],
        )
        second, second_items = self.add_choice_task(
            "In the limelight",
            ["Fruit sellers", "Whitewashed stage", "Calcium oxide light"],
        )
        self.assertNotEqual(first.response_pool_id, second.response_pool_id)
        self.assertEqual(
            self.client.post(
                reverse("studio:change_status", args=[self.challenge.pk]),
                {"status": "ready"},
            ).status_code,
            302,
        )
        self.assertEqual(self.challenge.total_points, 2)
        question = challenge_preview(self.challenge)
        self.assertEqual(len(question["tasks"]), 2)
        self.assertEqual([len(task["options"]) for task in question["tasks"]], [3, 3])
        self.assertEqual(question["tasks"][0]["options"][0]["label"], "A")
        self.assertNotIn("correct_result", question["tasks"][0])
        self.assertNotIn("correct", question["tasks"][0]["options"][2])
        self.assertNotIn("reveal", question["tasks"][0]["options"][2])
        self.assertNotIn("Background details", str(question))
        html = self.client.get(
            reverse("studio:preview", args=[self.challenge.pk, "question"])
        )
        self.assertContains(html, "Gold Rush cooks")
        self.assertContains(html, "Calcium oxide light")
        self.assertNotContains(html, "Correct option")
        self.assertNotContains(html, "Background details")
        reveal = challenge_preview(self.challenge, reveal=True)
        self.assertEqual(reveal["tasks"][0]["correct_result"], "London vendors")
        self.assertEqual(reveal["tasks"][1]["correct_result"], "Calcium oxide light")
        self.assertTrue(reveal["tasks"][0]["options"][2]["correct"])
        self.assertFalse(reveal["tasks"][1]["options"][0]["correct"])
        self.assertContains(
            self.client.get(
                reverse("studio:preview", args=[self.challenge.pk, "reveal"])
            ),
            "Background details",
        )
        self.challenge.refresh_from_db()
        game = save_game(name="Idiom Game")
        round_ = add_round(game=game, name="First")
        add_placement(round_=round_, challenge=self.challenge)
        self.assertNotIn("correct_result", str(game_preview(game)))
        self.assertEqual(
            game_preview(game, reveal=True)["rounds"][0]["entries"][0]["challenge"][
                "total_points"
            ],
            2,
        )
        self.assertEqual(first_items[2].pool_id, first.response_pool_id)
        self.assertEqual(second_items[2].pool_id, second.response_pool_id)

    def test_reordering_option_changes_label_not_correct_identity(self):
        task, items = self.add_choice_task("Hot cakes", ["A", "B", "C"])
        set_status(self.challenge, Challenge.Status.READY)
        move_content(challenge=self.challenge, item=items[2], direction="up")
        task.refresh_from_db()
        self.assertEqual(task.evaluation_key, {"correct_item_id": items[2].pk})
        reveal = challenge_preview(self.challenge, reveal=True)["tasks"][0]["options"]
        self.assertEqual(
            [option["id"] for option in reveal], [items[0].pk, items[2].pk, items[1].pk]
        )
        self.assertEqual([option["label"] for option in reveal], ["A", "B", "C"])
        self.assertEqual(
            [option["label"] for option in reveal if option["correct"]], ["B"]
        )

    def test_foreign_or_missing_correct_option_rejected_and_ready_delete_rolled_back(
        self,
    ):
        first, items = self.add_choice_task("Hot cakes", ["A", "B", "C"])
        second, others = self.add_choice_task("Limelight", ["D", "E", "F"])
        invalid = self.client.post(
            reverse("studio:edit_task", args=[self.challenge.pk, first.pk]),
            {"format": "single_choice", "max_points": 1, "correct_item": others[0].pk},
        )
        self.assertContains(invalid, "Select a valid choice", status_code=400)
        with self.assertRaisesMessage(ValidationError, "belonging to this task"):
            save_task(
                challenge=self.challenge,
                task=first,
                format="single_choice",
                max_points=1,
                reference_answer="",
                correct_item=others[0],
            )
        first.refresh_from_db()
        self.assertEqual(first.evaluation_key, {"correct_item_id": items[2].pk})
        set_status(self.challenge, Challenge.Status.READY)
        correct_id = items[2].pk
        with self.assertRaisesMessage(ValidationError, "choose a correct option"):
            delete_content(challenge=self.challenge, item=items[2])
        self.assertTrue(ResponseItem.objects.filter(pk=correct_id).exists())
        set_status(self.challenge, Challenge.Status.DRAFT)
        delete_content(
            challenge=self.challenge, item=ResponseItem.objects.get(pk=correct_id)
        )
        with self.assertRaisesMessage(ValidationError, "choose a correct option"):
            set_status(self.challenge, Challenge.Status.READY)
        self.assertEqual(first.response_pool.items.count(), 2)

    def test_item_editor_and_item_scoped_blocks_enforce_ownership(self):
        task, items = self.add_choice_task("Hot cakes", ["A", "B", "C"])
        edit = self.client.post(
            reverse(
                "studio:edit_option", args=[self.challenge.pk, task.pk, items[0].pk]
            ),
            {"prompt_text": "New A", "reveal_text": "Extra fact"},
        )
        self.assertEqual(edit.status_code, 302)
        block = items[0].content_blocks.get(phase="prompt")
        self.assertEqual(block.text, "New A")
        extra = self.client.post(
            reverse("studio:new_block", args=[self.challenge.pk]),
            {"phase": "reveal", "item": items[0].pk, "text": "More context"},
        )
        self.assertEqual(extra.status_code, 302)
        self.assertEqual(items[0].content_blocks.filter(phase="reveal").count(), 2)
        other = save_draft(working_title="Other challenge", rough_notes="")
        self.assertEqual(
            self.client.get(
                reverse("studio:edit_block", args=[other.pk, block.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("studio:edit_option", args=[other.pk, task.pk, items[0].pk])
            ).status_code,
            404,
        )
        with self.assertRaises(ValidationError):
            ContentBlock(
                task=task, item=items[0], order=2, phase="reveal", text="Both"
            ).full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ResponseItem.objects.create(pool=task.response_pool, order=1)

    def test_choose_one_ready_needs_two_displayable_options_and_valid_key(self):
        task = save_task(
            challenge=self.challenge,
            max_points=1,
            reference_answer="",
            format="single_choice",
        )
        with self.assertRaisesMessage(ValidationError, "at least two options"):
            set_status(self.challenge, Challenge.Status.READY)
        first = save_response_item(task=task, prompt_text="A")
        second = save_response_item(task=task, prompt_text="B")
        with self.assertRaisesMessage(ValidationError, "choose a correct option"):
            set_status(self.challenge, Challenge.Status.READY)
        task.evaluation_key = {"correct_item_id": first.pk}
        task.save()
        set_status(self.challenge, Challenge.Status.READY)
        self.assertTrue(self.challenge.status == Challenge.Status.READY)
        task.response_pool.items.filter(pk=second.pk).delete()
        with self.assertRaisesMessage(ValidationError, "at least two options"):
            set_status(self.challenge, Challenge.Status.READY)

    def test_switching_format_reuses_local_pool_and_deleting_task_removes_items(self):
        task, items = self.add_choice_task("Hot cakes", ["A", "B", "C"])
        pool_id = task.response_pool_id
        save_task(
            challenge=self.challenge,
            task=task,
            format="free_text",
            max_points=1,
            reference_answer="Reference",
        )
        task.refresh_from_db()
        self.assertIsNone(task.response_pool_id)
        save_task(
            challenge=self.challenge,
            task=task,
            format="single_choice",
            max_points=1,
            reference_answer="",
            correct_item=items[1].pk,
        )
        task.refresh_from_db()
        self.assertEqual(task.response_pool_id, pool_id)
        self.assertEqual(task.evaluation_key, {"correct_item_id": items[1].pk})
        delete_content(challenge=self.challenge, item=task)
        self.assertFalse(ResponseItem.objects.filter(pool_id=pool_id).exists())

    def test_free_text_and_choose_one_tasks_can_share_a_challenge(self):
        free = save_task(
            challenge=self.challenge, max_points=2, reference_answer="Reference"
        )
        save_block(
            challenge=self.challenge, task=free, phase="reveal", text="Explanation"
        )
        choice, _ = self.add_choice_task("Which is right?", ["False", "Maybe", "True"])
        set_status(self.challenge, Challenge.Status.READY)
        preview = challenge_preview(self.challenge, reveal=True)
        self.assertEqual(
            [task["format"] for task in preview["tasks"]],
            ["free_text", "single_choice"],
        )
        self.assertEqual(preview["total_points"], 3)
        self.assertEqual(preview["tasks"][0]["correct_result"], "Reference")
        self.assertEqual(preview["tasks"][1]["correct_result"], "True")
        self.assertEqual(choice.response_pool.items.count(), 3)
