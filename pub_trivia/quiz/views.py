from django.shortcuts import render, get_object_or_404, redirect
from .models import Game, Category, Question, QuestionRound
from django.http import HttpResponseRedirect, JsonResponse
from django.db import models

def get_first_question(request, round_id):
    try:
        game_id = request.GET.get('game_id')
        first_question = Question.objects.filter(
            game_id=game_id,
            game_round_id=round_id
        ).order_by('question_number').first()
        
        if first_question:
            return JsonResponse({
                'id': first_question.id,
                'category_id': first_question.category.id
            })
        else:
            return JsonResponse({'error': 'No questions found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def game_list_view(request):
    """View to list available trivia games."""
    games = Game.objects.all()
    return render(request, 'quiz/game_list.html', {'games': games})


def get_first_question_info(request, game_id, round_id):
    try:
        # Get the first question in the selected round
        first_question = Question.objects.filter(
            game_id=game_id,
            game_round_id=round_id
        ).order_by('question_number').first()
        
        return JsonResponse({
            'id': first_question.id,
            'category_id': first_question.category.id
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def get_next_question(question):
    """Get the next question in the same round"""
    return Question.objects.filter(
        game=question.game,
        game_round=question.game_round,
        question_number__gt=question.question_number
    ).order_by('question_number').first()

def question_view(request, game_id, round_id, category_id, question_id):
    game = Game.objects.get(id=game_id)
    question = Question.objects.get(id=question_id)
    rounds = QuestionRound.objects.filter(questions__game=game).distinct().order_by('round_number')
    round_questions = question.game_round.questions.filter(game=game).order_by('question_number')
    
    # Get next question
    next_question = Question.objects.filter(
        game=game,
        game_round=question.game_round,
        question_number__gt=question.question_number
    ).order_by('question_number').first()

    return render(request, 'quiz/question_view.html', {
        'game': game,
        'question': question,
        'rounds': rounds,
        'round_questions': round_questions,
        'next_question': next_question,
    })

def answer_view(request, game_id, round_id, category_id, question_id):
    game = get_object_or_404(Game, pk=game_id)
    question = get_object_or_404(Question, pk=question_id)

    rounds = QuestionRound.objects.filter(questions__game=game).distinct().order_by('round_number')
    round_questions = question.game_round.questions.filter(game=game).order_by('question_number')
    

    next_question = Question.objects.filter(
        game=game,
        game_round=question.game_round,
        question_number__gt=question.question_number
    ).order_by('question_number').first()

    return render(request, 'quiz/answer_view.html', {
        'game': game,
        'question': question,
        'rounds': rounds,  # Added
        'round_questions': round_questions,  # Added
        'next_question': next_question,
    })

def get_round_questions(request, game_id, round_id):
    questions = Question.objects.filter(
        game_id=game_id,
        game_round_id=round_id
    ).order_by('question_number').values(
        'id', 
        'question_number', 
        'category_id'
    )
    
    return JsonResponse({
        'questions': list(questions)
    })

def game_overview(request, game_id):
    game = Game.objects.get(id=game_id)
    rounds = QuestionRound.objects.filter(questions__game=game).distinct().order_by('round_number')
    
    # Calculate stats for each round
    rounds_stats = []
    total_questions = 0
    total_points = 0
    
    for round in rounds:
        round_questions = Question.objects.filter(game=game, game_round=round)
        question_count = round_questions.count()
        points = round_questions.aggregate(total_points=models.Sum('total_points'))['total_points'] or 0
        
        rounds_stats.append({
            'round': round,
            'question_count': question_count,
            'total_points': points
        })
        total_questions += question_count
        total_points += points

    return render(request, 'quiz/game_overview.html', {
        'game': game,
        'rounds_stats': rounds_stats,
        'total_questions': total_questions,
        'total_points': total_points,
    })