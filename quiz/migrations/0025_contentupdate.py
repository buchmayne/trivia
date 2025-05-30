# Generated by Django 4.2.18 on 2025-02-17 00:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0024_playerstats_gameresult"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContentUpdate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("filename", models.CharField(max_length=255, unique=True)),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                ("processed", models.BooleanField(default=False)),
                ("processed_at", models.DateTimeField(null=True)),
                ("checksum", models.CharField(max_length=64)),
                ("question_count", models.IntegerField()),
            ],
            options={
                "ordering": ["timestamp"],
            },
        ),
    ]
