# quiz/management/commands/fix_image_urls.py
from django.core.management.base import BaseCommand
from quiz.models import Answer, Question
import re

class Command(BaseCommand):
    help = 'Fix doubled CloudFront domain in image URLs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Pattern to match: cloudfront domain followed by s3 domain
        pattern = r'(https://d1eomq1h9ixjmb\.cloudfront\.net)(https://django-trivia-app-bucket\.s3\.amazonaws\.com)'
        replacement = r'\1'  # Keep only the CloudFront domain
        
        # Track counts of corrections
        answer_count = 0
        question_count = 0
        
        # Process Answer models
        self.stdout.write(self.style.NOTICE("Checking Answer image URLs..."))
        for answer in Answer.objects.all():
            changed = False
            
            # Check answer_image_url
            if answer.answer_image_url and re.search(pattern, answer.answer_image_url):
                new_url = re.sub(pattern, replacement, answer.answer_image_url)
                self.stdout.write(f"Answer {answer.id} answer_image_url:\n  {answer.answer_image_url} → \n  {new_url}")
                if not dry_run:
                    answer.answer_image_url = new_url
                    changed = True
            
            # Check question_image_url
            if answer.question_image_url and re.search(pattern, answer.question_image_url):
                new_url = re.sub(pattern, replacement, answer.question_image_url)
                self.stdout.write(f"Answer {answer.id} question_image_url:\n  {answer.question_image_url} → \n  {new_url}")
                if not dry_run:
                    answer.question_image_url = new_url
                    changed = True
            
            if changed:
                answer.save()
                answer_count += 1
        
        # Process Question models
        self.stdout.write(self.style.NOTICE("Checking Question image URLs..."))
        for question in Question.objects.all():
            changed = False
            
            # Check question_image_url
            if question.question_image_url and re.search(pattern, question.question_image_url):
                new_url = re.sub(pattern, replacement, question.question_image_url)
                self.stdout.write(f"Question {question.id} question_image_url:\n  {question.question_image_url} → \n  {new_url}")
                if not dry_run:
                    question.question_image_url = new_url
                    changed = True
            
            # Check answer_image_url
            if question.answer_image_url and re.search(pattern, question.answer_image_url):
                new_url = re.sub(pattern, replacement, question.answer_image_url)
                self.stdout.write(f"Question {question.id} answer_image_url:\n  {question.answer_image_url} → \n  {new_url}")
                if not dry_run:
                    question.answer_image_url = new_url
                    changed = True
            
            if changed:
                question.save()
                question_count += 1
        
        # Report results
        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"DRY RUN: Would fix {answer_count} answers and {question_count} questions"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Successfully fixed {answer_count} answers and {question_count} questions"
            ))