from django.shortcuts import render, get_object_or_404, redirect
from .models import Game, Category, Question, QuestionRound
from django.http import HttpResponseRedirect
from django.db.models import Sum

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

def question_view(request, game_id, round_id, category_id, question_id):
    game = get_object_or_404(Game, pk=game_id)
    question = get_object_or_404(Question, pk=question_id)

    # Get all the questions in the current round
    round_questions = Question.objects.filter(
        game=game,
        game_round=question.game_round
    ).order_by('question_number')

    # Get the next question
    next_question = (
        round_questions.filter(question_number__gt=question.question_number).first()
    )

    context = {
        'game': game,
        'question': question,
        'next_question': next_question,
    }

    return render(request, 'quiz/question_view.html', context)

def answer_view(request, game_id, round_id, category_id, question_id):
    game = get_object_or_404(Game, pk=game_id)
    question = get_object_or_404(Question, pk=question_id)

    # Get all the questions in the current round
    round_questions = Question.objects.filter(
        game=game,
        game_round=question.game_round
    ).order_by('question_number')

    # Get the next question
    next_question = (
        round_questions.filter(question_number__gt=question.question_number).first()
    )

    context = {
        'game': game,
        'question': question,
        'next_question': next_question,
    }

    return render(request, 'quiz/answer_view.html', context)

def game_rounds_view(request, game_id):
    """View to display all rounds in a game."""
    game = get_object_or_404(Game, id=game_id)
    rounds = QuestionRound.objects.filter(questions__game=game).distinct()  # Get all rounds with questions in the game
    return render(request, 'quiz/game_rounds.html', {'game': game, 'rounds': rounds})

def game_rounds_questions_view(request, game_id):
    """View to display all rounds in a game."""
    
    game = get_object_or_404(Game, id=game_id)

    # Total points for the game
    total_game_points = game.questions.aggregate(total_points=Sum('total_points'))['total_points'] or 0

    # Get all rounds with questions in the game and calculate total points for each round
    rounds = (
        QuestionRound.objects.filter(questions__game=game)
        .annotate(total_points=Sum('questions__total_points'))
        .distinct()
    )

    context = {
        'game': game,
        'rounds': rounds,
        'total_game_points': total_game_points,
    }
    
    return render(request, 'quiz/game_rounds_questions.html', context)

def game_rounds_answers_view(request, game_id):
    """View to display all rounds in a game."""
    game = get_object_or_404(Game, id=game_id)

    # Total points for the game
    total_game_points = game.questions.aggregate(total_points=Sum('total_points'))['total_points'] or 0

    # Get all rounds with questions in the game and calculate total points for each round
    rounds = (
        QuestionRound.objects.filter(questions__game=game)
        .annotate(total_points=Sum('questions__total_points'))
        .distinct()
    )

    context = {
        'game': game,
        'rounds': rounds,
        'total_game_points': total_game_points,
    }
    
    return render(request, 'quiz/game_rounds_answers.html', context)

def round_questions_view(request, game_id, round_id):
    """View to display all questions in a specific round."""
    game = get_object_or_404(Game, id=game_id)
    round_ = get_object_or_404(QuestionRound, id=round_id)
    questions = round_.questions.filter(game=game).order_by('question_number')  # Get questions in the round for the specific game

    # Total points for the round
    total_round_points = questions.aggregate(total_points=Sum('total_points'))['total_points'] or 0

    context = {
        'game': game,
        'round': round_,
        'questions': questions,
        'total_round_points': total_round_points,
    }

    return render(request, 'quiz/round_questions.html', context)

def round_answers_view(request, game_id, round_id):
    """View to display all questions in a specific round."""
    game = get_object_or_404(Game, id=game_id)
    round_ = get_object_or_404(QuestionRound, id=round_id)
    questions = round_.questions.filter(game=game).order_by('question_number')  # Get questions in the round for the specific game
    
    # Total points for the round
    total_round_points = questions.aggregate(total_points=Sum('total_points'))['total_points'] or 0

    context = {
        'game': game,
        'round': round_,
        'questions': questions,
        'total_round_points': total_round_points,
    }

    return render(request, 'quiz/round_answers.html', context)