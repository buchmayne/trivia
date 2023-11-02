from django.contrib import admin
from .models import Question, ChoicesSingleSlideMultipleChoiceNoAnswerBankQuestion

class ChoiceInline(admin.TabularInline):
    model = ChoicesSingleSlideMultipleChoiceNoAnswerBankQuestion
    extra = 4


class QuestionAdmin(admin.ModelAdmin):
    fieldsets = [
        ("Game", {"fields": ["game_id", "has_been_used", "question_number"]}),
        ("Question", {"fields": ["question_type", "category", "question_text", "points_application", "points"]})
    ]
    inlines = [ChoiceInline]


admin.site.register(Question, QuestionAdmin)