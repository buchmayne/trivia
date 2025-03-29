from django.core.management.base import BaseCommand
import json
import os
from django.conf import settings
from quiz.models import Game, Category, Question, Answer, QuestionType, QuestionRound
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Export changes between current database and initial data"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be exported without creating files',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information about changes',
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Show detailed information about field differences',
        )

    def normalize_values(self, value):
        """Normalize values for comparison"""
        if value is None:
            return ""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        # convert to a string and strip whitespace
        return str(value).strip()
    
    def values_equal(self, val1, val2, field_name=None, debug=False):
        "Compare two values after normalizing them"
        norm1 = self.normalize_values(val1)
        norm2 = self.normalize_values(val2)

        result = norm1 == norm2

        if debug and not result and field_name:
            self.stdout.write(f"Field '{field_name}' differs:")
            self.stdout.write(f"    Value 1: '{val1}' (type: {type(val1)}) -> normalized: '{norm1}' (type: {type(norm1)})")
            self.stdout.write(f"    Value 2: '{val2}' (type: {type(val2)}) -> normalized: '{norm2}' (type: {type(norm2)})")

        return result
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        debug = options['debug']
        
        self.stdout.write("Comparing current database with initial data...")
        
        # Step 1: Load the initial data file
        initial_data_path = os.path.join(settings.BASE_DIR, "db_initial_data.json")
        if not os.path.exists(initial_data_path):
            self.stderr.write(self.style.ERROR("Initial data file not found: db_initial_data.json"))
            return
        
        try:
            with open(initial_data_path, 'r') as f:
                initial_data = json.load(f)
                self.stdout.write(f"Loaded initial data file")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error loading initial data: {str(e)}"))
            return
            
        # Print the structure to understand what we're working with
        if verbose:
            self.stdout.write(f"Initial data type: {type(initial_data)}")
            if isinstance(initial_data, list):
                self.stdout.write(f"Initial data is a list with {len(initial_data)} items")
                if len(initial_data) > 0:
                    self.stdout.write(f"First item type: {type(initial_data[0])}")
                    self.stdout.write(f"First item model: {initial_data[0].get('model') if isinstance(initial_data[0], dict) else 'unknown'}")
        
        # Step 2: Extract questions and games from initial data for comparison
        initial_questions = {}
        initial_games = {}
        initial_games_by_name = {}
        initial_categories = {}
        initial_question_types = {}
        initial_rounds = {}
        
        # First, identify the structure of the initial data
        if isinstance(initial_data, list):
            # Handle Django serialized data format (list of objects with model field)
            for item in initial_data:
                if isinstance(item, dict) and 'model' in item and 'pk' in item and 'fields' in item:
                    model = item['model']
                    pk = item['pk']
                    fields = item['fields']
                    
                    # Extract game data
                    if model == 'quiz.game':
                        game_data = {
                            'id': pk,
                            'name': fields.get('name', ''),
                            'description': fields.get('description', ''),
                            'is_password_protected': fields.get('is_password_protected', False),
                            'password': fields.get('password', ''),
                            'game_order': fields.get('game_order', 1),
                        }
                        initial_games[pk] = game_data
                        initial_games_by_name[fields.get('name', '')] = game_data
                    
                    # Extract category data
                    elif model == 'quiz.category':
                        initial_categories[pk] = {
                            'id': pk,
                            'name': fields.get('name', ''),
                            'games': fields.get('games', []),
                        }
                    
                    # Extract question type data
                    elif model == 'quiz.questiontype':
                        initial_question_types[pk] = {
                            'id': pk,
                            'name': fields.get('name', ''),
                        }
                    
                    # Extract round data
                    elif model == 'quiz.questionround':
                        initial_rounds[pk] = {
                            'id': pk,
                            'name': fields.get('name', ''),
                            'round_number': fields.get('round_number', 1),
                        }
                    
                    # Extract question data
                    elif model == 'quiz.question':
                        game_id = fields.get('game')
                        category_id = fields.get('category')
                        question_number = fields.get('question_number')
                        
                        # Create a key based on game name, category name, and question number
                        # We'll need to look up the names based on IDs
                        game_name = initial_games.get(game_id, {}).get('name', f"game_{game_id}")
                        category_name = initial_categories.get(category_id, {}).get('name') if category_id else None
                        
                        key = f"{game_name}::{category_name}::{question_number}"
                        
                        initial_questions[key] = {
                            'id': pk,
                            'text': fields.get('text', ''),
                            'answer_bank': fields.get('answer_bank', ''),
                            'question_type': fields.get('question_type'),
                            'question_type_name': initial_question_types.get(fields.get('question_type'), {}).get('name', ''),
                            'question_image_url': fields.get('question_image_url', ''),
                            'answer_image_url': fields.get('answer_image_url', ''),
                            'total_points': fields.get('total_points', 1),
                            'question_number': question_number,
                            'game': game_id,
                            'game_name': game_name,
                            'category': category_id,
                            'category_name': category_name,
                            'game_round': fields.get('game_round'),
                            'answers': []  # We'll fill this with answer data in a second pass
                        }
                    
                    # Note: We'll handle answers separately since they need to be linked to questions
            
            # Now process answers and link them to questions
            answer_count = 0
            linked_count = 0
            for item in initial_data:
                if isinstance(item, dict) and item.get('model') == 'quiz.answer':
                    fields = item['fields']
                    question_id = fields.get('question')
                    answer_count += 1
                    
                    # Find which question this answer belongs to
                    for q_key, q_data in initial_questions.items():
                        if q_data['id'] == question_id:
                            q_data['answers'].append({
                                'text': fields.get('text', ''),
                                'question_image_url': fields.get('question_image_url', ''),
                                'display_order': fields.get('display_order'),
                                'correct_rank': fields.get('correct_rank'),
                                'points': fields.get('points', 1),
                                'answer_text': fields.get('answer_text', ''),
                                'explanation': fields.get('explanation', ''),
                                'answer_image_url': fields.get('answer_image_url', ''),
                            })
                            linked_count += 1
                            break
                            
            if verbose:
                self.stdout.write(f"Processed {answer_count} answers, linked {linked_count} to questions")
        
        else:
            # Handle the question_groups structure you previously described
            # This is the fallback in case the data is not in Django serialized format
            for game_data in initial_data.get('question_groups', []):
                game_name = game_data.get('game_name')
                
                # Store game data
                game_obj = {
                    'name': game_name,
                    'description': game_data.get('game_description'),
                    'is_password_protected': game_data.get('is_password_protected', False),
                    'password': game_data.get('password'),
                    'game_order': game_data.get('game_order', 1),
                }
                initial_games_by_name[game_name] = game_obj
                
                # Store each question
                for question_data in game_data.get('questions', []):
                    # Create a unique key for each question
                    key = f"{game_name}::{question_data.get('category')}::{question_data.get('question_number')}"
                    initial_questions[key] = question_data
        
        self.stdout.write(f"Found {len(initial_games_by_name)} games, {len(initial_categories)} categories, " + 
                         f"{len(initial_questions)} questions in initial data")
        
        # Step 3: Compare with current database
        # Track changes
        changed_games = {}
        new_or_changed_questions = []
        
        # Check games first
        games = Game.objects.all()
        for game in games:
            game_found = False
            
            # Try to find game by name
            if game.name in initial_games_by_name:
                game_found = True
                initial_game = initial_games_by_name[game.name]
                
                # Compare game properties with debug info if needed
                if not self.values_equal(game.description, initial_game.get('description'), 'description', debug) or \
                   not self.values_equal(game.is_password_protected, initial_game.get('is_password_protected'), 'is_password_protected', debug) or \
                   not self.values_equal(game.password, initial_game.get('password'), 'password', debug) or \
                   not self.values_equal(game.game_order, initial_game.get('game_order'), 'game_order', debug):
                    
                    if verbose:
                        self.stdout.write(f"Game changed: {game.name}")
                    
                    changed_games[game.name] = True
            
            # If not found at all, it's new
            if not game_found:
                if verbose:
                    self.stdout.write(f"New game found: {game.name}")
                changed_games[game.name] = True
        
        # Now check questions
        questions = Question.objects.select_related(
            'game', 'category', 'question_type', 'game_round'
        ).prefetch_related('answers').all()
        
        for question in questions:
            # If the question's game has changed, include the question
            if question.game.name in changed_games:
                new_or_changed_questions.append(question)
                if verbose:
                    self.stdout.write(f"Including question {question.id} due to game change")
                continue
            
            # Create the same key format used for initial questions
            key = f"{question.game.name}::{question.category.name if question.category else None}::{question.question_number}"
            
            # Check if question is new
            if key not in initial_questions:
                if verbose:
                    self.stdout.write(f"New question found: {key}")
                new_or_changed_questions.append(question)
                continue
            
            # Question exists in initial data, check for changes
            initial_q = initial_questions[key]
            
            # Basic fields comparison with improved equality checking
            fields_match = True
            if not self.values_equal(question.text, initial_q.get('text', ''), 'text', debug) or \
               not self.values_equal(question.answer_bank, initial_q.get('answer_bank', ''), 'answer_bank', debug) or \
               (question.question_type and not self.values_equal(question.question_type.name, initial_q.get('question_type_name', initial_q.get('question_type', '')), 'question_type', debug)) or \
               not self.values_equal(question.question_image_url, initial_q.get('question_image_url', ''), 'question_image_url', debug) or \
               not self.values_equal(question.answer_image_url, initial_q.get('answer_image_url', ''), 'answer_image_url', debug) or \
               not self.values_equal(question.total_points, initial_q.get('total_points', 1), 'total_points', debug):
                
                fields_match = False
                if verbose:
                    self.stdout.write(f"Question fields changed: {key}")
                
            # If basic fields don't match, add to changes list and continue
            if not fields_match:
                new_or_changed_questions.append(question)
                continue
            
            # Compare answers
            initial_answers = initial_q.get('answers', [])
            db_answers = list(question.answers.all())
            
            # Simple length check first
            if len(initial_answers) != len(db_answers):
                if verbose:
                    self.stdout.write(f"Answer count changed: {key} - Initial: {len(initial_answers)}, Current: {len(db_answers)}")
                new_or_changed_questions.append(question)
                continue
            
            # Sort answers by display order first, then by test, then by answer_text
            # This is to ensure we're comparing the same answers in the same order
            db_answers.sort(key=lambda a: (a.display_order or 0, str(a.text or ''), str(a.answer_text or '')))
            initial_answers.sort(key=lambda a: (a.get('display_order') or 0, str(a.get('text', '') or ''), str(a.get('answer_text', '') or '')))
            
            # More detailed answer comparison
            answers_changed = False
            for i, (db_ans, initial_ans) in enumerate(zip(db_answers, initial_answers)):
                if not self.values_equal(db_ans.text, initial_ans.get('text', ''), f'answer_{i}_text', debug) or \
                   not self.values_equal(db_ans.question_image_url, initial_ans.get('question_image_url', ''), f'answer_{i}_question_image_url', debug) or \
                   not self.values_equal(db_ans.display_order, initial_ans.get('display_order'), f'answer_{i}_display_order', debug) or \
                   not self.values_equal(db_ans.correct_rank, initial_ans.get('correct_rank'), f'answer_{i}_correct_rank', debug) or \
                   not self.values_equal(db_ans.points, initial_ans.get('points', 1), f'answer_{i}_points', debug) or \
                   not self.values_equal(db_ans.answer_text, initial_ans.get('answer_text', ''), f'answer_{i}_answer_text', debug) or \
                   not self.values_equal(db_ans.explanation, initial_ans.get('explanation', ''), f'answer_{i}_explanation', debug) or \
                   not self.values_equal(db_ans.answer_image_url, initial_ans.get('answer_image_url', ''), f'answer_{i}_answer_image_url', debug):
                    
                    answers_changed = True
                    if verbose:
                        self.stdout.write(f"Answer {i+1} changed for question: {key}")
                    break
            
            if answers_changed:
                new_or_changed_questions.append(question)
        
        # Report findings
        self.stdout.write(f"Found {len(changed_games)} changed games")
        self.stdout.write(f"Found {len(new_or_changed_questions)} new or changed questions")
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run completed successfully"))
            return
            
        # If nothing changed, we're done
        if not changed_games and not new_or_changed_questions:
            self.stdout.write(self.style.SUCCESS("No changes detected"))
            return
            
        # At this point we'd prepare the changes file, but we'll implement that in the next step
        self.stdout.write(self.style.SUCCESS("Comparison complete!"))
        # Display summary
        self.stdout.write("Changed games:")
        for game_name in changed_games:
            self.stdout.write(f"  - {game_name}")