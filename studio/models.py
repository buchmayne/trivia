from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Challenge(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"

    working_title = models.CharField(max_length=255, blank=True)
    rough_notes = models.TextField(blank=True)
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="challenges",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=~(Q(working_title="") & Q(rough_notes="")),
                name="studio_challenge_has_idea",
            )
        ]

    def clean(self):
        super().clean()
        if not self.working_title.strip() and not self.rough_notes.strip():
            raise ValidationError("Enter a working title or rough notes.")

    @property
    def total_points(self):
        return sum(task.max_points for task in self.tasks.all())

    def __str__(self):
        return self.working_title or self.rough_notes[:60]


class Task(models.Model):
    class Format(models.TextChoices):
        FREE_TEXT = "free_text", "Free text"
        SINGLE_CHOICE = "single_choice", "Choose one"

    challenge = models.ForeignKey(
        Challenge, on_delete=models.CASCADE, related_name="tasks"
    )
    order = models.PositiveIntegerField()
    format = models.CharField(
        max_length=32, choices=Format.choices, default=Format.FREE_TEXT
    )
    max_points = models.PositiveIntegerField(default=1)
    evaluation_key = models.JSONField(default=dict, blank=True)
    response_pool = models.ForeignKey(
        "ResponsePool",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="used_by_tasks",
    )

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["challenge", "order"], name="studio_task_position"
            )
        ]

    def __str__(self):
        return f"{self.challenge} · Task {self.order}"


class ResponsePool(models.Model):
    task = models.OneToOneField(
        Task, on_delete=models.CASCADE, related_name="owned_pool"
    )

    def __str__(self):
        return f"Options for {self.task}"


class ResponseItem(models.Model):
    pool = models.ForeignKey(
        ResponsePool, on_delete=models.CASCADE, related_name="items"
    )
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["pool", "order"], name="studio_item_position"
            )
        ]

    def __str__(self):
        prompt = self.content_blocks.filter(phase="prompt").first()
        return prompt.text[:80] if prompt else f"Option {self.order}"


class ContentBlock(models.Model):
    class Phase(models.TextChoices):
        PROMPT = "prompt", "Prompt"
        REVEAL = "reveal", "Reveal"

    challenge = models.ForeignKey(
        Challenge,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="content_blocks",
    )
    task = models.ForeignKey(
        Task,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="content_blocks",
    )
    item = models.ForeignKey(
        ResponseItem,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="content_blocks",
    )
    phase = models.CharField(max_length=10, choices=Phase.choices)
    order = models.PositiveIntegerField()
    text = models.TextField()

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (
                        Q(challenge__isnull=False)
                        & Q(task__isnull=True)
                        & Q(item__isnull=True)
                    )
                    | (
                        Q(challenge__isnull=True)
                        & Q(task__isnull=False)
                        & Q(item__isnull=True)
                    )
                    | (
                        Q(challenge__isnull=True)
                        & Q(task__isnull=True)
                        & Q(item__isnull=False)
                    )
                ),
                name="studio_block_one_owner",
            ),
            models.UniqueConstraint(
                fields=["challenge", "phase", "order"],
                name="studio_challenge_block_position",
            ),
            models.UniqueConstraint(
                fields=["task", "phase", "order"], name="studio_task_block_position"
            ),
            models.UniqueConstraint(
                fields=["item", "phase", "order"], name="studio_item_block_position"
            ),
        ]

    def clean(self):
        super().clean()
        if (
            sum(
                owner is not None
                for owner in (self.challenge_id, self.task_id, self.item_id)
            )
            != 1
        ):
            raise ValidationError(
                "Content must belong to exactly one challenge, task or item."
            )
        if not self.text.strip():
            raise ValidationError({"text": "Enter text for this block."})


class Game(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.name


class GameRound(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="rounds")
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["game", "order"], name="studio_round_position"
            )
        ]

    def __str__(self):
        return f"{self.game} · {self.name}"


class Placement(models.Model):
    round = models.ForeignKey(
        GameRound, on_delete=models.CASCADE, related_name="placements"
    )
    challenge = models.ForeignKey(
        Challenge, on_delete=models.CASCADE, related_name="placements"
    )
    order = models.PositiveIntegerField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["round", "order"], name="studio_placement_position"
            )
        ]

    def __str__(self):
        return f"{self.round} · {self.challenge}"
