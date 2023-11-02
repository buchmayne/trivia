from django.urls import path

from . import views

app_name = "quiz"
urlpatterns = [
    path("", views.index, name="index"),
    # question_id
    path("<int:question_id>/", views.detail, name='detail'),
    path("<int:question_id>/results", views.results, name="results"),
    path("<int:question_id>/answer/", views.answer, name="answer"),
]