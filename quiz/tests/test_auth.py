"""
Tests for user authentication functionality.
Tests for email verification, protected views, and session hosting.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from allauth.account.models import EmailAddress

from quiz.models import Game, GameSession, UserProfile


class UserProfileSignalTests(TestCase):
    """Tests for UserProfile auto-creation signal."""

    def test_profile_created_on_user_creation(self):
        """UserProfile is automatically created when User is created."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.assertTrue(hasattr(user, "profile"))
        self.assertIsInstance(user.profile, UserProfile)

    def test_profile_is_game_admin_default_false(self):
        """New users are not game admins by default."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.assertFalse(user.profile.is_game_admin)


class GalleryViewAuthTests(TestCase):
    """Tests for gallery view authentication requirements."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.game = Game.objects.create(name="Test Game", is_public=True)

    def test_gallery_requires_login(self):
        """Gallery view redirects to login when not authenticated."""
        response = self.client.get(reverse("quiz:gallery"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_gallery_accessible_when_logged_in(self):
        """Gallery view is accessible when authenticated."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("quiz:gallery"))
        self.assertEqual(response.status_code, 200)

    def test_game_overview_requires_login(self):
        """Game overview view redirects to login when not authenticated."""
        response = self.client.get(
            reverse("quiz:game_overview", kwargs={"game_id": self.game.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_analytics_requires_login(self):
        """Analytics view redirects to login when not authenticated."""
        response = self.client.get(reverse("quiz:analytics"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)


class SessionHostAuthTests(TestCase):
    """Tests for session hosting authentication requirements."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.game = Game.objects.create(name="Test Game", is_public=True)

    def test_session_host_requires_login(self):
        """Session host page redirects to login when not authenticated."""
        response = self.client.get(reverse("quiz:session_host"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_session_host_requires_verified_email(self):
        """Session host page redirects to email page when email not verified."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("quiz:session_host"))
        # Should redirect to email management page
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/email/", response.url)

    def test_session_host_accessible_with_verified_email(self):
        """Session host page is accessible with verified email."""
        self.client.login(username="testuser", password="testpass123")
        # Create verified email
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=True, primary=True
        )
        response = self.client.get(reverse("quiz:session_host"))
        self.assertEqual(response.status_code, 200)


class SessionJoinPublicAccessTests(TestCase):
    """Tests that session joining remains public (no auth required)."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=True, primary=True
        )
        self.game = Game.objects.create(name="Test Game", is_public=True)

    def test_session_join_page_public(self):
        """Session join page is accessible without login."""
        response = self.client.get(reverse("quiz:session_join"))
        self.assertEqual(response.status_code, 200)

    def test_session_landing_public(self):
        """Session landing page is accessible without login."""
        response = self.client.get(reverse("quiz:session_landing"))
        self.assertEqual(response.status_code, 200)

    def test_session_play_page_public(self):
        """Session play page is accessible without login (for team players)."""
        session = GameSession.objects.create(
            game=self.game, admin_name="Test Admin", host_user=self.user
        )
        response = self.client.get(
            reverse("quiz:session_play", kwargs={"code": session.code})
        )
        self.assertEqual(response.status_code, 200)


class CreateSessionAPIAuthTests(TestCase):
    """Tests for create_session API authentication requirements."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.game = Game.objects.create(name="Test Game", is_public=True)

    def test_create_session_requires_login(self):
        """Create session API returns 401 when not authenticated."""
        response = self.client.post(
            reverse("quiz:session_create"),
            data={"game_id": self.game.id, "admin_name": "Test Admin"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Authentication required", response.json()["error"])

    def test_create_session_requires_verified_email(self):
        """Create session API returns 403 when email not verified."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            reverse("quiz:session_create"),
            data={"game_id": self.game.id, "admin_name": "Test Admin"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("verify your email", response.json()["error"])

    def test_create_session_success_with_verified_email(self):
        """Create session API succeeds with verified email."""
        self.client.login(username="testuser", password="testpass123")
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=True, primary=True
        )
        response = self.client.post(
            reverse("quiz:session_create"),
            data={"game_id": self.game.id, "admin_name": "Test Admin"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("code", response.json())
        self.assertIn("admin_token", response.json())

    def test_create_session_sets_host_user(self):
        """Create session API sets the host_user field."""
        self.client.login(username="testuser", password="testpass123")
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=True, primary=True
        )
        response = self.client.post(
            reverse("quiz:session_create"),
            data={"game_id": self.game.id, "admin_name": "Test Admin"},
            content_type="application/json",
        )
        session = GameSession.objects.get(code=response.json()["code"])
        self.assertEqual(session.host_user, self.user)


class JoinSessionAPIPublicAccessTests(TestCase):
    """Tests that session join API remains public."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=True, primary=True
        )
        self.game = Game.objects.create(name="Test Game", is_public=True)
        self.session = GameSession.objects.create(
            game=self.game, admin_name="Test Admin", host_user=self.user
        )

    def test_join_session_public(self):
        """Join session API works without authentication."""
        response = self.client.post(
            reverse("quiz:session_join", kwargs={"code": self.session.code}),
            data={"team_name": "Test Team"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("team_token", response.json())

    def test_get_session_state_public(self):
        """Get session state API works without authentication."""
        response = self.client.get(
            reverse("quiz:session_state", kwargs={"code": self.session.code})
        )
        self.assertEqual(response.status_code, 200)


class GameOwnershipTests(TestCase):
    """Tests for game ownership and permissions."""

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username="admin", email="admin@example.com", password="adminpass123"
        )
        self.admin_user.profile.is_game_admin = True
        self.admin_user.profile.save()
        EmailAddress.objects.create(
            user=self.admin_user,
            email=self.admin_user.email,
            verified=True,
            primary=True,
        )

        self.regular_user = User.objects.create_user(
            username="regular", email="regular@example.com", password="regularpass123"
        )
        EmailAddress.objects.create(
            user=self.regular_user,
            email=self.regular_user.email,
            verified=True,
            primary=True,
        )

        self.public_game = Game.objects.create(
            name="Public Game", is_public=True, owner=self.admin_user
        )
        self.private_game = Game.objects.create(
            name="Private Game", is_public=False, owner=self.admin_user
        )

    def test_regular_user_can_host_public_game(self):
        """Regular user can create session for public game."""
        self.client.login(username="regular", password="regularpass123")
        response = self.client.post(
            reverse("quiz:session_create"),
            data={"game_id": self.public_game.id, "admin_name": "Test"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_regular_user_cannot_host_private_game(self):
        """Regular user cannot create session for private game they don't own."""
        self.client.login(username="regular", password="regularpass123")
        response = self.client.post(
            reverse("quiz:session_create"),
            data={"game_id": self.private_game.id, "admin_name": "Test"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("permission", response.json()["error"])

    def test_game_admin_can_host_private_game(self):
        """Game admin can create session for any game."""
        self.client.login(username="admin", password="adminpass123")
        response = self.client.post(
            reverse("quiz:session_create"),
            data={"game_id": self.private_game.id, "admin_name": "Test"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_owner_can_host_own_private_game(self):
        """Game owner can create session for their private game."""
        # Transfer ownership to regular user
        self.private_game.owner = self.regular_user
        self.private_game.save()

        self.client.login(username="regular", password="regularpass123")
        response = self.client.post(
            reverse("quiz:session_create"),
            data={"game_id": self.private_game.id, "admin_name": "Test"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)


class GameVisibilityTests(TestCase):
    """Tests for game visibility in host view."""

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username="admin", email="admin@example.com", password="adminpass123"
        )
        self.admin_user.profile.is_game_admin = True
        self.admin_user.profile.save()
        EmailAddress.objects.create(
            user=self.admin_user,
            email=self.admin_user.email,
            verified=True,
            primary=True,
        )

        self.regular_user = User.objects.create_user(
            username="regular", email="regular@example.com", password="regularpass123"
        )
        EmailAddress.objects.create(
            user=self.regular_user,
            email=self.regular_user.email,
            verified=True,
            primary=True,
        )

        self.public_game = Game.objects.create(
            name="Public Game", is_public=True, owner=self.admin_user
        )
        self.private_game = Game.objects.create(
            name="Private Game", is_public=False, owner=self.admin_user
        )

    def test_regular_user_sees_only_public_games(self):
        """Regular user only sees public games on host page."""
        self.client.login(username="regular", password="regularpass123")
        response = self.client.get(reverse("quiz:session_host"))
        self.assertContains(response, "Public Game")
        self.assertNotContains(response, "Private Game")

    def test_game_admin_sees_all_games(self):
        """Game admin sees all games on host page."""
        self.client.login(username="admin", password="adminpass123")
        response = self.client.get(reverse("quiz:session_host"))
        self.assertContains(response, "Public Game")
        self.assertContains(response, "Private Game")
