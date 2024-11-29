from django.shortcuts import render, get_object_or_404, redirect
from .models import Game, Category, Question
from django.http import HttpResponseRedirect

def game_list_view(request):
    """View to list available trivia games."""
    games = Game.objects.all()
    return render(request, 'quiz/game_list.html', {'games': games})

def game_view(request, game_id):
    """
    View to display all questions in a game, allowing the user to select any question.
    """
    game = get_object_or_404(Game, id=game_id)
    
    # Get all questions in the game, ordered by question_number
    questions = game.questions.order_by('question_number')

    context = {
        'game': game,
        'questions': questions,  # Pass all questions to the template
    }

    return render(request, 'quiz/game.html', context)


def question_view(request, game_id, category_id, question_id):
    question = get_object_or_404(Question, pk=question_id)
    return render(request, 'quiz/question_view.html', {'question': question})

