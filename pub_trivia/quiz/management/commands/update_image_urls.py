# quiz/management/commands/update_image_urls.py
from django.core.management.base import BaseCommand
from quiz.models import Question, Answer
import time

class Command(BaseCommand):
    help = 'Update image URLs from S3 to CloudFront'

    def handle(self, *args, **options):
        s3_domain = 'django-trivia-app-bucket.s3.amazonaws.com'
        cloudfront_domain = 'd1eomq1h9ixjmb.cloudfront.net'

        # Update Question image URLs
        questions = Question.objects.exclude(question_image_url='').exclude(question_image_url__isnull=True)
        question_count = 0
        
        for question in questions:
            if s3_domain in question.question_image_url:
                question.question_image_url = question.question_image_url.replace(
                    s3_domain, cloudfront_domain
                )
                question.save()
                question_count += 1
                self.stdout.write(f'Updated question {question.id} image URL')
        
        # Update Answer image URLs
        answers = Answer.objects.exclude(question_image_url='').exclude(question_image_url__isnull=True)
        answer_count = 0
        
        for answer in answers:
            if s3_domain in answer.question_image_url:
                answer.question_image_url = answer.question_image_url.replace(
                    s3_domain, cloudfront_domain
                )
                answer.save()
                answer_count += 1
                self.stdout.write(f'Updated answer {answer.id} image URL')

        self.stdout.write(self.style.SUCCESS(
            f'Successfully updated {question_count} question URLs and {answer_count} answer URLs'
        ))