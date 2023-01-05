from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def index(request):
    return HttpResponse("Hello world. You're at the quiz index.")


def detail(request, question_id):
    return HttpResponse("You're looking at question %s." % question_id)
