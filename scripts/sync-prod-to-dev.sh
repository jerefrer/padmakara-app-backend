#!/bin/bash
# Production to Development Database Sync Script (PostgreSQL to PostgreSQL)
# Usage: ./scripts/sync-prod-to-dev.sh

set -e  # Exit on any error

# Configuration
LOCAL_PROJECT_PATH="/Users/jeremy/Documents/Programming/padmakara-backend-frontend/padmakara-backend"
PROD_SERVER="deploy@212.227.131.117"

# Extract database credentials from .env.production
if [ -f "$LOCAL_PROJECT_PATH/.env.production" ]; then
    DATABASE_URL=$(grep "^DATABASE_URL=" "$LOCAL_PROJECT_PATH/.env.production" | cut -d'=' -f2-)
    if [[ $DATABASE_URL =~ postgresql://([^:]+):([^@]+)@([^:]+):([0-9]+)/(.+) ]]; then
        PROD_DB_USER="${BASH_REMATCH[1]}"
        PROD_DB_PASSWORD="${BASH_REMATCH[2]}"
        PROD_DB_HOST="${BASH_REMATCH[3]}"
        PROD_DB_PORT="${BASH_REMATCH[4]}"
        PROD_DB_NAME="${BASH_REMATCH[5]}"
    else
        error "Could not parse DATABASE_URL from .env.production"
    fi
else
    error "Could not find .env.production file at $LOCAL_PROJECT_PATH/.env.production"
fi

# Extract local database credentials from .env
if [ -f "$LOCAL_PROJECT_PATH/.env" ]; then
    LOCAL_DATABASE_URL=$(grep "^DATABASE_URL=" "$LOCAL_PROJECT_PATH/.env" | cut -d'=' -f2-)
    if [[ $LOCAL_DATABASE_URL =~ postgresql://([^:]+):([^@]+)@([^:]+):([0-9]+)/(.+) ]]; then
        LOCAL_DB_USER="${BASH_REMATCH[1]}"
        LOCAL_DB_PASSWORD="${BASH_REMATCH[2]}"
        LOCAL_DB_HOST="${BASH_REMATCH[3]}"
        LOCAL_DB_PORT="${BASH_REMATCH[4]}"
        LOCAL_DB_NAME="${BASH_REMATCH[5]}"
    else
        error "Could not parse local DATABASE_URL from .env - make sure you migrated to PostgreSQL first"
    fi
else
    error "Could not find .env file. Run ./scripts/migrate-to-postgres.sh first"
fi

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

# Check environment
check_environment() {
    if [ ! -f "$LOCAL_PROJECT_PATH/manage.py" ]; then
        error "Cannot find Django project at $LOCAL_PROJECT_PATH"
    fi
    
    # Check if psql is available
    if ! command -v psql &> /dev/null; then
        error "psql command is required but not found. Install PostgreSQL client tools."
    fi
    
    log "Environment check passed"
}

# Test connections
test_connections() {
    info "Testing database connections..."
    
    # Test SSH connection
    if ssh -o ConnectTimeout=10 $PROD_SERVER "echo 'Connection successful'" &> /dev/null; then
        log "✓ SSH connection successful"
    else
        error "Cannot connect to production server. Check your SSH configuration."
    fi
    
    # Test local PostgreSQL connection
    export PGPASSWORD="$LOCAL_DB_PASSWORD"
    if psql -h $LOCAL_DB_HOST -p $LOCAL_DB_PORT -U $LOCAL_DB_USER -d $LOCAL_DB_NAME -c "SELECT 1;" >/dev/null 2>&1; then
        log "✓ Local PostgreSQL connection successful"
    else
        error "Cannot connect to local PostgreSQL database. Check your .env file."
    fi
}

# Show current database stats
show_database_info() {
    info "Gathering database information..."
    
    echo
    echo -e "${BOLD}=== PRODUCTION DATABASE (PostgreSQL) ===${NC}"
    ssh $PROD_SERVER "
        export PGPASSWORD='$PROD_DB_PASSWORD'
        psql -h $PROD_DB_HOST -p $PROD_DB_PORT -U $PROD_DB_USER -d $PROD_DB_NAME -t -c \"
        SELECT 
            schemaname||'.'||relname as table_name,
            n_tup_ins - n_tup_del as row_count
        FROM pg_stat_user_tables 
        WHERE schemaname = 'public' 
        AND relname NOT LIKE 'django_%' 
        AND relname NOT LIKE 'auth_%'
        ORDER BY relname;
        \" | while read line; do
            if [ ! -z \"\$line\" ]; then
                echo \"  \$line\"
            fi
        done
    "
    
    echo
    echo -e "${BOLD}=== LOCAL DATABASE (PostgreSQL) ===${NC}"
    export PGPASSWORD="$LOCAL_DB_PASSWORD"
    
    echo "Tables and row counts:"
    if psql -h $LOCAL_DB_HOST -p $LOCAL_DB_PORT -U $LOCAL_DB_USER -d $LOCAL_DB_NAME -c "SELECT 1;" >/dev/null 2>&1; then
        psql -h $LOCAL_DB_HOST -p $LOCAL_DB_PORT -U $LOCAL_DB_USER -d $LOCAL_DB_NAME -t -c "
        SELECT 
            schemaname||'.'||relname as table_name,
            n_tup_ins - n_tup_del as row_count
        FROM pg_stat_user_tables 
        WHERE schemaname = 'public' 
        AND relname NOT LIKE 'django_%' 
        AND relname NOT LIKE 'auth_%'
        ORDER BY relname;
        " | while read line; do
            if [ ! -z "$line" ]; then
                echo "  $line"
            fi
        done
    else
        echo "  Local PostgreSQL database not accessible - will be created/replaced"
    fi
    
    echo
}

# Simple confirmation
confirm_operation() {
    echo -e "${YELLOW}This will replace your local development database with production data.${NC}"
    echo "Your current local database will be overwritten (no backup will be made)."
    echo
    read -p "Do you want to continue? (y/N): " -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "Operation cancelled"
        exit 0
    fi
    
    log "Proceeding with production to development sync"
}

# Create PostgreSQL dump from production
export_prod_database() {
    log "Creating PostgreSQL dump from production database..."
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    DUMP_FILE="prod_to_local_$TIMESTAMP.sql"
    
    ssh $PROD_SERVER "
        cd ~/padmakara-backend
        mkdir -p dumps
        
        echo 'Creating PostgreSQL dump...'
        export PGPASSWORD='$PROD_DB_PASSWORD'
        
        # Create a complete dump with --clean to handle existing data
        pg_dump -h $PROD_DB_HOST -p $PROD_DB_PORT -U $PROD_DB_USER -d $PROD_DB_NAME \
            --clean \
            --no-owner \
            --no-privileges \
            > dumps/$DUMP_FILE
        
        echo 'Production dump created: dumps/$DUMP_FILE'
        ls -lh dumps/$DUMP_FILE
    "
    
    log "Production database dump completed"
}

# Transfer SQL dump to local machine
transfer_dump() {
    log "Transferring PostgreSQL dump from production server..."
    
    # Create local dumps directory
    mkdir -p "$LOCAL_PROJECT_PATH/dumps"
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    DUMP_FILE="prod_to_local_$TIMESTAMP.sql"
    
    scp "$PROD_SERVER:~/padmakara-backend/dumps/$DUMP_FILE" "$LOCAL_PROJECT_PATH/dumps/"
    
    # Create a latest symlink
    ln -sf "$DUMP_FILE" "$LOCAL_PROJECT_PATH/dumps/prod_latest.sql"
    
    log "PostgreSQL dump transferred successfully"
}

# Import production dump to local PostgreSQL
import_to_development() {
    log "Importing production database to local PostgreSQL..."
    
    cd "$LOCAL_PROJECT_PATH"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    DUMP_FILE="dumps/prod_to_local_$TIMESTAMP.sql"
    
    export PGPASSWORD="$LOCAL_DB_PASSWORD"
    
    # Import the dump directly - the --clean flag will handle existing data
    psql -h $LOCAL_DB_HOST -p $LOCAL_DB_PORT -U $LOCAL_DB_USER -d $LOCAL_DB_NAME < "$DUMP_FILE"
    
    log "Production data imported to local development successfully"
}

# Verify import success
verify_import() {
    log "Verifying import success..."
    
    cd "$LOCAL_PROJECT_PATH"
    
    echo
    echo -e "${BOLD}=== LOCAL DATABASE AFTER IMPORT ===${NC}"
    export PGPASSWORD="$LOCAL_DB_PASSWORD"
    
    echo "Tables and row counts:"
    psql -h $LOCAL_DB_HOST -p $LOCAL_DB_PORT -U $LOCAL_DB_USER -d $LOCAL_DB_NAME -t -c "
    SELECT 
        schemaname||'.'||relname as table_name,
        n_tup_ins - n_tup_del as row_count
    FROM pg_stat_user_tables 
    WHERE schemaname = 'public' 
    AND relname NOT LIKE 'django_%' 
    AND relname NOT LIKE 'auth_%'
    ORDER BY relname;
    " | while read line; do
        if [ ! -z "$line" ]; then
            echo "  $line"
        fi
    done
    
    # Test local development server briefly
    info "Testing local development server startup..."
    source venv/bin/activate
    timeout 10 python manage.py runserver --noinput 8001 >/dev/null 2>&1 &
    SERVER_PID=$!
    sleep 3
    
    if kill -0 $SERVER_PID 2>/dev/null; then
        log "✓ Development server started successfully"
        kill $SERVER_PID 2>/dev/null || true
        wait $SERVER_PID 2>/dev/null || true
    else
        warn "⚠ Development server may have issues starting"
    fi
    
    log "Import verification completed"
}

# Clean up temporary files
cleanup() {
    log "Cleaning up temporary files..."
    
    cd "$LOCAL_PROJECT_PATH"
    
    # Clean up remote dumps (keep last 5)
    ssh $PROD_SERVER "
        cd ~/padmakara-backend/dumps
        ls -t prod_to_local_*.sql 2>/dev/null | tail -n +6 | xargs rm -f
        echo 'Cleaned up old production dump files'
    " 2>/dev/null || true
    
    # Clean up local dumps (keep last 3)
    find dumps/ -name "prod_to_local_*.sql" -type f | sort -r | tail -n +4 | xargs rm -f 2>/dev/null || true
    
    log "Cleanup completed"
}

# Main execution
main() {
    echo -e "${BOLD}Production to Development Database Sync (PostgreSQL → PostgreSQL)${NC}"
    echo "=========================================================================="
    echo
    
    check_environment
    test_connections
    show_database_info
    confirm_operation
    export_prod_database
    transfer_dump
    import_to_development
    verify_import
    cleanup
    
    echo
    log "🎉 Production database successfully synced to development!"
    info "You can now run 'python manage.py runserver' to start your local development server"
    echo
}

# Run main function
main "$@"