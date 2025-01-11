from django.urls import path
from . import views

app_name = 'quiz'

urlpatterns = [
    path('', views.game_list_view, name='game_list'),  # List available games
    path('game/<int:game_id>/', views.game_options_view, name='game_options'),  # New Game Options view
    
    path('game/<int:game_id>/questions/rounds', views.game_rounds_questions_view, name='game_rounds_questions'),  # View all questions in a game
    path('game/<int:game_id>/answers/rounds', views.game_rounds_answers_view, name='game_rounds_answers'),  # View all questions in a game
    
    path('game/<int:game_id>/questions/round/<int:round_id>/questions/', views.round_questions_view, name='round_questions'),  # View questions in a round
    path('game/<int:game_id>/answers/round/<int:round_id>/answers/', views.round_answers_view, name='round_answers'),  # View questions in a round
    
    path('game/<int:game_id>/questions/', views.game_questions_view, name='game_questions'),  # View all questions in a game
    path('game/<int:game_id>/answers/', views.game_answers_view, name='game_answers'),  # View all answers in a game
    
    
    path(
        'game/<int:game_id>/questions/round/<int:round_id>/questions/category/<int:category_id>/question/<int:question_id>/', 
        views.question_view, 
        name='question_view' # View Question
    ),
    path(
        'game/<int:game_id>/answers/round/<int:round_id>/answers/category/<int:category_id>/question/<int:question_id>/', 
        views.answer_view, 
        name='answer_view' # View Answer
    ),
    path('api/rounds/<int:round_id>/first-question/', views.get_first_question, name='first_question'),
    path('quiz/game/<int:game_id>/round/<int:round_id>/first-question-info/', views.get_first_question_info, name='first_question_info'),
    path('game/<int:game_id>/questions/round/<int:round_id>/questions-list/', views.get_round_questions, name='round_questions_list'),
    path('game/<int:game_id>/overview/', views.game_overview, name='game_overview'),
]
