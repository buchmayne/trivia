from django.shortcuts import render, get_object_or_404, redirect
from .models import Game, Category, Question
from django.http import HttpResponseRedirect

def game_list_view(request):
    """View to list available trivia games."""
    games = Game.objects.all()
    return render(request, 'quiz/game_list.html', {'games': games})

def game_options_view(request, game_id):
    """View to let the user choose between viewing questions or answers for a specific game."""
    game = get_object_or_404(Game, id=game_id)
    return render(request, 'quiz/game_options.html', {'game': game})

def game_questions_view(request, game_id):
    """View to display all questions in a game."""
    game = get_object_or_404(Game, id=game_id)
    questions = game.questions.order_by('question_number')  # Get all questions in order
    return render(request, 'quiz/game_questions.html', {'game': game, 'questions': questions})

def game_answers_view(request, game_id):
    """View to display all answers for a game."""
    game = get_object_or_404(Game, id=game_id)
    questions = game.questions.prefetch_related('answers')  # Prefetch answers for efficiency
    return render(request, 'quiz/game_answers.html', {'game': game, 'questions': questions})

def question_view(request, game_id, category_id, question_id):
    question = get_object_or_404(Question, pk=question_id)
    return render(request, 'quiz/question_view.html', {'question': question})

def answer_view(request, game_id, category_id, question_id):
    question = get_object_or_404(Question, pk=question_id)
    return render(request, 'quiz/answer_view.html', {'question': question})
