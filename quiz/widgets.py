from django import forms
from django.utils.safestring import mark_safe
from django.conf import settings

class S3ImageUploadWidget(forms.FileInput):
    template_name = "admin/widgets/s3_file_input.html"

    def __init__(self, attrs=None, field_name=None):
        self.field_name = field_name
        super().__init__(attrs)
    
    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['field_name'] = self.field_name
        if value and hasattr(value, 'url'):
            context['widget']['current_path'] = value.url
        return context
