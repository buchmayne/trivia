from django import forms
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.utils.html import format_html
from .models import (
    Game,
    Category,
    Question,
    Answer,
    QuestionType,
    QuestionRound,
    GameSession,
    SessionTeam,
    TeamAnswer,
)
from .widgets import S3ImageUploadWidget, S3VideoUploadWidget


# Custom filter for alphabetically sorted categories
class AlphabeticalCategoryFilter(SimpleListFilter):
    title = "category"  # Display name in the admin sidebar
    parameter_name = "category"  # URL parameter name

    def lookups(self, request, model_admin):
        # Get all categories used in questions, ordered alphabetically
        categories = (
            Category.objects.filter(questions__isnull=False).distinct().order_by("name")
        )
        return [(cat.id, cat.name) for cat in categories]

    def queryset(self, request, queryset):
        # Filter the queryset based on the selected category
        if self.value():
            return queryset.filter(category__id=self.value())
        return queryset


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
            "question_video": S3VideoUploadWidget(field_name="question_video"),
            "answer_video": S3VideoUploadWidget(field_name="answer_video"),
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
            instance.save(update_fields=["question_image_url"])

        if instance.answer_image:
            instance.answer_image_url = instance.answer_image.name
            # Save again for this field if it wasn't already saved above
            instance.save(update_fields=["answer_image_url"])

        # Add video URL updates
        if instance.question_video:
            instance.question_video_url = instance.question_video.name
            instance.save(update_fields=["question_video_url"])

        if instance.answer_video:
            instance.answer_video_url = instance.answer_video.name
            instance.save(update_fields=["answer_video_url"])

        return instance

    class Media:
        js = (
            "js/question_admin.js",
            "js/category_defaults.js",
            "js/conditional_fields.js",
        )


class AnswerInlineForm(forms.ModelForm):
    class Meta:
        model = Answer
        fields = "__all__"
        widgets = {
            "question_image": S3ImageUploadWidget(field_name="question_image"),
            "answer_image": S3ImageUploadWidget(field_name="answer_image"),
            "question_video": S3VideoUploadWidget(field_name="question_video"),
            "answer_video": S3VideoUploadWidget(field_name="answer_video"),
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

            if instance.question_video:
                instance.question_video_url = instance.question_video.name

            if instance.answer_video:
                instance.answer_video_url = instance.answer_video.name

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
        "answer_image",
        "question_video",
        "answer_video",
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
    list_filter = ("game", AlphabeticalCategoryFilter, "question_type")
    search_fields = ["text"]

    inlines = [AnswerInline]  # Inline answers in the question form

    # Order by game_order (descending, most recent first), then question_number (descending)
    ordering = ["-game__game_order", "-question_number"]


# Admin customization for Game
class GameAdminForm(forms.ModelForm):
    class Meta:
        model = Game
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set a default placeholder for new games
        if not self.instance.pk:
            self.fields["game_order"].widget.attrs["placeholder"] = "..."

    class Media:
        js = ("js/game_admin.js",)


class GameAdmin(admin.ModelAdmin):
    form = GameAdminForm
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


class SessionTeamInline(admin.TabularInline):
    model = SessionTeam
    readonly_fields = ["joined_at"]  # removed 'last_seen' - doesn't exist
    extra = 0
    fields = [
        "team_name",
        "total_score",
        "current_question_score",
        "joined_at",
    ]  # removed 'is_connected'


class GameSessionAdmin(admin.ModelAdmin):
    list_display = [
        "session_code",
        "game",
        "host_name",
        "status",
        "current_question_number",
        "team_count",
        "created_at",
    ]
    list_filter = ["status", "game", "created_at"]
    readonly_fields = ["session_code", "created_at", "started_at", "completed_at"]
    search_fields = ["session_code", "host_name", "game__name"]
    inlines = [SessionTeamInline]

    def team_count(self, obj):
        return obj.teams.count()

    team_count.short_description = "Teams"


class SessionTeamAdmin(admin.ModelAdmin):
    list_display = [
        "team_name",
        "session",
        "total_score",
        "joined_at",
    ]  # removed 'is_connected'
    list_filter = ["session__game", "session__status"]  # removed 'is_connected'
    search_fields = ["team_name", "session__session_code"]


class TeamAnswerAdmin(admin.ModelAdmin):
    list_display = [
        "team",
        "question_number",
        "submitted_answer_preview",
        "points_awarded",
        "submitted_at",  # removed 'is_correct'
    ]
    list_filter = ["question__game", "submitted_at"]  # removed 'is_correct'
    search_fields = ["team__team_name", "submitted_answer"]

    def question_number(self, obj):
        return f"Q{obj.question.question_number}"

    question_number.short_description = "Question"

    def submitted_answer_preview(self, obj):
        return (
            obj.submitted_answer[:50] + "..."
            if len(obj.submitted_answer) > 50
            else obj.submitted_answer
        )

    submitted_answer_preview.short_description = "Answer"


# Registering the models with custom admin interfaces
admin.site.register(Game, GameAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Question, QuestionAdmin)
admin.site.register(QuestionType)
admin.site.register(QuestionRound)
admin.site.register(GameSession, GameSessionAdmin)
admin.site.register(SessionTeam, SessionTeamAdmin)
admin.site.register(TeamAnswer, TeamAnswerAdmin)
