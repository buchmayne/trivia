from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from quiz.models import GameSession


class Command(BaseCommand):
    help = "Delete old game sessions to prevent database bloat."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Delete sessions older than N days (default: 30)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )
        parser.add_argument(
            "--include-active",
            action="store_true",
            help="Also delete active/non-completed sessions older than N days",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]
        include_active = options["include_active"]

        cutoff = timezone.now() - timedelta(days=days)

        # Build query for sessions to delete
        sessions = GameSession.objects.filter(created_at__lt=cutoff)

        if not include_active:
            # Only delete completed or abandoned sessions
            sessions = sessions.filter(status__in=["COMPLETED", "LOBBY"])

        count = sessions.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No sessions to clean up."))
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Would delete {count} sessions older than {days} days"
                )
            )
            # Show breakdown by status
            status_counts = {}
            for session in sessions:
                status_counts[session.status] = status_counts.get(session.status, 0) + 1
            for status, c in sorted(status_counts.items()):
                self.stdout.write(f"  {status}: {c}")
            return

        # Delete sessions - cascades to SessionTeam, SessionRound, TeamAnswer
        deleted_count, deleted_details = sessions.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {count} sessions older than {days} days"
            )
        )
        for model, c in deleted_details.items():
            self.stdout.write(f"  {model}: {c}")
