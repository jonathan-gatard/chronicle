#!/bin/bash
# Script to drop the 'homeassistant' database
# Usage: ./drop_db.sh [postgres_user] [postgres_host] [db_name]

PGUSER=${1:-postgres}
PGHOST=${2:-localhost}
DB_NAME=${3:-dbname}

echo "⚠️  WARNING: This will DELETE the '$DB_NAME' database!"
read -p "Are you sure? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Aborted."
    exit 1
fi

echo "Dropping database '$DB_NAME'..."

# Kill active connections
echo "Terminating active connections..."
psql -h "$PGHOST" -U "$PGUSER" -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" > /dev/null 2>&1

dropdb -h "$PGHOST" -U "$PGUSER" --if-exists "$DB_NAME"

if [ $? -eq 0 ]; then
    echo "✅ Database '$DB_NAME' dropped successfully."
else
    echo "❌ Failed to drop database."
fi
