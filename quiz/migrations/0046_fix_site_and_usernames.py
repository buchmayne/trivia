# Data migration to fix Site pk=1 and empty usernames

import uuid
from django.db import migrations


def fix_site_and_usernames(apps, schema_editor):
    """
    Ensure Site pk=1 exists and fix any users with empty usernames.

    This migration is idempotent - safe to run multiple times.
    """
    Site = apps.get_model("sites", "Site")
    User = apps.get_model("auth", "User")

    # Fix Site: ensure pk=1 exists with correct domain
    site_exists = Site.objects.filter(pk=1).exists()
    if not site_exists:
        # Delete any existing site with our domain (wrong pk)
        Site.objects.filter(domain="thirdwavetrivia.com").delete()
        # Create with correct pk
        Site.objects.create(
            pk=1,
            domain="thirdwavetrivia.com",
            name="Third Wave Trivia",
        )

    # Fix users with empty usernames
    empty_username_users = User.objects.filter(username="")
    for user in empty_username_users:
        user.username = str(uuid.uuid4())[:30]
        user.save(update_fields=["username"])


def reverse_migration(apps, schema_editor):
    # No-op: we don't want to undo these fixes
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0045_update_site_domain"),
        ("sites", "0002_alter_domain_unique"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(fix_site_and_usernames, reverse_migration),
    ]
