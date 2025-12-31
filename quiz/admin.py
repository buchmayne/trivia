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
    SessionRound,
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


# Registering the models with custom admin interfaces
admin.site.register(Game, GameAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Question, QuestionAdmin)
admin.site.register(QuestionType)
admin.site.register(QuestionRound)


# ============================================================================
# SESSION ADMIN CUSTOMIZATION
# ============================================================================


class SessionTeamInline(admin.TabularInline):
    """Inline display of teams within a game session"""

    model = SessionTeam
    extra = 0
    fields = (
        "name",
        "score",
        "joined_at",
        "joined_late",
        "last_seen",
    )
    readonly_fields = ("token", "joined_at", "last_seen")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        # Don't allow adding teams through admin (should use API)
        return False


class SessionRoundInline(admin.TabularInline):
    """Inline display of rounds within a game session"""

    model = SessionRound
    extra = 0
    fields = (
        "round",
        "status",
        "started_at",
        "locked_at",
        "scored_at",
    )
    readonly_fields = ("started_at", "locked_at", "scored_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        # Rounds are auto-created when session is created
        return False


class SessionStatusFilter(SimpleListFilter):
    """Custom filter for session status"""

    title = "session status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return GameSession.Status.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class GameSessionAdmin(admin.ModelAdmin):
    """Admin interface for GameSession"""

    list_display = (
        "code",
        "game",
        "admin_name",
        "status",
        "team_count",
        "created_at",
        "started_at",
    )
    list_filter = (SessionStatusFilter, "game", "created_at", "allow_late_joins")
    search_fields = ("code", "admin_name", "game__name")
    readonly_fields = (
        "code",
        "admin_token",
        "created_at",
        "started_at",
        "completed_at",
        "admin_last_seen",
        "display_admin_token",
    )
    fieldsets = (
        (
            "Session Info",
            {
                "fields": (
                    "code",
                    "game",
                    "admin_name",
                    "status",
                    "status_before_pause",
                )
            },
        ),
        (
            "Game State",
            {
                "fields": (
                    "current_round",
                    "current_question",
                )
            },
        ),
        (
            "Settings",
            {
                "fields": (
                    "max_teams",
                    "allow_late_joins",
                )
            },
        ),
        (
            "Security & Timestamps",
            {
                "fields": (
                    "display_admin_token",
                    "created_at",
                    "started_at",
                    "completed_at",
                    "admin_last_seen",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    inlines = [SessionTeamInline, SessionRoundInline]
    ordering = ["-created_at"]

    actions = ["end_session", "recalculate_team_scores"]

    def team_count(self, obj):
        """Display number of teams"""
        return obj.teams.count()

    team_count.short_description = "Teams"

    def display_admin_token(self, obj):
        """Display admin token with copy button"""
        if obj.admin_token:
            return format_html(
                '<input type="text" value="{}" readonly style="width: 300px;" '
                "onclick=\"this.select(); document.execCommand('copy');\" "
                'title="Click to copy" />',
                obj.admin_token,
            )
        return "-"

    display_admin_token.short_description = "Admin Token (click to copy)"

    def end_session(self, request, queryset):
        """Custom action to end selected sessions"""
        from django.utils import timezone

        count = 0
        for session in queryset:
            if session.status != GameSession.Status.COMPLETED:
                session.status = GameSession.Status.COMPLETED
                session.completed_at = timezone.now()
                session.save()
                count += 1

        self.message_user(request, f"{count} session(s) marked as completed.")

    end_session.short_description = "End selected sessions"

    def recalculate_team_scores(self, request, queryset):
        """Recalculate all team scores for selected sessions"""
        from django.db.models import Sum

        count = 0
        for session in queryset:
            for team in session.teams.all():
                team.score = (
                    team.answers.filter(points_awarded__isnull=False).aggregate(
                        total=Sum("points_awarded")
                    )["total"]
                    or 0
                )
                team.save()
                count += 1

        self.message_user(request, f"Recalculated scores for {count} team(s).")

    recalculate_team_scores.short_description = "Recalculate team scores"


class TeamAnswerInline(admin.TabularInline):
    """Inline display of answers within a team"""

    model = TeamAnswer
    extra = 0
    fields = (
        "question",
        "answer_text",
        "points_awarded",
        "is_locked",
        "submitted_at",
    )
    readonly_fields = ("submitted_at", "updated_at", "scored_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        # Don't allow adding answers through admin
        return False


class SessionTeamAdmin(admin.ModelAdmin):
    """Admin interface for SessionTeam"""

    list_display = (
        "name",
        "session_code",
        "score",
        "joined_at",
        "joined_late",
        "answer_count",
    )
    list_filter = ("joined_late", "session__game", "session__status")
    search_fields = ("name", "session__code", "session__game__name")
    readonly_fields = ("token", "joined_at", "last_seen", "display_token")
    fieldsets = (
        (
            "Team Info",
            {
                "fields": (
                    "session",
                    "name",
                    "score",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "joined_late",
                    "joined_at",
                    "last_seen",
                )
            },
        ),
        (
            "Security",
            {
                "fields": ("display_token",),
                "classes": ("collapse",),
            },
        ),
    )

    inlines = [TeamAnswerInline]
    ordering = ["-session__created_at", "-score"]

    def session_code(self, obj):
        """Display session code"""
        return obj.session.code

    session_code.short_description = "Session"
    session_code.admin_order_field = "session__code"

    def answer_count(self, obj):
        """Display number of answers submitted"""
        return obj.answers.count()

    answer_count.short_description = "Answers"

    def display_token(self, obj):
        """Display team token with copy button"""
        if obj.token:
            return format_html(
                '<input type="text" value="{}" readonly style="width: 300px;" '
                "onclick=\"this.select(); document.execCommand('copy');\" "
                'title="Click to copy" />',
                obj.token,
            )
        return "-"

    display_token.short_description = "Team Token (click to copy)"


class RoundStatusFilter(SimpleListFilter):
    """Custom filter for round status"""

    title = "round status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return SessionRound.Status.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class SessionRoundAdmin(admin.ModelAdmin):
    """Admin interface for SessionRound"""

    list_display = (
        "session_code",
        "round_name",
        "round_number",
        "status",
        "started_at",
        "scored_at",
    )
    list_filter = (RoundStatusFilter, "session__game")
    search_fields = ("session__code", "round__name")
    readonly_fields = ("started_at", "locked_at", "scored_at")
    fieldsets = (
        (
            "Round Info",
            {
                "fields": (
                    "session",
                    "round",
                    "status",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "started_at",
                    "locked_at",
                    "scored_at",
                )
            },
        ),
    )

    ordering = ["-session__created_at", "round__round_number"]

    def session_code(self, obj):
        """Display session code"""
        return obj.session.code

    session_code.short_description = "Session"
    session_code.admin_order_field = "session__code"

    def round_name(self, obj):
        """Display round name"""
        return obj.round.name

    round_name.short_description = "Round"
    round_name.admin_order_field = "round__name"

    def round_number(self, obj):
        """Display round number"""
        return obj.round.round_number

    round_number.short_description = "#"
    round_number.admin_order_field = "round__round_number"


class TeamAnswerAdmin(admin.ModelAdmin):
    """Admin interface for TeamAnswer"""

    list_display = (
        "team_name",
        "session_code",
        "question_number",
        "answer_preview",
        "points_awarded",
        "is_locked",
        "submitted_at",
    )
    list_filter = (
        "is_locked",
        "session_round__session__game",
        "session_round__status",
    )
    search_fields = (
        "team__name",
        "team__session__code",
        "question__text",
        "answer_text",
    )
    readonly_fields = ("submitted_at", "updated_at", "scored_at")
    fieldsets = (
        (
            "Answer Info",
            {
                "fields": (
                    "team",
                    "question",
                    "session_round",
                    "answer_text",
                )
            },
        ),
        (
            "Scoring",
            {
                "fields": (
                    "points_awarded",
                    "is_locked",
                    "scored_at",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "submitted_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["-submitted_at"]

    def team_name(self, obj):
        """Display team name"""
        return obj.team.name

    team_name.short_description = "Team"
    team_name.admin_order_field = "team__name"

    def session_code(self, obj):
        """Display session code"""
        return obj.team.session.code

    session_code.short_description = "Session"

    def question_number(self, obj):
        """Display question number"""
        return f"Q{obj.question.question_number}"

    question_number.short_description = "Question"
    question_number.admin_order_field = "question__question_number"

    def answer_preview(self, obj):
        """Display truncated answer text"""
        if obj.answer_text:
            return (
                obj.answer_text[:50] + "..."
                if len(obj.answer_text) > 50
                else obj.answer_text
            )
        return "(empty)"

    answer_preview.short_description = "Answer"


# Register session models
admin.site.register(GameSession, GameSessionAdmin)
admin.site.register(SessionTeam, SessionTeamAdmin)
admin.site.register(SessionRound, SessionRoundAdmin)
admin.site.register(TeamAnswer, TeamAnswerAdmin)
