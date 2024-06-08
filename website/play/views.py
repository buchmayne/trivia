from django.shortcuts import render, get_object_or_404
from .models import RankingQuestion

def ranking_question(request, question_id):
    question = get_object_or_404(RankingQuestion, question_id=question_id)
    options = question.rankingoption_set.all()
    
    if request.method == 'POST':
        # Handle form submission and process the user's answer
        # Retrieve the selected rankings from the form data
        selected_rankings = request.POST.getlist('rankings')
        
        # Compare the selected rankings with the correct rankings
        correct_rankings = list(options.values_list('correct_rank', flat=True))
        
        if selected_rankings == correct_rankings:
            # User's answer is correct
            result = 'Correct!'
        else:
            # User's answer is incorrect
            result = 'Incorrect!'
        
        # Render the result template with the question, options, and result
        return render(request, 'ranking_question_result.html', {
            'question': question,
            'options': options,
            'result': result,
        })
    
    # Render the ranking question template with the question and options
    return render(request, 'ranking_question.html', {
        'question': question,
        'options': options,
    })