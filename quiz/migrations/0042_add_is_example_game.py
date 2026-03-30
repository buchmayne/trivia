from django.db import migrations, models


def set_example_games(apps, schema_editor):
    """Set January-2025 as an example game."""
    Game = apps.get_model("quiz", "Game")
    Game.objects.filter(name="January-2025").update(is_example_game=True)


def unset_example_games(apps, schema_editor):
    """Reverse: unset January-2025 as an example game."""
    Game = apps.get_model("quiz", "Game")
    Game.objects.filter(name="January-2025").update(is_example_game=False)


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0041_assign_games_to_admin"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="is_example_game",
            field=models.BooleanField(
                default=False,
                help_text="Example games can be hosted without authentication",
            ),
        ),
        migrations.RunPython(set_example_games, unset_example_games),
    ]
