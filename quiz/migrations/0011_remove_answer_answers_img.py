# Generated by Django 4.2.17 on 2025-01-05 21:06

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0010_answer_answer_url_answer_answers_img"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="answer",
            name="answers_img",
        ),
    ]
