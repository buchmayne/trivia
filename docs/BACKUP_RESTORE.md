# Database Backup and Restore

## How backups work

The `db-backup` service in `docker-compose.yml` runs `pg_dump` against the
`db` container on a weekly schedule, gzips the output, and streams it
directly to a dedicated, private S3 bucket. The dump never touches the
droplet's disk, not even transiently.

- Bucket: value of `BACKUP_S3_BUCKET` (private, versioned, encrypted)
- Prefix: `backups/`
- Schedule: weekly (`SCHEDULE=@weekly` in `docker-compose.yml`)
- Retention: enforced by an S3 lifecycle rule on the bucket that expires
  objects after ~21 days. There is no local retention/pruning logic in this
  repo - if you need to change how long backups are kept, change the
  lifecycle rule on the bucket, not this repo.
- Credentials: a dedicated IAM user scoped to only this bucket
  (`s3:PutObject`, `s3:GetObject`, `s3:ListBucket`). These are intentionally
  separate from the `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` credentials
  used for media storage, so a problem with one can't affect the other.

## Restoring a backup

1. **Find the backup you want.**
   ```bash
   aws s3 ls s3://$BACKUP_S3_BUCKET/backups/
   ```

2. **Download and decompress it.**
   ```bash
   aws s3 cp s3://$BACKUP_S3_BUCKET/backups/<object-key> ./restore.sql.gz
   gunzip restore.sql.gz
   ```

3. **Restore into the running `db` container.**

   This will overwrite the target database - make sure you're restoring
   into the database you intend to (and consider taking a fresh backup of
   the current state first, if it's not already what you're replacing).

   ```bash
   cat restore.sql | docker-compose exec -T db psql -U "$DB_USER" -d "$DB_NAME"
   ```

   If the dump was taken with `pg_dump -Fc` (custom format) rather than
   plain SQL, use `pg_restore` instead:
   ```bash
   docker-compose exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists < restore.sql
   ```

4. **Verify the app is functioning** against the restored data before
   considering the restore complete.

## Notes

- This procedure is manual by design - restores are rare, and the goal is a
  reliable, well-understood process rather than automation for something
  that happens once every few years.
- If IAM credentials ever need rotating, update the `BACKUP_AWS_ACCESS_KEY_ID`
  / `BACKUP_AWS_SECRET_ACCESS_KEY` GitHub Secrets and redeploy; no code
  changes are needed.
