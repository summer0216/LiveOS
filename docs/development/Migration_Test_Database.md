# Migration Test Database

This workflow runs an isolated PostgreSQL 17 database on `127.0.0.1:55432`.
It uses only the dedicated `liveos_migration_test` database and a dedicated
Docker volume. It does not read production or development environment files.

```bash
scripts/migration-test-db up
scripts/migration-test-db initialize
scripts/migration-test-db test
scripts/migration-test-db down
```

To validate a production snapshot, start from a fresh volume and restore it
before running initialize:

```bash
scripts/migration-test-db down
scripts/migration-test-db up
scripts/migration-test-db restore /path/to/snapshot.dump
scripts/migration-test-db initialize
```

`restore` accepts plain `.sql` files and PostgreSQL archive dumps. The snapshot
is restored without source ownership or privilege metadata. `down` deletes only
the migration test workflow's dedicated Docker volume.
