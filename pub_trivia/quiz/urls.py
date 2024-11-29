from django.urls import path
from . import views

app_name = 'quiz'

urlpatterns = [
    path('', views.game_list_view, name='game_list'),  # List available games
    path('game/<int:game_id>/', views.game_options_view, name='game_options'),  # New Game Options view
    path('game/<int:game_id>/questions/', views.game_questions_view, name='game_questions'),  # View all questions in a game
    path('game/<int:game_id>/answers/', views.game_answers_view, name='game_answers'),  # View all answers in a game
    path(
        'game/<int:game_id>/questions/category/<int:category_id>/question/<int:question_id>/', views.question_view, name='question_view'
    ),
    path(
        'game/<int:game_id>/answers/category/<int:category_id>/question/<int:question_id>/', views.answer_view, name='answer_view'
    ),  
]
