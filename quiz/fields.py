from django.db import models
from django.conf import settings

class CloudFrontURLField(models.CharField):
    """Field that stores relative S3 paths and prefixes CloudFront domain when accessed"""
    
    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = kwargs.get('max_length', 255)
        super().__init__(*args, **kwargs)
    
    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return self.get_full_url(value)
    
    def to_python(self, value):
        if isinstance(value, str) and value.startswith(settings.AWS_CLOUDFRONT_DOMAIN):
            # Strip the CloudFront domain if it's present
            return value.replace(settings.AWS_CLOUDFRONT_DOMAIN, '')
        return value
    
    def get_prep_value(self, value):
        if value is None:
            return None
        # Store just the path part
        if value.startswith(settings.AWS_CLOUDFRONT_DOMAIN):
            return value.replace(settings.AWS_CLOUDFRONT_DOMAIN, '')
        return value
    
    @staticmethod
    def get_full_url(path):
        if not path:
            return path
        if path.startswith(settings.AWS_CLOUDFRONT_DOMAIN):
            return path
        return f"{settings.AWS_CLOUDFRONT_DOMAIN}{path}"