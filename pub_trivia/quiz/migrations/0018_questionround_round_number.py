# Generated by Django 4.2.17 on 2025-01-09 04:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0017_question_answer_bank"),
    ]

    operations = [
        migrations.AddField(
            model_name="questionround",
            name="round_number",
            field=models.IntegerField(default=1),
        ),
    ]
