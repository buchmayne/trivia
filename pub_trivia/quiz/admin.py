from django.contrib import admin
from .models import Game, Category, Question, Answer, QuestionType

# Inline to add multiple answers directly in the question form
class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4  # Set the default number of answer fields to display
    min_num = 1  # Require at least one answer
    max_num = 10  # Maximum number of answer options
    verbose_name = "Answer"
    verbose_name_plural = "Answers"
    fields = ['text', 'display_order', 'correct_rank', 'points', 'answer_text', 'explanation']  # Add ranking fields

# Admin customization for Question
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'game', 'category', 'question_type', 'question_number', 'total_points')
    list_filter = ('game', 'category', 'question_type')
    search_fields = ['text']
    
    inlines = [AnswerInline]  # Inline answers in the question form

    ordering = ['game', 'question_number']


# Admin customization for Game
class GameAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ['name']
    ordering = ['name']

# Admin customization for Category
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'game')
    list_filter = ('game',)
    search_fields = ['name']

# Registering the models with custom admin interfaces
admin.site.register(Game, GameAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Question, QuestionAdmin)
admin.site.register(QuestionType)