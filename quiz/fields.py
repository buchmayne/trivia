from django.db import models
from django.conf import settings
from .storage import S3MediaStorage
from .upload_helpers import get_upload_path


class CloudFrontURLField(models.CharField):
    """Field that stores relative S3 paths and prefixes CloudFront domain when accessed"""

    def __init__(self, *args, **kwargs):
        kwargs["max_length"] = kwargs.get("max_length", 255)
        super().__init__(*args, **kwargs)

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
        if full_path.startswith('/'):
            return full_path[1:]
        return full_path
    
    def pre_save(self, model_instance, add):
        """
        Before saving, update the corresponding URL field with the full path
        """
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