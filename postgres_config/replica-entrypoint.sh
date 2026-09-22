#!/bin/bash
# Entrypoint for the read-only standbys. On first start the data directory is
# cloned from the primary; after that the normal postgres entrypoint takes over
# and the server starts in standby mode because pg_basebackup -R left a
# standby.signal file behind.
set -euo pipefail

if [ ! -s "$PGDATA/PG_VERSION" ]; then
    mkdir -p "$PGDATA"
    chown postgres:postgres "$PGDATA"
    chmod 700 "$PGDATA"

    echo "Cloning $PRIMARY_HOST using slot $REPLICATION_SLOT"
    until gosu postgres pg_basebackup \
        --host="$PRIMARY_HOST" --username=replicator \
        --pgdata="$PGDATA" --wal-method=stream \
        --write-recovery-conf --slot="$REPLICATION_SLOT"; do
        echo "Primary not reachable yet, retrying in 3s"
        rm -rf "${PGDATA:?}"/*
        sleep 3
    done
fi

exec docker-entrypoint.sh postgres
