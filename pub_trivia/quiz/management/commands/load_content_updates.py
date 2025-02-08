from django.core.management.base import BaseCommand
import json
import os
from django.conf import settings
from quiz.models import Question, Game, Category, QuestionType, QuestionRound
from django.db import transaction

class Command(BaseCommand):
    help = 'Load content updates from the content_updates directory'

    def handle(self, *args, **options):
        updates_dir = os.path.join(settings.BASE_DIR, 'content_updates')
        
        if not os.path.exists(updates_dir):
            os.makedirs(updates_dir)
            self.stdout.write('Created content_updates directory')
            return None

        processed_file = os.path.join(updates_dir, '.processed')
        processed_updates = set()
        if os.path.exists(processed_file):
            with open(processed_file, 'r') as f:
                processed_updates = set(f.read().splitlines())

        for filename in sorted(os.listdir(updates_dir)):
            if not filename.endswith('.json') or filename in processed_updates:
                continue

            self.stdout.write(f'Processing {filename}...')
            
            try:
                with open(os.path.join(updates_dir, filename)) as f:
                    data = json.load(f)
                    
                with transaction.atomic():
                    for game_data in data.get('question_groups', []):
                        game, _ = Game.objects.get_or_create(
                            name=game_data['game_name'],
                            defaults={
                                'description': game_data.get('game_description', ''),
                                'is_password_protected': game_data.get('is_password_protected', False),
                                'password': game_data.get('password'),
                                'game_order': game_data.get('game_order', 1)
                            }
                        )

                        for question_data in game_data.get('questions', []):
                            # Get or create category if specified
                            category = None
                            if question_data.get('category'):
                                category, _ = Category.objects.get_or_create(
                                    name=question_data['category']
                                )
                                game.categories.add(category)

                            # Get or create question type
                            question_type, _ = QuestionType.objects.get_or_create(
                                name=question_data['question_type']
                            )

                            # Get or create round if specified
                            game_round = None
                            if question_data.get('round'):
                                game_round, _ = QuestionRound.objects.get_or_create(
                                    name=question_data['round']['name'],
                                    defaults={
                                        'round_number': question_data['round'].get('round_number', 1)
                                    }
                                )

                            # Get or create question
                            question, created = Question.objects.get_or_create(
                                game=game,
                                question_number=question_data['question_number'],
                                defaults={
                                    'category': category,
                                    'text': question_data['text'],
                                    'answer_bank': question_data.get('answer_bank'),
                                    'question_type': question_type,
                                    'question_image_url': question_data.get('question_image_url'),
                                    'answer_image_url': question_data.get('answer_image_url'),
                                    'total_points': question_data.get('total_points', 1),
                                    'game_round': game_round
                                }
                            )

                            if created:
                                # Only create answers for new questions
                                for answer_data in question_data.get('answers', []):
                                    question.answers.create(
                                        text=answer_data.get('text'),
                                        question_image_url=answer_data.get('question_image_url'),
                                        display_order=answer_data.get('display_order'),
                                        correct_rank=answer_data.get('correct_rank'),
                                        points=answer_data.get('points', 1),
                                        answer_text=answer_data.get('answer_text'),
                                        explanation=answer_data.get('explanation'),
                                        answer_image_url=answer_data.get('answer_image_url')
                                    )

                # Mark file as processed only if all operations succeeded
                with open(processed_file, 'a') as f:
                    f.write(f'{filename}\n')
                    
            except Exception as e:
                self.stderr.write(f'Error processing {filename}: {str(e)}')
                raise