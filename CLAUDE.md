# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Django web application for hosting trivia games at marleybuchman.com. It includes:
- A Django backend (4.2) with PostgreSQL database
- Frontend question/answer displays for trivia games
- Analytics dashboard for tracking game results and player statistics
- Admin interface for managing games, questions, and answers
- REST API for game sessions
- AWS S3 + CloudFront integration for media storage
- Docker deployment with nginx proxy and Let's Encrypt SSL

## Development Environment Setup

### Using uv (recommended)
```bash
# Install dependencies
uv sync

# Run development server
uv run manage.py runserver

# Run migrations
uv run manage.py migrate

# Create superuser for admin access
uv run manage.py createsuperuser

# Collect static files
uv run manage.py collectstatic
```

### Environment Variables
Create a `.env` file with:
- `SECRET_KEY`: Django secret key
- `DEBUG`: Set to "True" for development
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`: PostgreSQL credentials
- `DB_HOST`, `DB_PORT`: Database connection (localhost:5432 for local dev)
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: AWS credentials for S3

### Running Tests
The test suite is organized in `quiz/tests/` directory with 173+ tests covering all components.

```bash
# Run all tests
uv run manage.py test quiz

# Run specific test module
uv run manage.py test quiz.tests.test_models
uv run manage.py test quiz.tests.test_api_views
uv run manage.py test quiz.tests.test_integration

# Run specific test class
uv run manage.py test quiz.tests.test_models.GameModelTest
uv run manage.py test quiz.tests.test_api_views.CreateSessionAPITest

# Run specific test method
uv run manage.py test quiz.tests.test_models.GameModelTest.test_game_creation

# Run with options
uv run manage.py test quiz.tests --verbosity=2  # Verbose
uv run manage.py test quiz.tests --parallel     # Parallel execution
uv run manage.py test quiz.tests --keepdb       # Keep test DB
```

Test modules:
- `test_models.py` - Core models (Game, Question, Answer)
- `test_views.py` - Frontend views
- `test_api_views.py` - REST API endpoints
- `test_serializers.py` - DRF serializers
- `test_session_models.py` - Session models
- `test_session_views.py` - Session views
- `test_fields.py` - Custom fields (S3, CloudFront)
- `test_analytics.py` - Analytics utilities
- `test_api.py` - DRF ViewSets
- `test_views_extended.py` - Extended view tests
- `test_integration.py` - End-to-end workflows

### Docker Deployment
```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f web

# Run migrations in container
docker-compose exec web uv run manage.py migrate

# Stop all services
docker-compose down
```

## Architecture

### Apps
- **pub_trivia/**: Main Django project settings and root URLs
- **quiz/**: Core trivia application containing all models, views, and admin logic

### Data Model Hierarchy
```
Game (trivia event)
├── Questions (many)
│   ├── category (FK to Category)
│   ├── question_type (FK to QuestionType)
│   ├── game_round (FK to QuestionRound)
│   └── answers (many Answer objects via FK)
└── categories (many-to-many)

GameSession (for live play)
├── game (FK to Game)
└── teams (many SessionTeam)
    └── answers (many TeamAnswer)
```

### Key Models (quiz/models.py)
- **Game**: Top-level trivia game, can be password-protected
- **Question**: Individual trivia question with text, images/videos, points
- **Answer**: Answers for questions (supports multiple answer types: open-ended, ranking, matching)
- **Category**: Question categories (many-to-many with Games)
- **QuestionRound**: Organizes questions into rounds within a game
- **GameSession/SessionTeam/TeamAnswer**: Live game session tracking (API integration WIP)
- **GameResult/PlayerStats**: Analytics models for tracking performance

### Custom Fields (quiz/fields.py)
- **CloudFrontURLField**: Stores S3 paths, automatically prefixes CloudFront domain on retrieval
- **S3ImageField/S3VideoField**: File upload fields that automatically sync to S3 and update corresponding URL fields

### Views Structure
- **quiz/views.py**: Frontend views for displaying games, questions, answers, and analytics
- **quiz/api_views.py**: REST API endpoints for game sessions (designed for Go service integration)
- **quiz/session_views.py**: Frontend views for live game sessions
- **quiz/admin.py**: Extensive Django admin customization with inline answers, custom widgets, auto-numbering

### URL Patterns
Game display URLs follow the pattern:
```
/quiz/game/{game_id}/questions/round/{round_id}/questions/category/{category_id}/question/{question_id}/
/quiz/game/{game_id}/answers/round/{round_id}/answers/category/{category_id}/question/{question_id}/
```

## Working with Media Files

### Image/Video Upload Process
1. Files upload to S3 via custom S3ImageField/S3VideoField
2. File paths automatically stored in corresponding `*_url` fields (e.g., `question_image` → `question_image_url`)
3. CloudFrontURLField automatically prepends CloudFront domain when accessed
4. Admin interface includes custom widgets (S3ImageUploadWidget, S3VideoUploadWidget) in quiz/widgets.py

### Storage Configuration
- AWS S3 bucket: `django-trivia-app-bucket`
- CloudFront domain: `https://d1eomq1h9ixjmb.cloudfront.net`
- Storage backend: `storages.backends.s3boto3.S3Boto3Storage`
- Upload path helper: `quiz/upload_helpers.py` generates paths like `/{year}/{month}/{filename}`

## Admin Interface

### Key Features
- Questions can be created with inline Answer forms (min 1, max 10)
- Auto-incrementing question numbers: When creating a new question, the form automatically assigns the next available question_number for that game
- Category creation: Questions can create new categories on the fly via `new_category_name` field
- Custom JavaScript for conditional field display and category defaults (static/js/)
- Image/video upload widgets with S3 integration

### Creating Questions
1. Select a game
2. Question number auto-fills (or manually specify)
3. Either select existing category or enter `new_category_name`
4. Add inline answers (adjust display_order for ranking questions)
5. Upload images/videos via file fields (URLs auto-populate)

## Analytics System

The analytics views (quiz/analytics.py and quiz/views.py:analytics_view) display:
- **GameResult**: Individual game results by date, player, and round performance
- **PlayerStats**: Aggregate statistics including win rate, z-scores, and percentile rankings

Data is loaded from fixtures (db_initial_data.json) and can be filtered by:
- Player name search
- Game date
- Multiple games only (players with >1 game)

## Testing

### Test Coverage (quiz/tests.py)
- Model tests: Game, Question, Answer, QuestionRound creation and constraints
- View tests: Game list, overview, password protection, question navigation
- Unique constraint validation (question_number per game)
- Next question logic

When adding features, add corresponding tests following the existing pattern.

## Management Commands

Custom Django commands in quiz/management/commands/:
- `convert_image_urls.py`: Historical migration for image URL format
- `fix_image_urls.py`: URL cleanup and validation
- `migrate_answer_explanations.py`: Data migration for answer text fields

Run commands with: `uv run manage.py <command_name>`

## Database Operations

### Creating Fixtures
```bash
# Export all data
uv run manage.py dumpdata > db_initial_data.json

# Export specific app
uv run manage.py dumpdata quiz > quiz_data.json
```

### Loading Fixtures
```bash
# Load initial data (automatically runs in docker-compose)
uv run manage.py loaddata db_initial_data.json
```

## Code Style

- Uses Black for Python formatting (configured in pyproject.toml)
- Type hints used in views.py (HttpRequest, HttpResponse, JsonResponse, etc.)
- Follows Django conventions for model ordering, admin registration

## Production Deployment Notes

- Uses gunicorn WSGI server (see Dockerfile CMD)
- Nginx reverse proxy with SSL via Let's Encrypt (docker-compose.yml)
- Static files served from nginx
- Media files served from CloudFront CDN
- Database runs in separate postgres:14 container
- Environment uses `pub_trivia.settings` Django settings module
