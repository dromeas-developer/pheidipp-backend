#!/bin/bash
# Create test_pheidipp database on Postgres startup

set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE test_pheidipp;
EOSQL

echo "Created test_pheidipp database"
