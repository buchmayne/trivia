"""Custom allauth adapter for email-only authentication."""

import uuid

from allauth.account.adapter import DefaultAccountAdapter


class EmailOnlyAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter that generates unique usernames for email-only auth.

    Since we use email-only authentication but Django's User model still
    requires a username field with a unique constraint, we generate a
    unique username based on UUID for each user.
    """

    def populate_username(self, request, user):
        """Generate a unique username from UUID."""
        user.username = str(uuid.uuid4())[:30]
