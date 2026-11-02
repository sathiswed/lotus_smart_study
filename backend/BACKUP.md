# Pilot backup and restore runbook

Database rows and private answer images form one logical backup set. Take both
at the same cutoff and label them with the same timestamp/version.

## Backup

1. Quiesce writes or record a database transaction/WAL cutoff.
2. Use the project owner's PostgreSQL tooling to create an encrypted logical or
   physical backup of the pilot database.
3. Create a versioned inventory/copy of the private S3 bucket, including object
   keys referenced by `answer_images`.
4. Store the database backup, object inventory/version, migration revision, and
   application release identifier together in restricted backup storage.
5. Verify that the backup is readable using an isolated environment.

## Restore

1. Restore PostgreSQL into an isolated database and confirm the Alembic revision.
2. Restore the matching object-store version into a private bucket.
3. Compare every Ready `answer_images.object_key` with the restored inventory.
4. Point the API at the restored pair and perform the project owner's manual
   end-to-end validation before reopening access.

Retention, encryption keys, frequency, and recovery objectives are deployment
inputs. The bucket and backups must remain private.
