from django import forms

from .models import Category, Challenge, Game, ResponseItem, Task


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
    format = forms.ChoiceField(
        choices=Task.Format.choices, required=False, initial=Task.Format.FREE_TEXT
    )
    max_points = forms.IntegerField(min_value=1, initial=1, label="Maximum points")
    correct_item = forms.ModelChoiceField(
        queryset=ResponseItem.objects.none(),
        required=False,
        label="Correct option",
        help_text="Choose after adding options; the option ID stays correct when you reorder them.",
    )
    reference_answer = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        help_text="Answer used for later manual review. Required when marking Ready.",
    )

    def __init__(self, *args, task=None, **kwargs):
        super().__init__(*args, **kwargs)
        if task and task.response_pool_id:
            self.fields["correct_item"].queryset = task.response_pool.items.all()


class ItemForm(forms.Form):
    prompt_text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}), label="Option shown to players"
    )
    reveal_text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}),
        required=False,
        label="Additional reveal (optional)",
    )


class BlockForm(forms.Form):
    text = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), label="Text")


class GameForm(forms.ModelForm):
    class Meta:
        model = Game
        fields = ["name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class RoundForm(forms.Form):
    name = forms.CharField(max_length=255, label="Round name")


class PlacementForm(forms.Form):
    challenge = forms.ModelChoiceField(queryset=Challenge.objects.none())

    def __init__(self, *args, challenges=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["challenge"].queryset = (
            challenges
            if challenges is not None
            else Challenge.objects.filter(status=Challenge.Status.READY)
        )


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]
