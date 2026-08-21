# Design: Move Database Backups from Droplet-Local Disk to S3

## Problem

The `db-backup` service in `docker-compose.yml` currently writes weekly Postgres
dumps to a local bind mount (`./backups`) on the production droplet. This has
two problems:

1. **Resource cost.** The droplet is small, and local backup storage
   competes with the app for disk (and, previously, memory - the retention
   policy was already tightened once due to memory issues).
2. **False sense of safety.** A backup stored on the same host as the
   database it protects doesn't protect against the most common failure
   mode: losing the droplet itself. If the droplet fails, both the live
   database and its backups are lost together.

## Goals

- Backups land in S3, never touching the droplet's disk (not even
  transiently).
- Backup storage/access is isolated from the existing media bucket and its
  credentials, so a compromise or misconfiguration of one can't affect the
  other.
- Match the current backup cadence and retention (weekly, keep last 3) -
  this is a personal project with no business-critical data; the backup is
  a safety net for live-session data, not a compliance requirement.
- Minimal new code to own. Prefer configuration over custom scripts where a
  well-maintained off-the-shelf tool does the job.

## Non-goals

- Point-in-time recovery / WAL archiving. Weekly full dumps are sufficient
  for this project's risk profile.
- Automated restore tooling. Restores are rare and manual; a documented
  runbook is enough.
- Alerting/monitoring on backup failure. Out of scope for now (YAGNI) -
  revisit if this ever becomes more than a personal project.
- Testing a full restore as part of this change. The current maintainer
  recently performed an emergency backup/restore using this same mechanism
  and is confident the dump format is restorable, so a dry-run restore is
  not required before shipping this change.

## Design

### Architecture

```
[droplet]                                    [AWS]
 db (postgres container)  <---pg_dump---  backup-s3 container (cron-scheduled)
                                                |
                                                | gzip, streamed via aws-sdk
                                                v
                                    S3 bucket: trivia-app-db-backups
                                    (private, versioned, encrypted,
                                     lifecycle rule expires objects
                                     after ~21 days)
```

The backup container runs `pg_dump` against the `db` service on a cron
schedule, pipes the output through gzip, and streams it directly to S3. No
host volume is used - the dump never touches the droplet's disk.

### AWS setup (manual, outside git)

- New bucket, e.g. `trivia-app-db-backups`, same region as the existing
  media bucket (us-west-2) to avoid cross-region transfer costs/latency.
- Block all public access: enabled. Unlike the media bucket (which serves
  public content via CloudFront), this bucket has no legitimate public
  access case.
- Default encryption (SSE-S3): enabled.
- Versioning: enabled, as a cheap safety net against a buggy script
  overwriting or corrupting an object.
- Lifecycle rule: expire objects after ~21 days. This *is* the retention
  policy - weekly backups plus a 21-day expiry keeps roughly the last 3
  backups around, matching current `BACKUP_KEEP_WEEKS=3` behavior, without
  needing any custom pruning logic.
- New IAM user (e.g. `trivia-backup-writer`) with a policy scoped to
  `s3:PutObject`, `s3:GetObject`, and `s3:ListBucket` on this bucket only.
  This is a distinct identity from the existing media-upload credentials,
  so a leak or bug in one path can't reach the other bucket.

### Docker Compose changes

Replace the existing `db-backup` service definition:

- Remove `prodrigestivill/postgres-backup-local`, the `./backups` volume,
  and its bind mount.
- Add a maintained Postgres-to-S3 backup image (e.g.
  `eeshugerman/postgres-backup-s3`, the actively maintained fork of the
  older, now-unmaintained `schickling/postgres-backup-s3`), configured with:
  - `SCHEDULE`: weekly cron expression, matching the current `@weekly`
    cadence.
  - `S3_BUCKET`, `S3_PREFIX`, `S3_REGION`: point at the new bucket.
  - New, distinctly-named env vars for the dedicated backup IAM
    credentials (e.g. `BACKUP_AWS_ACCESS_KEY_ID` /
    `BACKUP_AWS_SECRET_ACCESS_KEY`), added to `.env` locally and to GitHub
    Secrets for deploy. These must not reuse the existing
    `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` names used by
    django-storages for media, to keep the two credential sets
    unambiguous and separately rotatable.
  - Existing `DB_*` values reused for the Postgres connection.

### Restore runbook

A short doc, `docs/BACKUP_RESTORE.md`, covering:

1. Download the relevant `.sql.gz` object from S3 (console or
   `aws s3 cp`).
2. `gunzip` it.
3. Restore into the `db` container via `psql`/`pg_restore`.

This is documented but not automated or tested as part of this change (see
Non-goals).

## Validation plan

This change is infra configuration rather than application code, so there's
no unit test. Validation is operational:

- Deploy the new service and manually trigger one backup run; confirm the
  object lands in the new S3 bucket.
- Spot-check that the backup IAM credentials are in fact restricted to the
  new bucket only (e.g. confirm an attempt to access the media bucket with
  them fails).

## Rollout notes

- Remove the old `./backups` directory from the droplet once the new
  mechanism is confirmed working, to reclaim disk space.
- Update `CLAUDE.md` / relevant docs if the backup mechanism is referenced
  elsewhere (currently only described inline in `docker-compose.yml`
  comments).
