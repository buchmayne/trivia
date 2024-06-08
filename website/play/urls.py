from django.urls import path
from .views import ranking_question

urlpatterns = [
    path('ranking_question/<int:question_id>/', ranking_question, name='ranking_question'),
]