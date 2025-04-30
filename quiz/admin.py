from django import forms
from django.contrib import admin
from django.utils.html import format_html
from .models import Game, Category, Question, Answer, QuestionType, QuestionRound
from .widgets import S3ImageUploadWidget


class QuestionAdminForm(forms.ModelForm):
    new_category_name = forms.CharField(
        required=False,
        help_text="Enter a new category name, or leave blank to select an existing category.",
    )

    class Meta:
        model = Question
        fields = "__all__"
        help_texts = {
            "question_image_url": "Enter only the S3 path (e.g., /2021/March/image.jpg). CloudFront domain will be added automatically.",
            "answer_image_url": "Enter only the S3 path (e.g., /2021/March/image.jpg). CloudFront domain will be added automatically.",
        }
        widgets = {
            "question_image": S3ImageUploadWidget(field_name="question_image"),
            "answer_image": S3ImageUploadWidget(field_name="answer_image"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Order categories alphabetically by name
        if "category" in self.fields:
            self.fields["category"].queryset = Category.objects.all().order_by("name")

        if not self.instance.pk:
            # Set a default placeholder
            self.fields["question_number"].widget.attrs["placeholder"] = "..."

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get("category")
        new_category_name = cleaned_data.get("new_category_name")

        # Ensure either an existing category or a new category name is provided
        if not category and not new_category_name:
            raise forms.ValidationError(
                "Please select an existing category or provide a new category name."
            )

        # Only apply for new questions and when game is selected
        if not self.instance.pk and "game" in cleaned_data and cleaned_data["game"]:
            # If question_number is not set by the user
            if not cleaned_data.get("question_number"):
                game = cleaned_data["game"]

                # Get all existing question numbers for this game
                existing_numbers = set(
                    Question.objects.filter(game=game).values_list(
                        "question_number", flat=True
                    )
                )

                # Find the first available number
                next_number = 1
                while next_number in existing_numbers:
                    next_number += 1

                # Set the next available number
                cleaned_data["question_number"] = next_number

                # Update the form field to show the value
                self.data = self.data.copy()  # Make mutable
                self.data["question_number"] = next_number

        return cleaned_data

    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Handle creating a new category if a name is provided
        new_category_name = self.cleaned_data.get("new_category_name")
        if new_category_name:
            category, created = Category.objects.get_or_create(name=new_category_name)
            instance.category = category

        # Add the game's reference to the category
        if instance.category and instance.game:
            instance.category.games.add(instance.game)
        
        # Always save the instance to handle file fields properly
        instance.save()
        
        # Manual URL update after the instance is saved
        if instance.question_image:
            instance.question_image_url = instance.question_image.name
            # We need to save again for the URL update
            instance.save(update_fields=['question_image_url'])
        
        if instance.answer_image:
            instance.answer_image_url = instance.answer_image.name
            # Save again for this field if it wasn't already saved above
            instance.save(update_fields=['answer_image_url'])
        
        return instance

    class Media:
        js = ("js/question_admin.js", "js/category_defaults.js",)


class AnswerInlineForm(forms.ModelForm):
    class Meta:
        model = Answer
        fields = '__all__'
        widgets = {
            'question_image': S3ImageUploadWidget(field_name="question_image"),
            'answer_image': S3ImageUploadWidget(field_name="answer_image"),
        }
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Save the instance first to generate IDs, etc.
        if commit:
            instance.save()
            # After saving, update the URL fields to match the file fields
            if instance.question_image:
                instance.question_image_url = instance.question_image.name
                
            if instance.answer_image:
                instance.answer_image_url = instance.answer_image.name
                
            # Save again to update URLs
            instance.save()
        
        return instance


class AnswerInline(admin.TabularInline):
    model = Answer
    form = AnswerInlineForm
    extra = 4
    min_num = 1
    max_num = 10
    verbose_name = "Answer"
    verbose_name_plural = "Answers"
    fields = [
        "text",
        "points",
        "answer_text",
        "correct_rank",
        "question_image", 
        "explanation",
        "question_image_url", 
        "answer_image", 
        "answer_image_url", 
        "display_order",
    ]
    readonly_fields = ["image_preview"]

    def image_preview(self, obj):
        if obj.question_image_url:
            return format_html(
                f'<img src="{obj.question_image_url}" style="max-height: 100px;" />'
            )
        elif obj.answer_image_url:
            return format_html(
                f'<img src="{obj.answer_image_url}" style="max-height: 100px;" />'
            )
        return "No Image"

    image_preview.short_description = "Image Preview"
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        
        # Add initialization for the formset to handle ordering
        original_init = formset.__init__
        
        def __init__(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            for i, form in enumerate(self.forms):
                if not form.instance.pk and not form.initial.get("display_order"):
                    form.initial["display_order"] = i + 1
        
        formset.__init__ = __init__
        return formset


# Admin customization for Question
class QuestionAdmin(admin.ModelAdmin):
    form = QuestionAdminForm
    list_display = (
        "text",
        "game",
        "category",
        "question_type",
        "question_number",
        "game_round",
        "total_points",
        "answer_bank",
    )
    list_filter = ("game", "category", "question_type")
    search_fields = ["text"]

    inlines = [AnswerInline]  # Inline answers in the question form

    ordering = ["game", "question_number"]


# Admin customization for Game
class GameAdmin(admin.ModelAdmin):
    list_display = ("name", "is_password_protected", "created_at", "game_order")
    list_filter = ("is_password_protected",)
    fields = ("name", "description", "game_order", "is_password_protected", "password")
    ordering = ["-game_order"]


class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "get_games")
    list_filter = ("games",)
    search_fields = ["name"]

    # Custom method to display related games
    def get_games(self, obj):
        return ", ".join([game.name for game in obj.games.all()])

    get_games.short_description = "Games"


# Registering the models with custom admin interfaces
admin.site.register(Game, GameAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Question, QuestionAdmin)
admin.site.register(QuestionType)
admin.site.register(QuestionRound)
