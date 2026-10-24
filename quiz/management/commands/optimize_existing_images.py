"""Additive backfill: verify new WebP copies before changing local DB references.

Never delete or overwrite originals: production, fixtures, shared references,
and database backups may still need them. New objects are content-addressed
and created conditionally, so retries and same-basename sources are safe.
"""

import base64
from collections import defaultdict
from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
import logging
from pathlib import Path
from urllib.parse import urlsplit

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image

from quiz.image_processing import optimize_image
from quiz.models import Answer, Question
from quiz.storage import S3MediaStorage

logger = logging.getLogger(__name__)
IMAGE_FIELDS = [
    (Question, "question_image"),
    (Question, "answer_image"),
    (Answer, "question_image"),
    (Answer, "answer_image"),
]


@dataclass(frozen=True)
class Reference:
    model: type
    field: str
    pk: int
    file_name: str
    url: str

    def describe(self):
        return {"model": self.model._meta.label, "pk": self.pk, "field": self.field}


def source_key(value):
    """Normalize this app's CloudFront URLs, but never treat external URLs as keys.

    Some legacy external URLs have themselves been prefixed by
    CloudFrontURLField.from_db_value; detect those after stripping the prefix.
    """
    domain = settings.AWS_CLOUDFRONT_DOMAIN.rstrip("/")
    if value.startswith(domain + "/"):
        value = value[len(domain) + 1 :]
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        return None
    return value.lstrip("/") or None


def ensure_verified_copy(storage, key, data):
    """Conditionally create a WebP, then read it back and verify exact bytes.

    A pre-existing destination must match too: do not trust HEAD alone or a
    coincidentally correct extension. Return True for a newly uploaded object.
    """
    client = storage.connection.meta.client
    s3_key = "/".join(part for part in (storage.location.strip("/"), key) if part)
    digest = hashlib.sha256(data).digest()
    parameters = dict(storage.get_object_parameters(key))
    parameters.update(
        ContentType="image/webp",
        ChecksumSHA256=base64.b64encode(digest).decode("ascii"),
    )
    uploaded = True
    try:
        client.put_object(
            Bucket=storage.bucket_name,
            Key=s3_key,
            Body=data,
            IfNoneMatch="*",
            **parameters,
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in ("PreconditionFailed", "412"):
            raise
        uploaded = False

    response = client.get_object(Bucket=storage.bucket_name, Key=s3_key)
    body = response["Body"]
    try:
        if response["ContentLength"] != len(data):
            raise ValueError(f"Verification failed: incorrect size for {key}")
        if response.get("ContentType") != "image/webp":
            raise ValueError(f"Verification failed: incorrect content type for {key}")
        saved_hash = hashlib.sha256()
        while chunk := body.read(1024 * 1024):
            saved_hash.update(chunk)
        if saved_hash.digest() != digest:
            raise ValueError(f"Verification failed: checksum mismatch for {key}")
    finally:
        body.close()
    return uploaded


class Command(BaseCommand):
    help = "Add verified WebP copies and update local image references. Never deletes originals."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Default is dry run.")
        parser.add_argument(
            "--limit", type=int, help="Attempt at most N distinct sources."
        )
        parser.add_argument(
            "--report", help="Write a JSON audit/mapping report locally."
        )
        parser.add_argument(
            "--download-originals",
            action="store_true",
            help="Mirror referenced objects to media_backup/referenced-originals/.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        if limit is not None and limit <= 0:
            raise CommandError("--limit must be a positive integer")
        if options["apply"] and options["download_originals"]:
            raise CommandError("Use --apply and --download-originals separately")

        groups, external = self._enumerate_targets()
        pending = [key for key in groups if not key.lower().endswith(".webp")]
        selected = pending if limit is None else pending[:limit]
        self.stdout.write(
            f"Found {sum(map(len, groups.values()))} S3 image references "
            f"({len(groups)} distinct keys); {len(groups) - len(pending)} already WebP; "
            f"{len(external)} external references left unchanged."
        )
        storage = S3MediaStorage()
        if options["download_originals"]:
            self._download_originals(groups, storage)
            return
        if not options["apply"]:
            for key in selected[:20]:
                self.stdout.write(f"  would convert: {key}")
            self.stdout.write(
                f"Dry run: {len(selected)} distinct sources would be converted; "
                "no S3 or DB writes. Originals will be retained."
            )
            return

        report = {
            "status": "in_progress",
            "originals_retained": True,
            "bucket": storage.bucket_name,
            "database_host": settings.DATABASES["default"].get("HOST", ""),
            "external_references": external,
            "results": [],
        }
        self._write_report(options["report"], report)
        for key in selected:
            try:
                result = self._convert_group(key, groups[key], storage)
            except Exception as exc:
                logger.exception("Backfill failed for %s (original retained)", key)
                result = {"status": "failed", "old_key": key, "error": str(exc)}
            report["results"].append(result)
            self._write_report(options["report"], report)

        counts = defaultdict(int)
        for result in report["results"]:
            counts[result["status"]] += 1
        report["status"] = "failed" if counts["failed"] else "complete"
        report["counts"] = dict(counts)
        self._write_report(options["report"], report)
        self.stdout.write(
            f"Backfill: {counts['converted']} distinct sources converted, "
            f"{counts['passed_through']} passed through, {counts['failed']} failed. "
            "All originals retained; only the connected database's references updated."
        )
        if counts["failed"]:
            raise CommandError(
                "Some images failed; see the report/logs. Originals are unchanged."
            )

    def _enumerate_targets(self):
        groups = defaultdict(list)
        external = []
        for model, field in IMAGE_FIELDS:
            for pk, file_name, url in model.objects.order_by("pk").values_list(
                "pk", field, f"{field}_url"
            ):
                value = url or file_name
                if not value:
                    continue
                ref = Reference(model, field, pk, file_name or "", url or "")
                key = source_key(value)
                if key is None:
                    external.append(dict(ref.describe(), url=value))
                else:
                    groups[key].append(ref)
        return groups, external

    def _convert_group(self, old_key, refs, storage):
        with storage.open(old_key, "rb") as f:
            original = f.read()
        data, _ = optimize_image(original, old_key)
        result = {
            "old_key": old_key,
            "references": [r.describe() for r in refs],
            "source_bytes": len(original),
        }
        if data == original:
            return dict(result, status="passed_through")
        with Image.open(BytesIO(data)) as image:
            if image.format != "WEBP":
                raise ValueError("Optimizer did not produce WebP")
            image.load()
        digest = hashlib.sha256(data).hexdigest()
        new_key = f"optimized/{digest}.webp"
        uploaded = ensure_verified_copy(storage, new_key, data)

        # Group all shared references atomically. Detect edits since enumeration
        # rather than clobbering concurrent authoring. Remote verification has
        # already succeeded before the first DB write.
        with transaction.atomic():
            for ref in refs:
                current = ref.model.objects.select_for_update().get(pk=ref.pk)
                current_file = getattr(current, ref.field).name or ""
                current_url = getattr(current, f"{ref.field}_url") or ""
                if current_file != ref.file_name or current_url != ref.url:
                    raise ValueError(
                        f"Reference changed during backfill: {ref.describe()}"
                    )
                ref.model.objects.filter(pk=ref.pk).update(
                    **{ref.field: new_key, f"{ref.field}_url": new_key}
                )
        return dict(
            result,
            status="converted",
            new_key=new_key,
            optimized_bytes=len(data),
            sha256=digest,
            newly_uploaded=uploaded,
        )

    def _write_report(self, filename, report):
        if filename:
            path = Path(filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + ".tmp")
            temporary.write_text(json.dumps(report, indent=2) + "\n")
            temporary.replace(path)

    def _download_originals(self, groups, storage):
        root = Path("media_backup/referenced-originals").resolve()
        failures = []
        for key in groups:
            try:
                dest = root / key
                dest.resolve().relative_to(root)
                with storage.open(key, "rb") as f:
                    data = f.read()
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists() and dest.read_bytes() != data:
                    raise ValueError(
                        "Existing local backup differs; refusing to overwrite"
                    )
                with dest.open("ab") as out:
                    if out.tell() == 0:
                        out.write(data)
                if dest.read_bytes() != data:
                    raise ValueError("Local mirror verification failed")
            except Exception as exc:
                failures.append(key)
                self.stderr.write(f"Mirror failed for {key}: {exc}")
        self.stdout.write(
            f"Mirror: {len(groups) - len(failures)} verified, {len(failures)} failed."
        )
        if failures:
            raise CommandError("Some originals could not be mirrored")
