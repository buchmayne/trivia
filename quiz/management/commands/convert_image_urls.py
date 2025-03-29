from django.core.management.base import BaseCommand
from django.conf import settings
from quiz.models import Question, Answer
import time

class Command(BaseCommand):
    help = "Convert full CloudFront URLs to just S3 paths in database"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--revert',
            action='store_true',
            help='Revert paths back to full URLs (rarely needed)',
        )

    def handle(self, *args, **options):
        cloudfront_domain = settings.AWS_CLOUDFRONT_DOMAIN
        dry_run = options['dry_run']
        revert = options['revert']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in dry-run mode - no changes will be made'))
        
        if revert:
            self.stdout.write(self.style.WARNING('REVERTING: Adding CloudFront domain to paths'))
        else:
            self.stdout.write(self.style.WARNING('CONVERTING: Removing CloudFront domain from URLs'))
        
        # Process Question models
        self.stdout.write(self.style.NOTICE('Processing Questions...'))
        question_count = 0
        
        questions = Question.objects.all()
        self.stdout.write(f"Found {questions.count()} questions to process")
        
        for question in questions:
            changed = False
            
            # Handle question_image_url
            if question.question_image_url:
                if not revert and question.question_image_url.startswith(cloudfront_domain):
                    new_url = question.question_image_url.replace(cloudfront_domain, '')
                    self.stdout.write(f"Question {question.id} image: {question.question_image_url} -> {new_url}")
                    if not dry_run:
                        question.question_image_url = new_url
                        changed = True
                elif revert and not question.question_image_url.startswith(cloudfront_domain):
                    new_url = f"{cloudfront_domain}{question.question_image_url}"
                    self.stdout.write(f"Question {question.id} image: {question.question_image_url} -> {new_url}")
                    if not dry_run:
                        question.question_image_url = new_url
                        changed = True
            
            # Handle answer_image_url
            if question.answer_image_url:
                if not revert and question.answer_image_url.startswith(cloudfront_domain):
                    new_url = question.answer_image_url.replace(cloudfront_domain, '')
                    self.stdout.write(f"Question {question.id} answer image: {question.answer_image_url} -> {new_url}")
                    if not dry_run:
                        question.answer_image_url = new_url
                        changed = True
                elif revert and not question.answer_image_url.startswith(cloudfront_domain):
                    new_url = f"{cloudfront_domain}{question.answer_image_url}"
                    self.stdout.write(f"Question {question.id} answer image: {question.answer_image_url} -> {new_url}")
                    if not dry_run:
                        question.answer_image_url = new_url
                        changed = True
            
            if changed and not dry_run:
                question.save()
                question_count += 1
                # Slight pause to avoid database load
                time.sleep(0.01)
        
        # Process Answer models
        self.stdout.write(self.style.NOTICE('Processing Answers...'))
        answer_count = 0
        
        answers = Answer.objects.all()
        self.stdout.write(f"Found {answers.count()} answers to process")
        
        for answer in answers:
            changed = False
            
            # Handle question_image_url
            if answer.question_image_url:
                if not revert and answer.question_image_url.startswith(cloudfront_domain):
                    new_url = answer.question_image_url.replace(cloudfront_domain, '')
                    self.stdout.write(f"Answer {answer.id} image: {answer.question_image_url} -> {new_url}")
                    if not dry_run:
                        answer.question_image_url = new_url
                        changed = True
                elif revert and not answer.question_image_url.startswith(cloudfront_domain):
                    new_url = f"{cloudfront_domain}{answer.question_image_url}"
                    self.stdout.write(f"Answer {answer.id} image: {answer.question_image_url} -> {new_url}")
                    if not dry_run:
                        answer.question_image_url = new_url
                        changed = True
            
            # Handle answer_image_url
            if answer.answer_image_url:
                if not revert and answer.answer_image_url.startswith(cloudfront_domain):
                    new_url = answer.answer_image_url.replace(cloudfront_domain, '')
                    self.stdout.write(f"Answer {answer.id} answer image: {answer.answer_image_url} -> {new_url}")
                    if not dry_run:
                        answer.answer_image_url = new_url
                        changed = True
                elif revert and not answer.answer_image_url.startswith(cloudfront_domain):
                    new_url = f"{cloudfront_domain}{answer.answer_image_url}"
                    self.stdout.write(f"Answer {answer.id} answer image: {answer.answer_image_url} -> {new_url}")
                    if not dry_run:
                        answer.answer_image_url = new_url
                        changed = True
            
            if changed and not dry_run:
                answer.save()
                answer_count += 1
                # Slight pause to avoid database load
                time.sleep(0.01)
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"DRY RUN: Would update {question_count} questions and {answer_count} answers"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully updated {question_count} questions and {answer_count} answers"))