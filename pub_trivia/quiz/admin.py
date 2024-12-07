from django.contrib import admin
from django.utils.html import format_html
from .models import Game, Category, Question, Answer, QuestionType, QuestionRound

# Inline to add multiple answers directly in the question form
class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4  # Set the default number of answer fields to display
    min_num = 1  # Require at least one answer
    max_num = 10  # Maximum number of answer options
    verbose_name = "Answer"
    verbose_name_plural = "Answers"
    fields = ['text', 'image_url', 'display_order', 'correct_rank', 'points', 'answer_text', 'explanation']  # Add ranking fields
    readonly_fields = ['image_preview']

    # Optional: Method to display a preview of the uploaded image
    def image_preview(self, obj):
        if obj.image_url:
            return format_html(f'<img src="{obj.image_url}" style="max-height: 100px;" />')
        return "No Image"
    image_preview.short_description = "Image Preview"

# Admin customization for Question
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'game', 'category', 'question_type', 'question_number', 'game_round', 'total_points')
    list_filter = ('game', 'category', 'question_type')
    search_fields = ['text']
    
    inlines = [AnswerInline]  # Inline answers in the question form

    ordering = ['game', 'question_number']


# Admin customization for Game
class GameAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ['name']
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