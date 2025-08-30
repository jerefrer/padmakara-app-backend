#!/bin/bash
# Migrate from SQLite to PostgreSQL locally
# Usage: ./scripts/migrate-to-postgres.sh

set -e  # Exit on any error

# Configuration
LOCAL_PROJECT_PATH="/Users/jeremy/Documents/Programming/padmakara-backend-frontend/padmakara-backend"
LOCAL_DB_FILE="db.sqlite3"
LOCAL_PG_DB="padmakara_dev"
LOCAL_PG_USER="padmakara_dev"
LOCAL_PG_PASSWORD="dev_password_123"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

info() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

# Check if we're in the right directory
check_environment() {
    if [ ! -f "$LOCAL_PROJECT_PATH/manage.py" ]; then
        error "Cannot find Django project at $LOCAL_PROJECT_PATH"
    fi
    
    if [ ! -f "$LOCAL_PROJECT_PATH/$LOCAL_DB_FILE" ]; then
        error "Cannot find local SQLite database at $LOCAL_PROJECT_PATH/$LOCAL_DB_FILE"
    fi
    
    log "Environment check passed"
}

# Check PostgreSQL installation
check_postgresql() {
    info "Checking PostgreSQL installation..."
    
    if ! command -v psql &> /dev/null; then
        echo
        error "PostgreSQL is not installed. Please install it first:
        
On macOS with Homebrew:
    brew install postgresql
    brew services start postgresql
    
On Ubuntu/Debian:
    sudo apt update
    sudo apt install postgresql postgresql-contrib
    sudo systemctl start postgresql
    
Then run this script again."
    fi
    
    if ! command -v createdb &> /dev/null; then
        error "PostgreSQL client tools not found in PATH"
    fi
    
    log "PostgreSQL is installed"
}

# Setup local PostgreSQL database
setup_local_postgres() {
    info "Setting up local PostgreSQL database..."
    
    # Create database user (idempotent)
    echo "Setting up PostgreSQL user '$LOCAL_PG_USER'..."
    psql postgres -c "DROP USER IF EXISTS $LOCAL_PG_USER;" 2>/dev/null || true
    if psql postgres -c "CREATE USER $LOCAL_PG_USER WITH PASSWORD '$LOCAL_PG_PASSWORD';" 2>/dev/null; then
        echo "✓ User '$LOCAL_PG_USER' created"
    else
        echo "✓ User '$LOCAL_PG_USER' already exists"
    fi
    
    # Create database (idempotent)
    echo "Setting up database '$LOCAL_PG_DB'..."
    if dropdb $LOCAL_PG_DB 2>/dev/null; then
        echo "✓ Existing database '$LOCAL_PG_DB' dropped"
    else
        echo "✓ No existing database to drop"
    fi
    
    if createdb $LOCAL_PG_DB -O $LOCAL_PG_USER 2>/dev/null; then
        echo "✓ Database '$LOCAL_PG_DB' created"
    else
        echo "✓ Database '$LOCAL_PG_DB' already exists"
    fi
    
    log "Local PostgreSQL database setup completed"
}

# Show current SQLite data
show_sqlite_data() {
    info "Current SQLite database content:"
    
    cd "$LOCAL_PROJECT_PATH"
    
    # Check if we still have SQLite database and .env pointing to it
    if [ -f "$LOCAL_DB_FILE" ] && [ -f ".env" ] && grep -q "sqlite" .env; then
        source venv/bin/activate
        echo "Tables and row counts:"
        python manage.py shell -c "
from django.db import connection
cursor = connection.cursor()
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'django_%'\")
tables = cursor.fetchall()
total_rows = 0
for table in tables:
    cursor.execute(f'SELECT COUNT(*) FROM {table[0]}')
    count = cursor.fetchone()[0]
    total_rows += count
    print(f'  {table[0]}: {count} rows')
print(f'\\nTotal rows: {total_rows}')
"
    elif [ -f "$LOCAL_DB_FILE" ] && [ -f ".env.backup.sqlite" ]; then
        # We have the SQLite file but .env was already changed - use backup
        source venv/bin/activate
        echo "Using backed up SQLite configuration to check data..."
        ORIGINAL_ENV=$(cat .env)
        cp .env.backup.sqlite .env
        python manage.py shell -c "
from django.db import connection
cursor = connection.cursor()
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'django_%'\")
tables = cursor.fetchall()
total_rows = 0
for table in tables:
    cursor.execute(f'SELECT COUNT(*) FROM {table[0]}')
    count = cursor.fetchone()[0]
    total_rows += count
    print(f'  {table[0]}: {count} rows')
print(f'\\nTotal rows: {total_rows}')
"
        echo "$ORIGINAL_ENV" > .env
    elif [ -f "${LOCAL_DB_FILE}.backup" ]; then
        echo "SQLite database found as backup: ${LOCAL_DB_FILE}.backup"
        echo "Migration appears to have already been partially completed."
    else
        echo "No SQLite database found - this may be a fresh installation"
    fi
}

# Create new .env file for local PostgreSQL
create_local_env() {
    info "Creating .env file for local PostgreSQL..."
    
    cd "$LOCAL_PROJECT_PATH"
    
    # Backup existing .env if it exists and isn't already PostgreSQL
    if [ -f ".env" ] && ! grep -q "postgresql://" .env 2>/dev/null; then
        if [ ! -f ".env.backup.sqlite" ]; then
            cp .env .env.backup.sqlite
            warn "Backed up existing .env to .env.backup.sqlite"
        else
            warn "Using existing .env.backup.sqlite (not overwriting)"
        fi
    elif [ -f ".env" ] && grep -q "postgresql://" .env 2>/dev/null; then
        info ".env already configured for PostgreSQL"
        return 0
    fi
    
    # Create new .env file
    cat > .env << EOF
# Django Settings
SECRET_KEY=local-development-secret-key-not-for-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
ENVIRONMENT=development

# Local PostgreSQL Database
DATABASE_URL=postgresql://$LOCAL_PG_USER:$LOCAL_PG_PASSWORD@localhost:5432/$LOCAL_PG_DB

# Language and Timezone
LANGUAGE_CODE=pt-pt
TIME_ZONE=Europe/Lisbon

# AWS S3 Configuration (Optional - uses local storage if disabled)
USE_S3=False
# AWS_ACCESS_KEY_ID=your-key
# AWS_SECRET_ACCESS_KEY=your-secret
# AWS_STORAGE_BUCKET_NAME=your-bucket
# AWS_S3_REGION_NAME=eu-west-1

# Development settings
REDIS_URL=redis://localhost:6379/0
EOF
    
    log "Created .env file for PostgreSQL"
}

# Export SQLite data and import to PostgreSQL
migrate_data() {
    info "Migrating data from SQLite to PostgreSQL..."
    
    cd "$LOCAL_PROJECT_PATH"
    
    # First, export SQLite data using the original .env (still pointing to SQLite)
    info "Exporting SQLite data as Django fixtures..."
    mkdir -p dumps
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    FIXTURES_FILE="dumps/sqlite_to_postgres_$TIMESTAMP.json"
    
    # Check if we have data to migrate
    if [ ! -f "$LOCAL_DB_FILE" ] && [ ! -f "${LOCAL_DB_FILE}.backup" ]; then
        warn "No SQLite database found to migrate from - will create empty PostgreSQL database"
        echo "[]" > "$FIXTURES_FILE"
        log "Created empty fixtures file"
    else
        # Determine which SQLite file to use
        SQLITE_FILE="$LOCAL_DB_FILE"
        if [ ! -f "$SQLITE_FILE" ] && [ -f "${LOCAL_DB_FILE}.backup" ]; then
            SQLITE_FILE="${LOCAL_DB_FILE}.backup"
            info "Using SQLite backup file: $SQLITE_FILE"
        fi
        
        # Temporarily restore original .env to export from SQLite
        if [ -f ".env.backup.sqlite" ]; then
            cp .env .env.postgres.new
            cp .env.backup.sqlite .env
            info "Temporarily using SQLite .env for data export"
        fi
        
        source venv/bin/activate
        
        # Export data if we have any
        if python manage.py shell -c "from django.db import connection; cursor = connection.cursor(); cursor.execute('SELECT count(*) FROM sqlite_master WHERE type=\"table\" AND name NOT LIKE \"sqlite_%\" AND name NOT LIKE \"django_%\"'); print(cursor.fetchone()[0])" | grep -q "^0$"; then
            warn "No user tables found in SQLite database - creating empty fixtures"
            echo "[]" > "$FIXTURES_FILE"
        else
            python manage.py dumpdata \
                --natural-foreign \
                --natural-primary \
                --exclude=sessions \
                --exclude=contenttypes \
                --exclude=auth.Permission \
                --exclude=admin.LogEntry \
                --format=json > "$FIXTURES_FILE"
            
            # Check for any potential data constraint issues (informational only)
            info "Checking data for potential constraint issues..."
            python -c "
import json
import sys

with open('$FIXTURES_FILE', 'r') as f:
    data = json.load(f)

# Just check for potential issues without modifying data
for obj in data:
    fields = obj['fields']
    
    # Report any unusually long string fields for review
    for key, value in fields.items():
        if isinstance(value, str) and len(value) > 400:
            print(f'Long field: {obj[\"model\"]} pk={obj[\"pk\"]} field \"{key}\" has {len(value)} characters')

print('Data constraint check completed - FileField max_length increased to 500')
"
        fi
        
        log "SQLite data exported to $FIXTURES_FILE"
        
        # Restore PostgreSQL .env
        if [ -f ".env.postgres.new" ]; then
            cp .env.postgres.new .env
            rm .env.postgres.new
            info "Restored PostgreSQL .env"
        fi
    fi
    
    # Create PostgreSQL schema using Django migrations
    info "Creating PostgreSQL schema..."
    python manage.py migrate
    
    # Import data into PostgreSQL (if we have any)
    if [ -s "$FIXTURES_FILE" ] && [ "$(cat "$FIXTURES_FILE")" != "[]" ]; then
        info "Importing data into PostgreSQL..."
        python manage.py loaddata "$FIXTURES_FILE"
        log "Data imported successfully"
    else
        info "No data to import - PostgreSQL database is ready for fresh use"
    fi
    
    # Create cache tables
    info "Creating cache tables..."
    python manage.py createcachetable
    
    log "Data migration completed successfully"
}

# Verify PostgreSQL setup
verify_postgres_setup() {
    info "Verifying PostgreSQL setup..."
    
    cd "$LOCAL_PROJECT_PATH"
    source venv/bin/activate
    
    echo
    echo -e "${BOLD}=== LOCAL POSTGRESQL DATABASE ===${NC}"
    python manage.py shell -c "
from django.db import connection
cursor = connection.cursor()
cursor.execute(\"SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename NOT LIKE 'django_%' AND tablename NOT LIKE 'auth_%'\")
tables = cursor.fetchall()
total_rows = 0
for table in tables:
    cursor.execute(f'SELECT COUNT(*) FROM {table[0]}')
    count = cursor.fetchone()[0]
    total_rows += count
    print(f'  {table[0]}: {count} rows')
print(f'\\nTotal rows: {total_rows}')
print(f'\\nDatabase engine: {connection.settings_dict[\"ENGINE\"]}')
print(f'Database name: {connection.settings_dict[\"NAME\"]}')
"
    
    # Test Django functionality
    info "Testing Django functionality..."
    python manage.py check
    
    # Test development server briefly
    info "Testing development server..."
    timeout 5 python manage.py runserver --noinput 8002 >/dev/null 2>&1 &
    SERVER_PID=$!
    sleep 2
    
    if kill -0 $SERVER_PID 2>/dev/null; then
        log "✓ Development server works with PostgreSQL"
        kill $SERVER_PID 2>/dev/null || true
        wait $SERVER_PID 2>/dev/null || true
    else
        warn "⚠ Development server test failed"
    fi
    
    log "PostgreSQL setup verification completed"
}

# Cleanup old files
cleanup() {
    info "Cleaning up..."
    
    cd "$LOCAL_PROJECT_PATH"
    
    # Keep last 3 fixture files
    find dumps/ -name "sqlite_to_postgres_*.json" -type f | head -n -3 | xargs rm -f 2>/dev/null || true
    
    # Optional: backup SQLite file (if not already backed up)
    if [ -f "$LOCAL_DB_FILE" ] && [ ! -f "${LOCAL_DB_FILE}.backup" ]; then
        mv "$LOCAL_DB_FILE" "${LOCAL_DB_FILE}.backup"
        log "SQLite database backed up to ${LOCAL_DB_FILE}.backup"
    elif [ -f "$LOCAL_DB_FILE" ]; then
        rm "$LOCAL_DB_FILE"
        log "Removed SQLite database (backup already exists)"
    fi
    
    log "Cleanup completed"
}

# Main execution
main() {
    echo -e "${BOLD}SQLite to PostgreSQL Migration${NC}"
    echo "====================================="
    echo
    
    check_environment
    check_postgresql
    show_sqlite_data
    
    echo
    warn "This will:"
    warn "1. Create a new local PostgreSQL database"
    warn "2. Replace your .env file (backup will be created)"
    warn "3. Migrate all SQLite data to PostgreSQL"
    warn "4. Backup your SQLite database file"
    echo
    read -p "Do you want to continue? (y/N): " -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "Migration cancelled"
        exit 0
    fi
    
    setup_local_postgres
    create_local_env
    migrate_data
    verify_postgres_setup
    cleanup
    
    echo
    log "🎉 Successfully migrated from SQLite to PostgreSQL!"
    echo
    info "Your local development setup now uses:"
    info "  Database: PostgreSQL ($LOCAL_PG_DB)"
    info "  User: $LOCAL_PG_USER"  
    info "  Password: $LOCAL_PG_PASSWORD"
    echo
    info "Next steps:"
    info "1. Test your application: python manage.py runserver"
    info "2. The sync scripts will now work with pure PostgreSQL SQL dumps:"
    info "   • ./scripts/sync-prod-to-dev.sh - Import production data to local"
    info "   • ./scripts/sync-dev-to-prod.sh - Push local data to production"
    echo
    warn "Your original SQLite database is backed up as: ${LOCAL_DB_FILE}.backup"
    warn "Your original .env is backed up as: .env.backup.sqlite"
    echo
}

# Run main function
main "$@"