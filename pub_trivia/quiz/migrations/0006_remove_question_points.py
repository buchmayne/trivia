# Generated by Django 4.2.9 on 2024-11-20 03:48

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0005_remove_answer_image_answer_image_url"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="question",
            name="points",
        ),
    ]