# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<principles>
    <style>No emojis. No em dashes - use hyphens or colons instead.</style>
    
    <epistemology>
      Assumptions are the enemy. Never guess the numerical values - benchmark instead of estimating. 
      When uncertain, measure. Say "this needs to be measured" rather than inventing statistics.
    </epistemology>

    <interaction>
      Clarify unclear requests, then proceed autonomously. Only ask for help when scripts timeout, sudo is needed, or genuine blockers arise.
    </interaction>

    <ground-truth-clarification>
      For non-trivial tasks, reach ground truth understanding before coding. Simple tasks
      execute immediately. Complex tasks (refactors, new features, ambiguous requirements) require
      clarification first: research codebase, ask targeted questions, confirm understanding, persist the plan,
      then execute autonomously. 
    </ground-truth-clarification>

</principles>


## Project Overview

This is a Django web application for hosting trivia games at marleybuchman.com. The application supports three main modes of operation:

1. **Gallery Mode**: Browse and display trivia games, questions, and answers
2. **Live Session Mode**: Real-time multiplayer trivia with admin-controlled game flow, team scoring, and leaderboards
3. **Analytics Mode**: Player statistics, game results, and performance tracking

Tech stack:
- Django 4.2 with PostgreSQL database
- Django REST Framework for APIs
- AWS S3 + CloudFront for media storage
- Docker deployment with nginx proxy and Let's Encrypt SSL
- Google Sheets integration for analytics data import

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
- `DB_HOST`, `DB_PORT`: Database connection (localhost:5432 for local dev, db:5432 in Docker)
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: AWS credentials for S3

### Running Tests
The test suite is organized in `quiz/tests/` directory with comprehensive coverage.

```bash
# Run all tests
uv run manage.py test quiz

# Run specific test module
uv run manage.py test quiz.tests.test_models
uv run manage.py test quiz.tests.test_session_api
uv run manage.py test quiz.tests.test_integration

# Run specific test class
uv run manage.py test quiz.tests.test_models.GameModelTest
uv run manage.py test quiz.tests.test_session_api.AdminEndpointsTest

# Run with options
uv run manage.py test quiz.tests --verbosity=2  # Verbose
uv run manage.py test quiz.tests --parallel     # Parallel execution
uv run manage.py test quiz.tests --keepdb       # Keep test DB
```

Test modules:
- `test_models.py` - Core models (Game, Question, Answer, QuestionRound)
- `test_views.py` - Frontend views (gallery, questions, answers)
- `test_api_views.py` - Legacy REST API endpoints
- `test_serializers.py` - DRF serializers
- `test_fields.py` - Custom fields (S3, CloudFront)
- `test_analytics.py` - Analytics utilities
- `test_api.py` - DRF ViewSets
- `test_views_extended.py` - Extended view tests
- `test_integration.py` - End-to-end workflows
- `test_session_models.py` - GameSession, SessionTeam, TeamAnswer models
- `test_session_views.py` - Session frontend views
- `test_session_api.py` - Session API endpoints (comprehensive)
- `test_session_admin.py` - Session admin interface
- `test_session_integration.py` - Session end-to-end workflows

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
- **quiz/**: Core trivia application containing all models, views, APIs, and admin logic

### Data Model Hierarchy
```
Game (trivia event)
├── Questions (many)
│   ├── category (FK to Category)
│   ├── question_type (FK to QuestionType)
│   ├── game_round (FK to QuestionRound)
│   ├── answers (many Answer objects via FK)
│   └── sub_questions (many SubQuestion objects via FK)
└── categories (many-to-many)

GameSession (for live multiplayer play)
├── game (FK to Game)
├── rounds (many SessionRound)
│   └── status: PENDING → ACTIVE → LOCKED → SCORED
└── teams (many SessionTeam)
    └── answers (many TeamAnswer)
        └── answer_part (FK to SubQuestion, optional)
```

### Key Models (quiz/models.py)

**Core Trivia Models:**
- **Game**: Top-level trivia game with name, description, password protection, game_order
- **Question**: Individual question with text, answer_bank, images/videos, total_points
- **Answer**: Answers with text, points, display_order, correct_rank (for ranking questions)
- **SubQuestion**: Sub-parts of questions for detailed scoring (e.g., multi-part answers)
- **Category**: Question categories (many-to-many with Games)
- **QuestionRound**: Organizes questions into rounds within a game
- **QuestionType**: Types of questions (multiple choice, ranking, matching, etc.)

**Live Session Models:**
- **GameSession**: Live multiplayer session with 6-character code, admin token authentication
  - Status states: `LOBBY` → `PLAYING` ↔ `PAUSED` → `SCORING` → `REVIEWING` → `LEADERBOARD` → `COMPLETED`
  - Tracks current_question, current_round, max_teams, allow_late_joins, team_navigation_enabled
- **SessionTeam**: Teams with name, token, score, joined_at, last_seen, joined_late flag
- **SessionRound**: Round state tracking with status and timestamps (started_at, locked_at, scored_at)
- **TeamAnswer**: Team answers with text, lock status, admin-assigned points, answer_part for sub-questions

**Analytics Models:**
- **GameResult**: Individual game results by date, player, place, round scores, z-scores
- **PlayerStats**: Aggregate statistics including win rate, z-scores, percentile rankings

### Custom Fields (quiz/fields.py)
- **CloudFrontURLField**: Stores S3 paths, automatically prefixes CloudFront domain on retrieval
- **S3ImageField/S3VideoField**: File upload fields that sync to S3 and update corresponding URL fields

### File Structure
```
quiz/
├── models.py          # All data models
├── views.py           # Gallery and analytics views
├── session_views.py   # Live session frontend views
├── session_api.py     # Live session API endpoints (40+)
├── api.py             # DRF ViewSets (Game, Question)
├── api_views.py       # Legacy API endpoints
├── serializers.py     # DRF serializers
├── admin.py           # Django admin configuration
├── fields.py          # Custom S3/CloudFront fields
├── widgets.py         # Custom admin widgets
├── upload_helpers.py  # S3 upload path generation
├── analytics.py       # Google Sheets data import
└── tests/             # Test modules
```

## Live Session System

The live session system enables real-time multiplayer trivia games with admin control.

### Session Flow
1. **Host creates session** → Receives admin token and 6-character code
2. **Teams join** → Enter code, receive team token
3. **Admin starts game** → Status: LOBBY → PLAYING
4. **Admin controls questions** → Sets current question, teams submit answers
5. **Admin locks round** → Prevents further answer submissions
6. **Admin scores answers** → Reviews and assigns points
7. **Admin completes round** → Status: SCORING → REVIEWING
8. **Admin shows leaderboard** → Status: LEADERBOARD
9. **Repeat for each round** or complete game

### Session API Endpoints (quiz/session_api.py)

**Authentication**: Token-based via Bearer header
- Admin endpoints require `require_admin_token` decorator
- Team endpoints require `require_team_token` decorator
- Automatic session pause after 30s admin inactivity (`check_admin_timeout`)

**Public Endpoints:**
- `POST /quiz/api/sessions/create/` - Create session for a game
- `POST /quiz/api/sessions/join/` - Team joins with code
- `POST /quiz/api/sessions/rejoin/` - Team reconnects
- `GET /quiz/api/sessions/<code>/state/` - Get session state
- `POST /quiz/api/sessions/<code>/validate/` - Validate token access

**Admin Endpoints:**
- `POST /quiz/api/sessions/<code>/admin/start/` - Start the game
- `POST /quiz/api/sessions/<code>/admin/question/` - Set current question
- `POST /quiz/api/sessions/<code>/admin/toggle-team-navigation/` - Enable/disable team navigation
- `POST /quiz/api/sessions/<code>/admin/lock-round/` - Lock round answers
- `GET /quiz/api/sessions/<code>/admin/scoring-data/` - Get answers needing scoring
- `POST /quiz/api/sessions/<code>/admin/score/` - Score a team's answer
- `POST /quiz/api/sessions/<code>/admin/complete-round/` - Mark round complete
- `POST /quiz/api/sessions/<code>/admin/next-round/` - Advance to next round
- `POST /quiz/api/sessions/<code>/admin/leaderboard/` - Show leaderboard
- `GET /quiz/api/sessions/<code>/leaderboard/` - Get leaderboard data

**Team Endpoints:**
- `POST /quiz/api/sessions/<code>/team/answer/` - Submit answer
- `GET /quiz/api/sessions/<code>/team/answers/` - Get team's answers for round
- `GET /quiz/api/sessions/<code>/team/question/` - Get current question details
- `GET /quiz/api/sessions/<code>/team/results/` - Get final results

### Session Frontend
- `/quiz/play/` - Landing page (host or join)
- `/quiz/play/host/` - Admin creates session
- `/quiz/play/join/` - Teams enter code
- `/quiz/play/<code>/` - Live game view (single page, JS handles admin vs team UI)

## URL Patterns

### Gallery URLs
```
/quiz/gallery/                           # Game list
/quiz/game/<id>/overview/                # Game structure overview
/quiz/game/<id>/questions/round/<rid>/questions/category/<cid>/question/<qid>/
/quiz/game/<id>/answers/round/<rid>/answers/category/<cid>/question/<qid>/
/quiz/game/<id>/verify-password/         # Password verification
```

### API URLs
```
/quiz/api/games/                         # DRF: Game list
/quiz/api/games/<id>/questions/          # DRF: Game questions
/quiz/api/games/<id>/rounds/             # DRF: Game rounds
/quiz/api/questions/                     # DRF: Question list (filterable)
/quiz/api/rounds/<rid>/first-question/   # First question in round
/quiz/game/<id>/questions/               # All questions as JSON
```

### Session URLs (see Session API above)
```
/quiz/api/sessions/create/
/quiz/api/sessions/join/
/quiz/api/sessions/<code>/...
```

### Analytics
```
/quiz/analytics/                         # Analytics dashboard
```

## Working with Media Files

### Image/Video Upload Process
1. Files upload to S3 via custom S3ImageField/S3VideoField
2. File paths automatically stored in corresponding `*_url` fields
3. CloudFrontURLField automatically prepends CloudFront domain when accessed
4. Admin interface includes custom widgets (S3ImageUploadWidget, S3VideoUploadWidget)

### Storage Configuration
- AWS S3 bucket: `django-trivia-app-bucket` (us-west-2)
- CloudFront domain: `https://d1eomq1h9ixjmb.cloudfront.net`
- Storage backend: `storages.backends.s3boto3.S3Boto3Storage`

### Upload Path Helper (quiz/upload_helpers.py)
Generates S3 paths like `/{year}/{month}/{category}/{filename}`:
- Extracts month/year from game names (e.g., "January-2025")
- Sanitizes category names (removes spaces/quotes)

## Admin Interface

### Key Features
- Questions with inline Answer forms (min 1, max 10)
- Auto-incrementing question numbers per game
- Category creation on the fly via `new_category_name` field
- Custom JavaScript for conditional field display (static/js/)
- Image/video upload widgets with S3 integration
- GameSession admin with inline SessionTeam and SessionRound

### Creating Questions
1. Select a game
2. Question number auto-fills (or manually specify)
3. Either select existing category or enter `new_category_name`
4. Add inline answers (adjust display_order for ranking questions)
5. Upload images/videos via file fields (URLs auto-populate)

## Analytics System

### Data Sources
- **Google Sheets**: Game results and player data imported via gspread + oauth2client
- **quiz/analytics.py**: Reads sheets, calculates stats, bulk loads into database

### Views
- **analytics_view** (`/quiz/analytics/`): Displays GameResult and PlayerStats
- Filterable by player name, game date, multiple games only
- Shows win rates, z-scores, percentile rankings

## Dependencies (pyproject.toml)

**Core:**
- Django 4.2.18, PostgreSQL (psycopg2-binary)
- Django REST Framework 3.16.0, django-filter 25.1

**Storage & Media:**
- django-storages 1.14.6+, boto3 1.38.9+, Pillow 11.2.1+

**Features:**
- django-tinymce 4.1.0 (HTML editor for game descriptions)
- gspread 6.1.4 + oauth2client 4.1.3 (Google Sheets integration)

**Data:**
- pandas 2.1+, numpy 2.0.2+

**Deployment:**
- gunicorn 23.0.0+, python-dotenv 1.1.0+

**Development:**
- black 25.1.0 (code formatting)

## Management Commands

Custom Django commands in `quiz/management/commands/`:
- `convert_image_urls.py` - Historical migration for image URL format
- `fix_image_urls.py` - URL cleanup and validation
- `migrate_answer_explanations.py` - Data migration for answer text fields
- `update_image_urls.py` - URL updates

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
- Type hints used in views (HttpRequest, HttpResponse, JsonResponse, etc.)
- Follows Django conventions for model ordering, admin registration

## Production Deployment

### Docker Services (docker-compose.yml)
1. **nginx-proxy**: Reverse proxy with automatic SSL
2. **letsencrypt**: ACME companion for certificates
3. **nginx**: Static file server, reverse proxy to Django
4. **web**: Django application (gunicorn on port 8000)
5. **db**: PostgreSQL 14

### Configuration
- Domain: marleybuchman.com, www.marleybuchman.com
- Database: db:5432 (in container), localhost:5433 (from host)
- Static files: served from nginx
- Media files: served from CloudFront CDN
