# Generated by Django 4.2.18 on 2025-07-01 05:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0032_gamesession_sessionteam_teamanswer"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="max_teams",
            field=models.IntegerField(default=16),
        ),
    ]
