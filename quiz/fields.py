from django import forms
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.conf import settings
from .image_processing import optimize_image
from .storage import S3MediaStorage
from .upload_helpers import get_upload_path


def validate_video_upload(file):
    """Reject non-video uploads and videos over MAX_VIDEO_UPLOAD_MB.

    This is a validate-only check: no transcoding. Properly optimized trivia
    clips are a few MB, so the cap only ever catches raw un-optimized uploads.
    """
    if file is None:
        return

    max_mb = int(getattr(settings, "MAX_VIDEO_UPLOAD_MB", 100))
    try:
        size_mb = file.size / (1024 * 1024)
    except (OSError, AttributeError):
        size_mb = None
    if size_mb is not None and size_mb > max_mb:
        raise ValidationError(
            f"Video is {size_mb:.0f} MB, over the {max_mb} MB limit. Optimize "
            "locally before uploading (e.g. ffmpeg: -c:v libx264 -crf 21, "
            "cap at 1080p, -movflags +faststart)."
        )

    # UploadedFile carries content_type on itself; FieldFile wraps that upload.
    underlying = getattr(file, "file", None)
    content_type = (
        getattr(file, "content_type", None)
        or getattr(underlying, "content_type", "")
        or ""
    ).lower()
    if content_type and not (
        content_type.startswith("video/") or content_type == "application/octet-stream"
    ):
        raise ValidationError(
            f"Expected a video file, got content type '{content_type}'."
        )


class ValidatedVideoFileField(forms.FileField):
    """Admin form field wrapper: shows oversize/non-video uploads as inline
    validation errors instead of letting them reach the storage layer."""

    def clean(self, data, initial=None):
        f = super().clean(data, initial)
        # Only validate freshly uploaded files; when no new file is uploaded,
        # ``f`` is the existing (committed) file, which needs no HTTP-content
        # checks and whose size would cost an S3 call.
        if f and f is not initial:
            validate_video_upload(f)
        return f


class CloudFrontURLField(models.CharField):
    """Field that stores relative S3 paths and prefixes CloudFront domain when accessed"""

    def __init__(self, *args, **kwargs):
        kwargs["max_length"] = kwargs.get("max_length", 255)
        super().__init__(*args, **kwargs)

    def pre_save(self, model_instance, add):
        # URL columns precede their upload columns on Question/Answer. Commit a
        # new upload before Django serializes this URL, otherwise the DB can
        # retain the old URL even though the file field saved a new object.
        if self.name.endswith("_url"):
            upload_name = self.name[:-4]
            upload = getattr(model_instance, upload_name, None)
            if upload and getattr(upload, "_committed", True) is False:
                upload.field.pre_save(model_instance, add)
        return super().pre_save(model_instance, add)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return self.get_full_url(value)

    def to_python(self, value):
        if isinstance(value, str) and value.startswith(settings.AWS_CLOUDFRONT_DOMAIN):
            # Strip the CloudFront domain if it's present
            return value.replace(settings.AWS_CLOUDFRONT_DOMAIN, "")
        return value

    def get_prep_value(self, value):
        if value is None:
            return None
        # Store just the path part
        if value.startswith(settings.AWS_CLOUDFRONT_DOMAIN):
            return value.replace(settings.AWS_CLOUDFRONT_DOMAIN, "")
        return value

    @staticmethod
    def get_full_url(path):
        if not path:
            return path
        if path.startswith(settings.AWS_CLOUDFRONT_DOMAIN):
            return path
        return f"{settings.AWS_CLOUDFRONT_DOMAIN}/{path.lstrip('/')}"


class S3ImageField(models.FileField):
    """A custom field that uploads to S3 and stores the path in CloudFrontURLField"""

    def __init__(self, *args, **kwargs):
        kwargs["storage"] = S3MediaStorage()
        if "upload_to" in kwargs:
            del kwargs["upload_to"]
        super().__init__(*args, **kwargs)

    def generate_filename(self, instance, filename):
        """
        Get the path from get_upload_path and modify it to avoid Django's security check
        """
        full_path = get_upload_path(instance, filename)
        # Remove leading slash for Django's security check but preserve path structure
        if full_path.startswith("/"):
            return full_path[1:]
        return full_path

    def pre_save(self, model_instance, add):
        """
        Optimize uncommitted uploads to WebP, then update the corresponding
        URL field with the full path.

        Django's FileField.pre_save commits uncommitted files to storage; by
        processing first and committing here, super().pre_save() sees the file
        already committed and does not upload again.
        """
        file = getattr(model_instance, self.attname)
        if file and not file._committed and file.name:
            content, optimized_name = optimize_image(file.read(), file.name)
            # Commits to storage (sets _committed and file.name), uploading
            # the optimized bytes under the .webp name — or the original bytes
            # and name if optimization passed through.
            file.save(optimized_name, ContentFile(content), save=False)

        file = super().pre_save(model_instance, add)
        if file and file.name:
            # Get the field name (e.g., 'question_image' or 'answer_image')
            field_name = self.name
            # Find the corresponding URL field (e.g., 'question_image_url' or 'answer_image_url')
            url_field_name = f"{field_name}_url"
            if hasattr(model_instance, url_field_name):
                # Set the URL field to match the file path
                setattr(model_instance, url_field_name, file.name)
        return file


class S3VideoField(models.FileField):
    """A custom field that uploads videos to S3 and stores the path in CloudFrontURLField"""

    def __init__(self, *args, **kwargs):
        kwargs["storage"] = S3MediaStorage()
        if "upload_to" in kwargs:
            del kwargs["upload_to"]
        super().__init__(*args, **kwargs)

    def generate_filename(self, instance, filename):
        """
        Get the path from get_upload_path and modify it to avoid Django's security check
        """
        full_path = get_upload_path(instance, filename)
        # Remove leading slash for Django's security check but preserve path structure
        if full_path.startswith("/"):
            return full_path[1:]
        return full_path

    def formfield(self, **kwargs):
        # Validate videos inline in the admin form (inline errors, no latency).
        kwargs.setdefault("form_class", ValidatedVideoFileField)
        return super().formfield(**kwargs)

    def pre_save(self, model_instance, add):
        """
        Reject invalid video uploads, then update the corresponding URL field
        with the full path.
        """
        file = getattr(model_instance, self.attname)
        if file and not file._committed:
            validate_video_upload(file)

        file = super().pre_save(model_instance, add)
        if file and file.name:
            # Get the field name (e.g., 'question_video' or 'answer_video')
            field_name = self.name
            # Find the corresponding URL field (e.g., 'question_video_url' or 'answer_video_url')
            url_field_name = f"{field_name}_url"
            if hasattr(model_instance, url_field_name):
                # Set the URL field to match the file path
                setattr(model_instance, url_field_name, file.name)
        return file
