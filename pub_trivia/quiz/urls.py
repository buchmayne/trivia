from django.urls import path
from . import views

app_name = 'quiz'  # This defines the app namespace for reversing URLs

urlpatterns = [
    path('', views.game_list_view, name='game_list'),  # List available games
    path('game/<int:game_id>/', views.game_view, name='game_view'),  # View a specific game
    path(
        'game/<int:game_id>/category/<int:category_id>/question/<int:question_id>/', views.question_view, name='question_view'
    ),  
]
