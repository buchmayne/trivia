from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Category, Challenge
from .services import save_draft


@override_settings(ROOT_URLCONF="studio.test_urls", DEBUG=True, ENABLE_V2_STUDIO=True)
class StudioInboxTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@example.com", password="testpass123"
        )
        self.author.profile.is_game_admin = True
        self.author.profile.save()
        self.client.force_login(self.author)

    def test_title_only_and_notes_only_drafts_are_saved(self):
        response = self.client.post(
            reverse("studio:capture"), {"working_title": "Hot cakes", "rough_notes": ""}
        )
        self.assertEqual(response.status_code, 302)
        titled = Challenge.objects.get(working_title="Hot cakes")
        self.assertEqual(response.url, reverse("studio:edit", args=[titled.pk]))
        notes_response = self.client.post(
            reverse("studio:capture"),
            {"working_title": "", "rough_notes": "  An idea for later  "},
        )
        self.assertEqual(notes_response.status_code, 302)
        self.assertEqual(Challenge.objects.count(), 2)
        self.assertEqual(titled.status, Challenge.Status.DRAFT)
        self.assertEqual(
            Challenge.objects.get(working_title="").rough_notes, "An idea for later"
        )

    def test_empty_draft_is_rejected_with_original_fields(self):
        response = self.client.post(
            reverse("studio:capture"), {"working_title": "  ", "rough_notes": " "}
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response, "Enter a working title or rough notes", status_code=400
        )
        self.assertEqual(Challenge.objects.count(), 0)

    def test_edit_and_filter_library_by_status_category_and_text(self):
        language = Category.objects.create(name="Language")
        other = Category.objects.create(name="History")
        challenge = save_draft(
            working_title="Hot cakes", rough_notes="Old phrase", category=language
        )
        save_draft(working_title="Archaeology", rough_notes="Stone", category=other)
        response = self.client.post(
            reverse("studio:edit", args=[challenge.pk]),
            {
                "working_title": "New title",
                "rough_notes": "Edited idea",
                "category": language.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Challenge.objects.get(pk=challenge.pk).working_title, "New title"
        )
        response = self.client.get(
            reverse("studio:library"),
            {"status": "draft", "category": language.pk, "q": "edited"},
        )
        self.assertContains(response, "New title")
        self.assertNotContains(response, "Archaeology")
        self.assertContains(
            self.client.get(reverse("studio:library"), {"q": "stone"}), "Archaeology"
        )
        self.assertEqual(
            self.client.get(reverse("studio:library"), {"category": "bad"}).status_code,
            200,
        )

    def test_add_category_and_reject_duplicate(self):
        response = self.client.post(
            reverse("studio:add_category"), {"name": "Language"}
        )
        self.assertRedirects(response, reverse("studio:library"))
        response = self.client.post(
            reverse("studio:add_category"), {"name": "Language"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Category.objects.count(), 1)

    def test_model_rejects_blank_title_and_notes_outside_form(self):
        with self.assertRaises(ValidationError):
            save_draft(working_title="  ", rough_notes="  ")
        self.assertEqual(Challenge.objects.count(), 0)

    def test_unauthenticated_and_non_author_are_denied(self):
        self.client.logout()
        response = self.client.get(reverse("studio:library"))
        self.assertRedirects(
            response, "/accounts/login/?next=/studio/", fetch_redirect_response=False
        )
        visitor = User.objects.create_user(username="visitor", password="testpass123")
        self.client.force_login(visitor)
        self.assertEqual(self.client.get(reverse("studio:library")).status_code, 403)
        self.assertEqual(
            self.client.post(
                reverse("studio:capture"), {"working_title": "No"}
            ).status_code,
            403,
        )
        self.assertEqual(Challenge.objects.count(), 0)

    def test_staff_can_use_studio_and_csrf_is_enforced(self):
        staff = User.objects.create_user(
            username="staff", password="testpass123", is_staff=True
        )
        client = Client(enforce_csrf_checks=True)
        client.force_login(staff)
        self.assertEqual(client.get(reverse("studio:library")).status_code, 200)
        self.assertEqual(
            client.post(
                reverse("studio:capture"), {"working_title": "Idea"}
            ).status_code,
            403,
        )
        self.assertEqual(Challenge.objects.count(), 0)
        token = client.cookies["csrftoken"].value
        self.assertEqual(
            client.post(
                reverse("studio:capture"),
                {"working_title": "Idea", "csrfmiddlewaretoken": token},
            ).status_code,
            302,
        )

    @override_settings(DEBUG=False)
    def test_studio_is_hidden_without_debug(self):
        self.assertEqual(self.client.get(reverse("studio:library")).status_code, 404)
        self.assertEqual(
            self.client.post(
                reverse("studio:capture"), {"working_title": "No"}
            ).status_code,
            404,
        )

    @override_settings(ENABLE_V2_STUDIO=False)
    def test_studio_is_hidden_without_opt_in(self):
        self.assertEqual(self.client.get(reverse("studio:library")).status_code, 404)
        self.assertEqual(Challenge.objects.count(), 0)


@override_settings(DEBUG=False, ENABLE_V2_STUDIO=False, ROOT_URLCONF="pub_trivia.urls")
class RootStudioRouteTests(TestCase):
    def test_studio_path_is_not_mounted_by_default(self):
        self.assertEqual(self.client.get("/studio/").status_code, 404)
