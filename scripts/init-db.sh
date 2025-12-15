#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- DevGodzilla user and database
    CREATE USER devgodzilla WITH PASSWORD 'changeme';
    CREATE DATABASE devgodzilla_db OWNER devgodzilla;
    GRANT ALL PRIVILEGES ON DATABASE devgodzilla_db TO devgodzilla;

    -- Windmill user and database (SUPERUSER needed for migrations)
    CREATE USER windmill WITH PASSWORD 'changeme' SUPERUSER;
    CREATE DATABASE windmill_db OWNER windmill;
    GRANT ALL PRIVILEGES ON DATABASE windmill_db TO windmill;
    
    -- Windmill requires these roles for migrations
    CREATE ROLE windmill_admin;
    CREATE ROLE windmill_user;
    
    -- Grant roles to windmill user
    GRANT windmill_admin TO windmill;
    GRANT windmill_user TO windmill;
EOSQL

# Grant schema permissions for PostgreSQL 15+ (public schema no longer has CREATE by default)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "devgodzilla_db" <<-EOSQL
    GRANT ALL ON SCHEMA public TO devgodzilla;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO devgodzilla;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO devgodzilla;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "windmill_db" <<-EOSQL
    GRANT ALL ON SCHEMA public TO windmill;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO windmill;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO windmill;
EOSQL
