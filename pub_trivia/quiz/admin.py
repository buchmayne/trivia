from django import forms
from django.contrib import admin
from django.utils.html import format_html
from .models import Game, Category, Question, Answer, QuestionType, QuestionRound

class QuestionAdminForm(forms.ModelForm):
    new_category_name = forms.CharField(
        required=False,
        help_text="Enter a new category name, or leave blank to select an existing category."
    )

    class Meta:
        model = Question
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        new_category_name = cleaned_data.get('new_category_name')

        # Ensure either an existing category or a new category name is provided
        if not category and not new_category_name:
            raise forms.ValidationError(
                "Please select an existing category or provide a new category name."
            )

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

        if commit:
            instance.save()

        return instance

# Inline to add multiple answers directly in the question form
class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4  # Set the default number of answer fields to display
    min_num = 1  # Require at least one answer
    max_num = 10  # Maximum number of answer options
    verbose_name = "Answer"
    verbose_name_plural = "Answers"
    fields = ['text', 'question_image_url', 'display_order', 'correct_rank', 'points', 'answer_text', 'explanation', 'answer_image_url']  # Add ranking fields
    readonly_fields = ['image_preview']

    # Optional: Method to display a preview of the uploaded image
    def image_preview(self, obj):
        if obj.image_url:
            return format_html(f'<img src="{obj.image_url}" style="max-height: 100px;" />')
        return "No Image"
    image_preview.short_description = "Image Preview"

# Admin customization for Question
class QuestionAdmin(admin.ModelAdmin):
    form = QuestionAdminForm
    list_display = ('text', 'game', 'category', 'question_type', 'question_number', 'game_round', 'total_points', 'answer_bank')
    list_filter = ('game', 'category', 'question_type')
    search_fields = ['text']
    
    inlines = [AnswerInline]  # Inline answers in the question form

    ordering = ['game', 'question_number']


# Admin customization for Game
class GameAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_password_protected', 'created_at')
    list_filter = ('is_password_protected',)
    fields = ('name', 'description', 'is_password_protected', 'password')
    ordering = ['name']


class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_games')
    list_filter = ('games',)
    search_fields = ['name']

    # Custom method to display related games
    def get_games(self, obj):
        return ", ".join([game.name for game in obj.games.all()])

    get_games.short_description = 'Games'

# Registering the models with custom admin interfaces
admin.site.register(Game, GameAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Question, QuestionAdmin)
admin.site.register(QuestionType)
admin.site.register(QuestionRound)