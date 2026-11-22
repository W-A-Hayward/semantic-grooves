#!/bin/sh
# Make sure a database is in place, then run the given command (the web server).
set -eu

: "${SG_DB_PATH:=/data/database.sqlite}"

if [ ! -f "$SG_DB_PATH" ]; then
    if [ -n "${SG_DB_URL:-}" ]; then
        if [ ! -w "$(dirname "$SG_DB_PATH")" ]; then
            echo "error: $(dirname "$SG_DB_PATH") is not writable, so the database cannot be downloaded there." >&2
            echo "Use a Docker volume for /data, or mount a folder that the container user (uid $(id -u)) can write to." >&2
            exit 1
        fi
        echo "No database at $SG_DB_PATH: downloading it from SG_DB_URL..."
        sg download-db
    else
        cat >&2 <<MSG
error: no database at $SG_DB_PATH.

Either mount a folder that contains database.sqlite:
    docker run -p 8000:8000 -v "\$PWD/data:/data:ro" semantic-grooves
or set SG_DB_URL and SG_DB_SHA256 to download a prebuilt database on first start.
MSG
        exit 1
    fi
fi

exec "$@"
