#!/bin/bash
# Runs once, when the primary's data directory is first initialised.
# Creates the role and slots the standbys replicate through.
set -euo pipefail

psql -v ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set replication_password="$REPLICATION_PASSWORD" <<'SQL'
CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD :'replication_password';
SELECT pg_create_physical_replication_slot('replica_1');
SELECT pg_create_physical_replication_slot('replica_2');
SQL

echo "host replication replicator all scram-sha-256" >> "$PGDATA/pg_hba.conf"
