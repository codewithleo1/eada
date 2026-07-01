#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE eada_app;
    GRANT ALL PRIVILEGES ON DATABASE eada_app TO eada;
EOSQL