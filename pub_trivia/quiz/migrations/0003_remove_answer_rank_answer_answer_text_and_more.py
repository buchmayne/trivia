# Generated by Django 4.2.9 on 2024-11-11 20:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0002_answer_correct_rank_answer_display_order_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="answer",
            name="rank",
        ),
        migrations.AddField(
            model_name="answer",
            name="answer_text",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="answer",
            name="explanation",
            field=models.TextField(blank=True, null=True),
        ),
    ]