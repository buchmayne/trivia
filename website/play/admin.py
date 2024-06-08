from functools import partial
from django.contrib import admin
from .models import (
    TriviaGame,
    Category,
    RankingQuestion,
    RankingOption
    )


class RankingOptionInline(admin.TabularInline):
    model = RankingOption
    extra = 4
    fields = ['option_text', 'correct_rank', 'points', 'value_text']
    template = 'admin/edit_inline/tabular_ranking_option.html'


class RankingQuestionAdmin(admin.ModelAdmin):
    inlines = [RankingOptionInline]


admin.site.register(TriviaGame)
admin.site.register(Category)
admin.site.register(RankingQuestion, RankingQuestionAdmin)