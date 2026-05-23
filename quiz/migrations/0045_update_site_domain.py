# Generated migration to update Site domain from localhost to production

from django.db import migrations


def update_site_domain(apps, schema_editor):
    """
    Ensure Site with pk=1 exists with the production domain.

    Handles multiple scenarios:
    - Site pk=1 exists with old domain: update it
    - Site pk=1 doesn't exist but domain exists elsewhere: delete and recreate
    - No Site exists: create one
    """
    Site = apps.get_model("sites", "Site")

    # First, check if Site pk=1 exists
    try:
        site = Site.objects.get(pk=1)
        # Update if needed
        if site.domain != "thirdwavetrivia.com":
            site.domain = "thirdwavetrivia.com"
            site.name = "Third Wave Trivia"
            site.save()
        return
    except Site.DoesNotExist:
        pass

    # Site pk=1 doesn't exist - check if domain exists with different pk
    existing = Site.objects.filter(domain="thirdwavetrivia.com").first()
    if existing:
        # Delete it so we can create with pk=1
        existing.delete()

    # Create Site with pk=1
    Site.objects.create(
        pk=1,
        domain="thirdwavetrivia.com",
        name="Third Wave Trivia",
    )


def reverse_site_domain(apps, schema_editor):
    """Reverse migration - restore localhost for development"""
    # No-op: we don't want to break production if someone reverses migrations
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0044_hash_existing_passwords"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.RunPython(update_site_domain, reverse_site_domain),
    ]
