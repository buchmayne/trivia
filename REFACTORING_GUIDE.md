# Refactoring Guide

With the comprehensive test suite now in place, you're ready to refactor your trivia application with confidence. This guide outlines the best practices and workflow for refactoring.

## Why Refactor Now?

Your test suite provides:
- **173+ tests** covering all major functionality
- **Regression detection** - Tests will catch when you break something
- **Confidence** - Refactor freely knowing tests verify behavior
- **Documentation** - Tests show how code should behave

## Refactoring Workflow

### 1. Run Tests Before Starting
```bash
# Verify all tests pass (or note which ones fail)
uv run manage.py test quiz.tests --noinput

# Run with verbose output to see what's being tested
uv run manage.py test quiz.tests --verbosity=2
```

### 2. Make Small, Focused Changes
- Refactor one thing at a time
- Commit after each successful refactor
- Run tests after each change

### 3. Run Relevant Tests Frequently
```bash
# If refactoring models
uv run manage.py test quiz.tests.test_models

# If refactoring API views
uv run manage.py test quiz.tests.test_api_views

# If refactoring serializers
uv run manage.py test quiz.tests.test_serializers
```

### 4. Run Full Test Suite Before Committing
```bash
# Run all tests
uv run manage.py test quiz.tests --noinput

# Parallel for speed
uv run manage.py test quiz.tests --parallel --noinput
```

## Common Refactoring Tasks

### Refactoring Models

**Safe to change:**
- Internal method implementations
- Adding new methods
- Optimizing queries
- Adding indexes

**Test after changing:**
```bash
uv run manage.py test quiz.tests.test_models
uv run manage.py test quiz.tests.test_session_models
uv run manage.py test quiz.tests.test_integration
```

**Example: Optimizing Question queries**
```python
# Before
def get_round_questions(game_id, round_id):
    return Question.objects.filter(
        game_id=game_id,
        game_round_id=round_id
    )

# After (optimized)
def get_round_questions(game_id, round_id):
    return Question.objects.filter(
        game_id=game_id,
        game_round_id=round_id
    ).select_related('category', 'question_type').prefetch_related('answers')

# Run tests to verify behavior unchanged
uv run manage.py test quiz.tests.test_models.QuestionModelTest
```

### Refactoring Views

**Safe to change:**
- View logic organization
- Moving code to helper functions
- Changing template context structure (update templates accordingly)
- Query optimization

**Test after changing:**
```bash
uv run manage.py test quiz.tests.test_views
uv run manage.py test quiz.tests.test_views_extended
uv run manage.py test quiz.tests.test_integration
```

**Example: Extract reusable logic**
```python
# Before - duplicated code
def game_overview(request, game_id):
    game = Game.objects.get(id=game_id)
    rounds = QuestionRound.objects.filter(
        questions__game=game
    ).distinct().order_by('round_number')
    # ... more code

def another_view(request, game_id):
    game = Game.objects.get(id=game_id)
    rounds = QuestionRound.objects.filter(
        questions__game=game
    ).distinct().order_by('round_number')
    # ... duplicated

# After - extracted helper
def get_game_rounds(game):
    """Get all rounds for a game, ordered by round number"""
    return QuestionRound.objects.filter(
        questions__game=game
    ).distinct().order_by('round_number')

def game_overview(request, game_id):
    game = Game.objects.get(id=game_id)
    rounds = get_game_rounds(game)
    # ... rest of code

def another_view(request, game_id):
    game = Game.objects.get(id=game_id)
    rounds = get_game_rounds(game)
    # ... rest of code
```

### Refactoring API Endpoints

**Safe to change:**
- Validation logic
- Permission classes
- Serializer implementations
- Response formatting

**Test after changing:**
```bash
uv run manage.py test quiz.tests.test_api_views
uv run manage.py test quiz.tests.test_api
uv run manage.py test quiz.tests.test_serializers
```

### Refactoring Database Schema

**CAUTION:** Schema changes require migrations

**Workflow:**
1. Run tests to establish baseline
2. Make model changes
3. Create migration: `uv run manage.py makemigrations`
4. Run migration: `uv run manage.py migrate`
5. Update affected tests
6. Run full test suite

```bash
# Example: Adding a field
# 1. Edit model
class Game(models.Model):
    # ... existing fields
    max_players = models.IntegerField(default=50)  # New field

# 2. Create migration
uv run manage.py makemigrations

# 3. Run migration
uv run manage.py migrate

# 4. Run tests
uv run manage.py test quiz.tests --noinput
```

## Fixing Failing Tests

### Current Known Failures (~30 tests)

Most failures are minor and fall into categories:

1. **Custom field tests** - Mock expectations don't match implementation
2. **API permission tests** - Need authentication setup
3. **Integration edge cases** - Navigation across round boundaries

### Workflow for Fixing Tests

```bash
# 1. Run specific failing test
uv run manage.py test quiz.tests.test_fields.S3ImageFieldTest.test_generate_filename_removes_leading_slash --verbosity=2

# 2. Read the error message carefully
# 3. Fix either the test or the code
# 4. Verify fix
uv run manage.py test quiz.tests.test_fields

# 5. Run full suite to check for side effects
uv run manage.py test quiz.tests --noinput
```

## Refactoring Priorities

### High Priority (Safe, High Impact)

1. **Extract duplicate code** - Many views have similar patterns
2. **Optimize queries** - Use select_related/prefetch_related
3. **Add type hints** - Some files already have them, add to rest
4. **Improve error handling** - Use consistent patterns

### Medium Priority (Moderate Risk)

1. **Consolidate similar views** - Use class-based views
2. **Refactor admin forms** - Simplify QuestionAdminForm
3. **Improve serializer organization** - Group related serializers
4. **Add caching** - For expensive queries

### Low Priority (Higher Risk)

1. **Change URL patterns** - Requires updating frontend
2. **Modify API contracts** - May break external clients
3. **Change model relationships** - Requires careful migration
4. **Restructure apps** - Major architectural change

## Code Coverage Analysis

### Generate Coverage Report
```bash
# Install coverage
uv add --dev coverage

# Run with coverage
uv run coverage run --source='quiz' manage.py test quiz.tests

# View report
uv run coverage report

# HTML report
uv run coverage html
open htmlcov/index.html
```

### Identify Gaps
Look for:
- Functions with 0% coverage
- Edge cases not tested
- Error handling paths
- Complex business logic

### Add Missing Tests
```python
# If coverage shows untested function
def uncovered_function(x, y):
    if x > y:
        return "greater"
    return "less"

# Add test
class NewTest(TestCase):
    def test_uncovered_function_greater(self):
        result = uncovered_function(5, 3)
        self.assertEqual(result, "greater")

    def test_uncovered_function_less(self):
        result = uncovered_function(2, 8)
        self.assertEqual(result, "less")
```

## Performance Optimization

### Identify Slow Tests
```bash
# Run with timing
uv run manage.py test quiz.tests --verbosity=2 --timing
```

### Optimize Database Queries
```python
# Before
def get_questions_with_answers(game_id):
    questions = Question.objects.filter(game_id=game_id)
    for q in questions:
        answers = q.answers.all()  # N+1 query problem!

# After
def get_questions_with_answers(game_id):
    questions = Question.objects.filter(
        game_id=game_id
    ).prefetch_related('answers')
    for q in questions:
        answers = q.answers.all()  # Single query
```

### Test Performance Improvements
```python
from django.test import TestCase
from django.test.utils import override_settings
from django.db import connection
from django.test.utils import CaptureQueriesContext

class PerformanceTest(TestCase):
    def test_query_count(self):
        """Verify optimized queries"""
        with CaptureQueriesContext(connection) as queries:
            get_questions_with_answers(self.game.id)

        # Should be 2 queries (1 for questions, 1 for prefetch)
        self.assertLessEqual(len(queries), 2)
```

## Git Workflow

### Recommended Branch Strategy
```bash
# Create feature branch for refactoring
git checkout -b refactor/optimize-question-queries

# Make changes and run tests
uv run manage.py test quiz.tests --noinput

# Commit with descriptive message
git add .
git commit -m "Refactor: Optimize question query in get_round_questions

- Add select_related for category and question_type
- Add prefetch_related for answers
- Reduces queries from N+1 to 2
- All tests passing"

# Push and create PR
git push origin refactor/optimize-question-queries
```

### Commit Message Template
```
Refactor: <brief description>

<What changed>
- Bullet point 1
- Bullet point 2

<Why it changed>
- Reason 1
- Reason 2

<Test results>
- All tests passing
- Added/Updated tests for X
- Performance improved by Y%
```

## Next Steps

1. **Fix the ~30 failing tests** - Get to 100% passing
2. **Run coverage analysis** - Identify gaps
3. **Start small** - Refactor one file at a time
4. **Document changes** - Update CLAUDE.md as you go
5. **Consider CI/CD** - Automate test runs on push

## Resources

- [Test Documentation](quiz/tests/README.md)
- [Test Suite Summary](TEST_SUITE_SUMMARY.md)
- [Development Guide](CLAUDE.md)

## Questions to Ask Before Refactoring

1. ✅ Do I have tests covering this code?
2. ✅ Are all tests currently passing?
3. ✅ Do I understand what this code does?
4. ✅ Have I run the relevant tests?
5. ✅ Is my change small and focused?
6. ✅ Can I easily revert if something breaks?

If you answer "yes" to all, you're ready to refactor safely!
