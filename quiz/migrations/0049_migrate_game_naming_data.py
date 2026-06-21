"""
Data migration to populate the new game naming fields from existing data.
"""

from datetime import date
from django.db import migrations

# Month name to number mapping
MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


def migrate_game_data(apps, schema_editor):
    Game = apps.get_model("quiz", "Game")

    # Get all games ordered by game_order (descending, so higher = newer/first),
    # then by created_at for any ties
    # Note: game_order values are typically ascending (1, 2, 3...) where higher = newer
    games = Game.objects.all().order_by("game_order", "created_at")

    next_number = 1
    for game in games:
        # Preserve original name as legacy_name for gallery
        game.legacy_name = game.name

        # Handle Future-Game specially
        if game.name == "Future-Game":
            game.is_draft = True
            game.game_number = None  # Drafts don't get numbers
            game.name = "Draft: Untitled"
        else:
            game.game_number = next_number
            next_number += 1

            # Parse original_date from "Month-Year" format
            if "-" in game.name:
                parts = game.name.split("-")
                if len(parts) == 2:
                    month_name, year_str = parts
                    if month_name in MONTHS:
                        try:
                            year = int(year_str)
                            game.original_date = date(year, MONTHS[month_name], 1)
                        except ValueError, TypeError:
                            pass  # Skip if year parsing fails

            # Mark existing games as played (they were all hosted previously)
            game.has_been_played = True

            # Update name to new format
            game.name = f"Game {game.game_number}"

        game.save()


def reverse_migration(apps, schema_editor):
    """Reverse the migration by restoring original names from legacy_name."""
    Game = apps.get_model("quiz", "Game")

    for game in Game.objects.all():
        if game.legacy_name:
            game.name = game.legacy_name
        game.game_number = None
        game.is_draft = False
        game.has_been_played = False
        game.original_date = None
        game.legacy_name = ""
        game.save()


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0048_add_game_naming_fields"),
    ]

    operations = [
        migrations.RunPython(migrate_game_data, reverse_migration),
    ]
