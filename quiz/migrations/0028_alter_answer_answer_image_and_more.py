# Generated by Django 4.2.18 on 2025-04-09 00:31

from django.db import migrations
import quiz.fields
import quiz.storage


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0027_delete_contentupdate_answer_answer_image_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="answer",
            name="answer_image",
            field=quiz.fields.S3ImageField(
                blank=True,
                null=True,
                storage=quiz.storage.S3MediaStorage(),
                upload_to="",
            ),
        ),
        migrations.AlterField(
            model_name="answer",
            name="question_image",
            field=quiz.fields.S3ImageField(
                blank=True,
                null=True,
                storage=quiz.storage.S3MediaStorage(),
                upload_to="",
            ),
        ),
        migrations.AlterField(
            model_name="question",
            name="answer_image",
            field=quiz.fields.S3ImageField(
                blank=True,
                null=True,
                storage=quiz.storage.S3MediaStorage(),
                upload_to="",
            ),
        ),
        migrations.AlterField(
            model_name="question",
            name="question_image",
            field=quiz.fields.S3ImageField(
                blank=True,
                null=True,
                storage=quiz.storage.S3MediaStorage(),
                upload_to="",
            ),
        ),
    ]
