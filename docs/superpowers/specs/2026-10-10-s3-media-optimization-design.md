# S3 Media Optimization at Upload — Design

**Date:** 2026-10-10
**Status:** Approved for implementation; backfill safety amended 2026-10-24

**Execution safety amendment (2026-10-24):** The bucket is unversioned and is
shared by local authoring and production. The backfill must retain every
original object, use conditional content-addressed writes, and verify copies
before updating DB references. This supersedes the original delete-after-copy
proposal. A verified full-bucket snapshot now exists under gitignored
`media_backup/`; the user has existing database backups.

## Problem

Trivia game media is uploaded to S3 (served via CloudFront) through the Django
admin. The two artifact types are:

- **Screenshots** taken on macOS → stored as **PNG**, typically 1–5 MB each.
  Lossless, oversized for the display context (1080p projector + phones).
- **Videos** ripped from YouTube, edited, uploaded as MP4 (H.264). Encoding is
  done by hand and inconsistent; rips are sometimes uploaded raw (bloated).

The authoring workflow (uploading via the Django admin) must not change. All
optimization happens **behind the scenes** at upload time.

Non-goals: server-side video transcoding (rejected for cost/latency), Lambda@
Edge conversion (overkill), changing the upload path scheme, changing the admin
UI workflow.

## Scope

### 1. Image pipeline — full optimization at save

New module `quiz/image_processing.py`, single entry point:

```
optimize_image(file: File) -> (bytes, new_filename)
```

Rules:

- **Always convert to WebP, quality 80.** Applies to PNG, JPEG, and any other
  decodable raster format. One uniform output format going forward.
- **Downscale to max 1920px on the long edge**, only when larger. Never upscale.
- **Preserve alpha.** WebP supports it; PNG screenshots with transparency stay
  intact.
- **Animated images (GIF) pass through unchanged.** Converting would flatten
  them to a static frame. Log a warning; do not convert.
- **Failure mode: pass through.** If Pillow cannot decode/process a file,
  upload the original untouched and log a warning. A processing bug must never
  block a save or lose a file.
- The upload filename extension is rewritten to `.webp` (e.g.
  `screenshot.png` → `screenshot.webp`), so S3 paths become
  `game-N/Category/screenshot.webp`. `CloudFrontURLField` stores whatever path
  was uploaded — no change needed there.

Wiring: optimization runs inside the save path of `S3ImageField` (via
`pre_save` / storage handoff) so it applies to **every** upload route — admin
UI, scripts, fixtures — not just the admin widget.

### 2. Video validation — no transcoding, no ffmpeg

`S3VideoField` gains a server-side check at save:

- **Reject with `ValidationError`** (surfaced inline in the admin):
  1. Uploaded file is not a video content type.
  2. File size exceeds `MAX_VIDEO_UPLOAD_MB` (**default 100**, Django setting).
- No parsing, no new dependencies, no added request latency — file size and
  content type are free.
- The rejection message tells the author what to do:
  "Video exceeds 100 MB. Optimize locally before uploading
  (ffmpeg CRF 21, 1080p cap, `+faststart`)."
- Properly optimized trivia clips are 1–10 MB, so 100 MB only ever catches raw
  YouTube rips, never legitimate files.

### 3. Configuration

| Setting | Default | Purpose |
|---|---|---|
| `MAX_VIDEO_UPLOAD_MB` | `100` | Video size rejection threshold |
| `IMAGE_MAX_DIMENSION_PX` | `1920` | Long-edge cap for images |
| `IMAGE_WEBP_QUALITY` | `80` | WebP encoder quality |

### 4. Files touched

| File | Change |
|---|---|
| `quiz/image_processing.py` | **new** — `optimize_image()` (WebP convert + downscale + passthrough rules) |
| `quiz/fields.py` | hook `optimize_image` into `S3ImageField`; add validation to `S3VideoField` |
| `pub_trivia/settings.py` | the three settings above |
| `quiz/tests/test_fields.py` (+ maybe `test_image_processing.py`) | tests (see below) |
| `docs/CONTENT_WORKFLOW.md` | document behavior + pointer to the future local video script |

### 5. Tests

Image pipeline:
- PNG → WebP with size reduction and correct extension rename.
- Oversize image downscaled to 1920px long edge; small image untouched.
- Alpha preserved (WebP output has alpha channel).
- JPEG → WebP.
- Animated GIF passes through unchanged.
- Corrupt/unreadable file passes through unchanged (no exception raised).
- Content-type / size unchanged for under-threshold videos.

Video validation:
- Oversize video (> threshold) raises `ValidationError`.
- Non-video content type raises `ValidationError`.
- Legit-size MP4 passes.

Backfill (below):
- Dry run makes zero writes (S3 and DB).
- Convert path: conditionally upload, verify full bytes, atomically update DB.
- No original deletes or overwrites, even on failure or retry.
- Idempotency: `.webp` references skipped; existing matching copies reused.
- Failed verification leaves DB references unchanged.
- Shared references update together; concurrent edits are not overwritten.
- External URLs left alone; failed attempts count toward batch limits.
- Failures are reported with nonzero exit, even while other sources continue.

## Backfill: `optimize_existing_images` management command

**Risk context:** originals were initially stored only in S3. A verified local
snapshot now contains all 403 current objects, with exact key mappings and
checksums. The user also has database backups. Regardless of redundancy, the
command must never delete or overwrite originals: production and historical
fixtures/backups may reference them even after the local database changes.

### Preconditions and recovery

- Keep the full-bucket snapshot unchanged. No bucket settings are changed.
- Versioning is recommended generally, but is not required by this additive
  command. The unsafe unversioned-delete override is removed.
- Optionally, `--download-originals` mirrors referenced sources (including
  WebP) to `media_backup/referenced-originals/`, preventing path traversal and
  refusing to overwrite differing local bytes. This is not a full-bucket
  snapshot. Undecodable originals must still be backed up byte-for-byte.
- JSON reports preserve old/new keys and affected DB rows. Rollback can use
  those mappings or an existing DB backup, since original keys remain live.

### Command behavior

```
uv run manage.py optimize_existing_images            # dry run (default)
uv run manage.py optimize_existing_images --apply    # actually convert
uv run manage.py optimize_existing_images --download-originals
```

Default is **dry run**: enumerate and report planned conversions, write
nothing to S3 or the DB.

Targets: the four image fields across two models —
`Question.question_image`, `Question.answer_image`, `Answer.question_image`,
`Answer.answer_image` (follows the `_url` fields, which are the source of
truth for what's actually referenced).

Per-source algorithm (in `--apply` mode):

1. Enumerate all four field slots. Normalize own CloudFront URLs to S3 keys;
   skip external URLs. Use the URL field as the authoritative reference, with
   file-field fallback when the URL is empty. Group shared source keys.
2. Skip already-WebP references. Download each distinct source once and run
   the same `optimize_image()` used for uploads. Pass-through leaves references
   unchanged.
3. Validate the encoded output. Address it as
   `optimized/<sha256-of-encoded-bytes>.webp`, avoiding basename collisions.
4. Create the destination with `If-None-Match: *`, `Content-Type: image/webp`,
   and a SHA-256 upload checksum. Never replace an existing object. If the key
   exists already, verify it instead of trusting it.
5. GET the uploaded/existing copy and verify content type, size, and SHA-256
   against the optimized bytes. No DB references change before verification.
6. Lock affected rows and compare references against their enumerated values.
   Atomically update the file and URL fields of every shared reference. Abort
   the group if any reference changed concurrently.
7. Retain the original indefinitely. Cleanup is a separate future task, only
   after auditing every consuming environment and obtaining explicit approval.

Crash safety: a crash may leave a verified but unreferenced optimized object,
never a missing original. Re-running reuses content-addressed objects safely.
The local command changes only its connected database. Export updated local
content to the deployment fixture, but do not commit or deploy automatically.

Batch behavior:
- `--limit N` attempts at most N distinct non-WebP S3 sources, including failed
  attempts. Use a five-source batch and verify CloudFront delivery first.
- Continue past per-source failures; exit nonzero if any failed.
- `--report PATH` writes a JSON audit report (old/new keys, affected rows,
  sizes, output hashes, failures) before/after each source using atomic local
  report replacement. Use gitignored `media_backup/` for reports.
- Skip already-WebP references on repeat runs; retries verify and reuse copies.
- Export changed references for the normal human-reviewed content deployment.

### Out of scope

- Local video optimization script (`make optimize-videos`, ffmpeg wrapper) —
  the author will build this separately; validation thresholds are sized so
  nothing legitimate gets blocked in the meantime.
- Server-side video transcoding.
- Retroactive video re-encoding of existing S3 videos.
