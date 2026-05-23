# Generated migration to update Site domain from localhost to production

from django.db import migrations


def update_site_domain(apps, schema_editor):
    """Update the Site domain from localhost:8000 to thirdwavetrivia.com"""
    Site = apps.get_model("sites", "Site")
    try:
        site = Site.objects.get(pk=1)
        if site.domain in ("localhost:8000", "example.com", "localhost"):
            site.domain = "thirdwavetrivia.com"
            site.name = "Third Wave Trivia"
            site.save()
    except Site.DoesNotExist:
        # Create the site if it doesn't exist
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
