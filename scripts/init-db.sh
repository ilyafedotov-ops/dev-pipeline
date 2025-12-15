#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER devgodzilla WITH PASSWORD 'changeme';
    CREATE DATABASE devgodzilla_db;
    GRANT ALL PRIVILEGES ON DATABASE devgodzilla_db TO devgodzilla;

    CREATE USER windmill WITH PASSWORD 'changeme';
    CREATE DATABASE windmill_db;
    GRANT ALL PRIVILEGES ON DATABASE windmill_db TO windmill;
EOSQL
