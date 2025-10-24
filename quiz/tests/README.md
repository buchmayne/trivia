# Quiz Application Test Suite

This directory contains the comprehensive test suite for the trivia quiz application, with **173+ tests** organized into modular files.

## Directory Structure

```
tests/
├── __init__.py                 # Package initialization with test discovery info
├── test_models.py              # Core models (13 tests)
├── test_views.py               # Core views (13 tests)
├── test_api_views.py           # REST API endpoints (35 tests)
├── test_session_views.py       # Session views (15 tests)
├── test_serializers.py         # DRF serializers (30 tests)
├── test_fields.py              # Custom fields (20 tests)
├── test_session_models.py      # Session models (25 tests)
├── test_analytics.py           # Analytics (15 tests)
├── test_api.py                 # DRF ViewSets (20 tests)
├── test_views_extended.py     # Extended view tests (20 tests)
└── test_integration.py         # Integration tests (20 tests)
```

## Running Tests

### All Tests
```bash
# From project root
uv run manage.py test quiz.tests
```

### By Module
```bash
# Test specific functionality
uv run manage.py test quiz.tests.test_models
uv run manage.py test quiz.tests.test_api_views
uv run manage.py test quiz.tests.test_integration
```

### By Test Class
```bash
# Test a specific class
uv run manage.py test quiz.tests.test_models.GameModelTest
uv run manage.py test quiz.tests.test_api_views.CreateSessionAPITest
```

### By Test Method
```bash
# Test a single method
uv run manage.py test quiz.tests.test_models.GameModelTest.test_game_creation
```

### With Options
```bash
# Verbose output (shows each test name)
uv run manage.py test quiz.tests --verbosity=2

# Parallel execution (faster)
uv run manage.py test quiz.tests --parallel

# Keep test database (faster re-runs)
uv run manage.py test quiz.tests --keepdb

# No input prompts
uv run manage.py test quiz.tests --noinput
```

## Test Coverage by Module

### Core Functionality
- **test_models.py** - Game, Question, Answer, QuestionRound models
  - Model creation and validation
  - Unique constraints
  - Relationships (ManyToMany, ForeignKey)
  - Default values

- **test_views.py** - Frontend views
  - Game list and overview
  - Question and answer display
  - Password protection
  - Navigation between questions

### API Testing
- **test_api_views.py** - REST API endpoints
  - Session creation and management
  - Team management
  - Answer submission
  - Session finalization

- **test_api.py** - DRF ViewSets
  - GameViewSet with custom actions
  - QuestionViewSet with filtering
  - Pagination

- **test_serializers.py** - Data serialization
  - All DRF serializers
  - Validation logic
  - Nested serialization

### Session Management
- **test_session_models.py** - Session models
  - GameSession lifecycle
  - SessionTeam management
  - TeamAnswer submissions
  - Complete workflow tests

- **test_session_views.py** - Session frontend
  - Host dashboard
  - Team join flow
  - Live session views

### Advanced Features
- **test_fields.py** - Custom model fields
  - CloudFrontURLField (S3 path handling)
  - S3ImageField (image uploads)
  - S3VideoField (video uploads)

- **test_analytics.py** - Analytics system
  - GameResult and PlayerStats models
  - AnalyticsLoader utility
  - Data transformations

- **test_views_extended.py** - Edge cases
  - Multiple answers
  - Ranking questions
  - Multi-round statistics
  - Analytics filtering

- **test_integration.py** - End-to-end workflows
  - Complete game flow
  - Multi-round navigation
  - Password-protected games
  - API + frontend integration

## Writing New Tests

### Best Practices

1. **Organize by functionality** - Keep related tests together
2. **Use descriptive names** - Test names should explain what they verify
3. **Follow AAA pattern** - Arrange, Act, Assert
4. **Isolate tests** - Each test should be independent
5. **Use fixtures** - setUp() for common test data
6. **Test edge cases** - Don't just test the happy path

### Example Test Structure

```python
from django.test import TestCase
from quiz.models import Game, Question

class NewFeatureTest(TestCase):
    """Test description for the new feature"""

    def setUp(self):
        """Create common test data"""
        self.game = Game.objects.create(name="Test Game")

    def test_specific_behavior(self):
        """Test a specific behavior with descriptive name"""
        # Arrange - set up test conditions
        question = Question.objects.create(
            game=self.game,
            text="Test?",
            question_number=1
        )

        # Act - perform the action
        result = question.some_method()

        # Assert - verify the result
        self.assertEqual(result, expected_value)
```

### Where to Add Tests

- **Model tests** → `test_models.py` or `test_session_models.py`
- **View tests** → `test_views.py` or `test_views_extended.py`
- **API tests** → `test_api_views.py` or `test_api.py`
- **Serializer tests** → `test_serializers.py`
- **Integration tests** → `test_integration.py`

## Code Coverage

### Generate Coverage Report
```bash
# Install coverage
uv add --dev coverage

# Run tests with coverage
uv run coverage run --source='quiz' manage.py test quiz.tests

# View coverage report
uv run coverage report

# Generate HTML report
uv run coverage html

# Open in browser
open htmlcov/index.html
```

### Current Coverage
The test suite provides comprehensive coverage of:
- ✅ All models and their methods
- ✅ All views (frontend and API)
- ✅ All serializers
- ✅ Custom fields and utilities
- ✅ Complete user workflows

## Continuous Integration

These tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run Tests
  run: uv run manage.py test quiz.tests --parallel --noinput
```

## Troubleshooting

### Tests Run Slowly
- Use `--parallel` flag for parallel execution
- Use `--keepdb` to reuse test database
- Run specific test modules instead of entire suite

### Test Database Issues
```bash
# Drop and recreate test database
uv run manage.py test quiz.tests --noinput
```

### Import Errors
- Ensure you're running from project root
- Check that all test files import from `quiz.models`, not `.models`

## Next Steps

1. **Fix failing tests** - Address the ~30 known minor failures
2. **Increase coverage** - Add tests for uncovered code paths
3. **Add performance tests** - Test query optimization
4. **Add security tests** - Test authentication and permissions
