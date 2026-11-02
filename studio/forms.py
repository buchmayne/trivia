from django import forms

from .models import Category, Challenge


class ChallengeDraftForm(forms.ModelForm):
    class Meta:
        model = Challenge
        fields = ["working_title", "rough_notes", "category"]
        labels = {
            "working_title": "Working title",
            "rough_notes": "Rough notes",
        }
        widgets = {
            "rough_notes": forms.Textarea(attrs={"rows": 4}),
        }


class TaskForm(forms.Form):
    max_points = forms.IntegerField(min_value=1, initial=1, label="Maximum points")
    reference_answer = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        help_text="Answer used for later manual review. Required when marking Ready.",
    )


class BlockForm(forms.Form):
    text = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), label="Text")


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]
