from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404

from .models import Question


def index(request):
    latest_question_list = Question.objects.order_by("-question_number")[:20]
    context = {
        "latest_question_list": latest_question_list
    }
    return render(request, "quiz/index.html", context)

def detail(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    return render(request, "quiz/detail.html", {"question": question})

def results(requestion, question_id):
    response = "You're looking at the results of question %s."
    return HttpResponse(response % question_id)

def answer(requestion, question_id):
    return HttpResponse("You're answering question %s." % question_id)
