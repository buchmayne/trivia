"""
Test utilities for quiz app tests.
Provides helper functions and mixins for authenticated tests.
"""

from django.contrib.auth.models import User
from allauth.account.models import EmailAddress
from rest_framework.test import APIClient


def create_verified_user(
    username="testuser", email="test@example.com", password="testpass123"
):
    """Create a user with a verified email address for testing."""
    user = User.objects.create_user(username=username, email=email, password=password)
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user


def get_authenticated_client(user=None):
    """Get a Django test client that's logged in as the given user."""
    from django.test import Client

    client = Client()
    if user is None:
        user = create_verified_user()
    client.login(username=user.username, password="testpass123")
    return client, user


def get_authenticated_api_client(user=None):
    """Get a DRF API client that's logged in as the given user."""
    client = APIClient()
    if user is None:
        user = create_verified_user()
    client.force_authenticate(user=user)
    return client, user


class AuthenticatedTestMixin:
    """Mixin that sets up an authenticated user and client for tests."""

    def setUp(self):
        super().setUp()
        self.user = create_verified_user()
        self.client.login(username="testuser", password="testpass123")


class AuthenticatedAPITestMixin:
    """Mixin that sets up an authenticated API client for tests."""

    def setUp(self):
        super().setUp()
        self.user = create_verified_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
