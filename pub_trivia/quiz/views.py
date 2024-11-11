from django.shortcuts import render, get_object_or_404, redirect
from .models import Game, Category, Question
from django.http import HttpResponseRedirect

def game_list_view(request):
    """View to list available trivia games."""
    games = Game.objects.all()
    return render(request, 'quiz/game_list.html', {'games': games})

def game_view(request, game_id):
    """
    View to display the current question in a game.
    This view retrieves all questions ordered by 'question_number' and progresses sequentially.
    """
    game = get_object_or_404(Game, id=game_id)
    
    # Get all questions in the game, ordered by question_number
    questions = game.questions.order_by('question_number')

    # Get the current question number from request or default to the first question
    current_question_number = request.GET.get('question_number', 1)
    
    try:
        current_question_number = int(current_question_number)
        current_question = questions.get(question_number=current_question_number)
    except (ValueError, Question.DoesNotExist):
        # If the number is invalid or the question doesn't exist, start at the first question
        current_question = questions.first()

    # Determine the next question number (if any)
    next_question = questions.filter(question_number__gt=current_question.question_number).first()

    context = {
        'game': game,
        'current_question': current_question,
        'next_question': next_question,
    }

    return render(request, 'quiz/game.html', context)

def submit_answer(request, game_id):
    """
    Handles the submission of an answer to a question.
    After submission, it redirects to the next question or shows the final score.
    """
    game = get_object_or_404(Game, id=game_id)
    
    if request.method == 'POST':
        question_number = request.POST.get('question_number')
        user_answer = request.POST.get('answer')
        question = get_object_or_404(Question, game=game, question_number=question_number)

        # Here you would validate the user's answer (exact validation logic depends on the question type)
        # Example validation (for demonstration purposes):
        is_correct = False
        if user_answer.lower() == 'correct_answer':  # Replace with actual logic
            is_correct = True
        
        # Store the answer and score (you'll need a model for tracking answers and user progress)
        # This is just a placeholder for now
        # For example, you might create a model to store user answers and scores
        request.session['score'] = request.session.get('score', 0) + (1 if is_correct else 0)

        # Redirect to the next question
        next_question_number = int(question_number) + 1
        next_question = game.questions.filter(question_number=next_question_number).first()

        if next_question:
            return HttpResponseRedirect(f'/game/{game_id}/?question_number={next_question_number}')
        else:
            # No more questions, show the final score
            return redirect('game_complete', game_id=game_id)

    return redirect('game', game_id=game_id)

def category_view(request, category_id):
    """View to display questions within a category, ordered by their question number."""
    category = get_object_or_404(Category, id=category_id)
    
    # Get the first question in the category based on its order in the game
    question = category.questions.order_by('question_number').first()

    return render(request, 'quiz/category.html', {'category': category, 'question': question})
