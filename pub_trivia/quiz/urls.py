from django.urls import path
from . import views

app_name = 'quiz'

urlpatterns = [
    path('', views.game_list_view, name='game_list'),  # List available games
    path(
        'game/<int:game_id>/questions/round/<int:round_id>/questions/category/<int:category_id>/question/<int:question_id>/', 
        views.question_view, 
        name='question_view'
    ),
    path(
        'game/<int:game_id>/answers/round/<int:round_id>/answers/category/<int:category_id>/question/<int:question_id>/', 
        views.answer_view, 
        name='answer_view'
    ),
    path('api/rounds/<int:round_id>/first-question/', views.get_first_question, name='first_question'),
    path('quiz/game/<int:game_id>/round/<int:round_id>/first-question-info/', views.get_first_question_info, name='first_question_info'),
    path('game/<int:game_id>/questions/round/<int:round_id>/questions-list/', views.get_round_questions, name='round_questions_list'),
    path('game/<int:game_id>/overview/', views.game_overview, name='game_overview'),
]
