from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Category, Challenge, Game, GameRound, Placement
from .projections import game_preview
from .services import (
    add_placement,
    add_round,
    move_game_item,
    remove_game_item,
    save_block,
    save_draft,
    save_game,
    save_task,
    set_status,
)


@override_settings(ROOT_URLCONF="studio.test_urls", DEBUG=True, ENABLE_V2_STUDIO=True)
class GameBuilderTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="author", password="testpass123")
        user.profile.is_game_admin = True
        user.profile.save()
        self.client.force_login(user)
        self.language = Category.objects.create(name="Language")
        self.history = Category.objects.create(name="History")
        self.challenge = self.make_ready("Hot cakes", self.language, "Fairground sales")

    def make_ready(self, title, category, answer):
        challenge = save_draft(working_title=title, rough_notes="", category=category)
        save_task(challenge=challenge, max_points=1, reference_answer=answer)
        save_block(challenge=challenge, phase="prompt", text=f"Origin of {title}?")
        set_status(challenge, Challenge.Status.READY)
        return challenge

    def test_game_creation_and_two_round_assembly_via_studio(self):
        response = self.client.post(
            reverse("studio:new_game"), {"name": "Game A", "description": "Fun"}
        )
        game = Game.objects.get(name="Game A")
        self.assertRedirects(response, reverse("studio:game_editor", args=[game.pk]))
        self.assertContains(self.client.get(reverse("studio:games")), "Game A")
        self.assertEqual(
            self.client.post(
                reverse("studio:game_add_round", args=[game.pk]), {"name": "First"}
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(
                reverse("studio:game_add_round", args=[game.pk]), {"name": "Final"}
            ).status_code,
            302,
        )
        rounds = list(game.rounds.all())
        self.assertEqual([round_.name for round_ in rounds], ["First", "Final"])
        self.assertEqual(
            self.client.post(
                reverse("studio:game_add_placement", args=[game.pk, rounds[1].pk]),
                {"challenge": self.challenge.pk},
            ).status_code,
            302,
        )
        outline = game_preview(game)
        self.assertEqual(
            [len(round_["entries"]) for round_ in outline["rounds"]], [0, 1]
        )
        self.assertEqual(outline["rounds"][1]["entries"][0]["number"], 1)
        self.assertEqual(outline["category_coverage"], [("Language", 1)])
        self.assertContains(
            self.client.get(reverse("studio:game_editor", args=[game.pk])),
            "Language: 1",
        )
        self.assertContains(
            self.client.get(reverse("studio:game_preview", args=[game.pk, "question"])),
            "Origin of Hot cakes?",
        )
        self.assertNotContains(
            self.client.get(reverse("studio:game_preview", args=[game.pk, "question"])),
            "Fairground sales",
        )
        self.assertContains(
            self.client.get(reverse("studio:game_preview", args=[game.pk, "reveal"])),
            "Fairground sales",
        )
        self.assertEqual(
            self.client.post(
                reverse("studio:game_editor", args=[game.pk]),
                {"name": "Revised", "description": "New"},
            ).status_code,
            302,
        )
        game.refresh_from_db()
        self.assertEqual(game.name, "Revised")

    def test_one_challenge_is_reused_and_edits_reach_both_games(self):
        first = save_game(name="A")
        second = save_game(name="B")
        one = add_round(game=first, name="First")
        add_round(game=second, name="First")
        two = add_round(game=second, name="Second")
        add_placement(round_=one, challenge=self.challenge)
        add_placement(round_=two, challenge=self.challenge)
        self.assertEqual(Challenge.objects.count(), 1)
        self.assertEqual(self.challenge.placements.count(), 2)
        save_draft(
            challenge=self.challenge,
            working_title="Improved hot cakes",
            rough_notes="",
            category=self.language,
        )
        for game in (first, second):
            response = self.client.get(
                reverse("studio:game_preview", args=[game.pk, "question"])
            )
            self.assertContains(response, "Improved hot cakes")
        self.assertEqual(game_preview(second)["rounds"][1]["entries"][0]["number"], 1)

    def test_ordering_after_move_remove_and_category_coverage(self):
        game = save_game(name="A")
        first = add_round(game=game, name="First")
        second = add_round(game=game, name="Second")
        other = self.make_ready("Limelight", self.history, "Lamp")
        one = add_placement(round_=first, challenge=self.challenge)
        two = add_placement(round_=first, challenge=other)
        three = add_placement(round_=second, challenge=self.challenge)
        move_game_item(game=game, item=two, direction="up")
        self.assertEqual(
            [
                entry["challenge"]["title"]
                for entry in game_preview(game)["rounds"][0]["entries"]
            ],
            ["Limelight", "Hot cakes"],
        )
        self.assertEqual(
            game_preview(game)["category_coverage"], [("History", 1), ("Language", 2)]
        )
        self.client.post(
            reverse(
                "studio:game_item_action",
                args=[game.pk, "placements", one.pk, "delete"],
            )
        )
        move_game_item(game=game, item=second, direction="up")
        outline = game_preview(game)
        self.assertEqual(
            [round_["name"] for round_ in outline["rounds"]], ["Second", "First"]
        )
        self.assertEqual(
            [
                entry["number"]
                for round_ in outline["rounds"]
                for entry in round_["entries"]
            ],
            [1, 2],
        )
        self.assertEqual(
            [
                entry["challenge"]["title"]
                for round_ in outline["rounds"]
                for entry in round_["entries"]
            ],
            ["Hot cakes", "Limelight"],
        )
        self.assertEqual(Placement.objects.get(pk=three.pk).round_id, second.pk)
        self.assertEqual(
            outline["category_coverage"], [("History", 1), ("Language", 1)]
        )

    def test_library_last_used_is_latest_placement_and_filters_by_category(self):
        game = save_game(name="A")
        round_ = add_round(game=game, name="First")
        old = add_placement(round_=round_, challenge=self.challenge)
        more_recent = add_placement(round_=round_, challenge=self.challenge)
        date = timezone.now() - timedelta(days=2)
        Placement.objects.filter(pk=old.pk).update(created_at=date - timedelta(days=1))
        Placement.objects.filter(pk=more_recent.pk).update(created_at=date)
        listing = self.client.get(
            reverse("studio:library"), {"category": self.language.pk}
        )
        row = listing.context["challenges"].get(pk=self.challenge.pk)
        self.assertEqual(row.last_used, date)
        self.assertContains(listing, "Last added to a game")
        self.assertEqual(listing.context["challenges"].count(), 1)
        filtered = self.client.get(
            reverse("studio:game_editor", args=[game.pk]), {"category": self.history.pk}
        )
        self.assertNotContains(
            filtered, '<option value="%s">Hot cakes' % self.challenge.pk, html=False
        )

    def test_invalid_initial_placement_draft_or_invalid_ready_does_not_save(self):
        game = save_game(name="A")
        round_ = add_round(game=game, name="First")
        draft = save_draft(working_title="Later", rough_notes="")
        response = self.client.post(
            reverse("studio:game_add_placement", args=[game.pk, round_.pk]),
            {"challenge": draft.pk},
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Select a valid choice", status_code=400)
        with self.assertRaisesMessage(ValidationError, "Only Ready"):
            add_placement(round_=round_, challenge=draft)
        self.challenge.tasks.update(evaluation_key={"reference_text": ""})
        with self.assertRaisesMessage(ValidationError, "enter a reference answer"):
            add_placement(round_=round_, challenge=self.challenge)
        self.assertEqual(round_.placements.count(), 0)

    def test_challenge_can_become_draft_after_placement_with_visible_warning(self):
        game = save_game(name="A")
        round_ = add_round(game=game, name="First")
        add_placement(round_=round_, challenge=self.challenge)
        set_status(self.challenge, Challenge.Status.DRAFT)
        response = self.client.get(
            reverse("studio:game_preview", args=[game.pk, "question"])
        )
        self.assertContains(response, "Incomplete draft")
        self.assertContains(response, "Origin of Hot cakes?")
        self.assertEqual(round_.placements.count(), 1)

    def test_cross_game_actions_and_invalid_inputs_do_not_change_other_game(self):
        game = save_game(name="A")
        other_game = save_game(name="B")
        round_ = add_round(game=other_game, name="Only B")
        placement = add_placement(round_=round_, challenge=self.challenge)
        self.assertEqual(
            self.client.post(
                reverse("studio:game_add_placement", args=[game.pk, round_.pk]),
                {"challenge": self.challenge.pk},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse(
                    "studio:game_item_action",
                    args=[game.pk, "placements", placement.pk, "delete"],
                )
            ).status_code,
            404,
        )
        with self.assertRaises(ValidationError):
            remove_game_item(game=game, item=round_)
        self.assertEqual(round_.placements.count(), 1)
        self.assertEqual(
            self.client.post(
                reverse("studio:game_add_round", args=[game.pk]), {"name": " "}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(reverse("studio:new_game"), {"name": "  "}).status_code,
            400,
        )

    def test_database_rejects_duplicate_round_and_placement_positions(self):
        game = save_game(name="A")
        round_ = add_round(game=game, name="First")
        with self.assertRaises(IntegrityError), transaction.atomic():
            GameRound.objects.create(game=game, name="Duplicate", order=round_.order)
        add_placement(round_=round_, challenge=self.challenge)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Placement.objects.create(round=round_, challenge=self.challenge, order=1)

    def test_games_require_authorization_and_are_hidden_when_disabled(self):
        game = save_game(name="A")
        self.client.logout()
        self.assertEqual(self.client.get(reverse("studio:games")).status_code, 302)
        visitor = User.objects.create_user(username="visitor", password="testpass123")
        self.client.force_login(visitor)
        self.assertEqual(
            self.client.get(
                reverse("studio:game_preview", args=[game.pk, "question"])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse("studio:new_game"), {"name": "No"}).status_code,
            403,
        )
        with override_settings(DEBUG=False):
            self.assertEqual(self.client.get(reverse("studio:games")).status_code, 404)
            self.assertEqual(
                self.client.post(
                    reverse("studio:new_game"), {"name": "No"}
                ).status_code,
                404,
            )
