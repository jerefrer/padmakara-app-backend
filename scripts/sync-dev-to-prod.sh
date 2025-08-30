#!/bin/bash
# Development to Production Database Sync Script (PostgreSQL to PostgreSQL)
# WARNING: This script will COMPLETELY REPLACE the production database
# Usage: ./scripts/sync-dev-to-prod.sh

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

danger() {
    echo -e "${RED}${BOLD}[$(date '+%Y-%m-%d %H:%M:%S')] DANGER: $1${NC}"
}

# Check environment
check_environment() {
    if [ ! -f "$LOCAL_PROJECT_PATH/manage.py" ]; then
        error "Cannot find Django project at $LOCAL_PROJECT_PATH"
    fi
    
    # Check if pg_dump is available
    if ! command -v pg_dump &> /dev/null; then
        error "pg_dump command is required but not found. Install PostgreSQL client tools."
    fi
    
    log "Environment check passed"
}

# Test connections
test_connections() {
    info "Testing database connections..."
    
    # Test local PostgreSQL connection
    export PGPASSWORD="$LOCAL_DB_PASSWORD"
    if psql -h $LOCAL_DB_HOST -p $LOCAL_DB_PORT -U $LOCAL_DB_USER -d $LOCAL_DB_NAME -c "SELECT 1;" >/dev/null 2>&1; then
        log "✓ Local PostgreSQL connection successful"
    else
        error "Cannot connect to local PostgreSQL database. Check your .env file."
    fi
    
    # Test SSH connection
    if ssh -o ConnectTimeout=10 $PROD_SERVER "echo 'Connection successful'" &> /dev/null; then
        log "✓ SSH connection successful"
    else
        error "Cannot connect to production server. Check your SSH configuration."
    fi
}

# Show current database stats
show_database_info() {
    info "Gathering database information..."
    
    echo
    echo -e "${BOLD}=== LOCAL DATABASE (PostgreSQL) ===${NC}"
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
}

# Multiple confirmation system
confirm_destructive_operation() {
    echo
    danger "╔══════════════════════════════════════════════════════════════════════════════╗"
    danger "║                                                                              ║"
    danger "║                            ⚠️  CRITICAL WARNING  ⚠️                           ║"
    danger "║                                                                              ║"
    danger "║  This operation will COMPLETELY DESTROY the production database and          ║"
    danger "║  replace it with your local development data.                                ║"
    danger "║                                                                              ║"
    danger "║  This action is IRREVERSIBLE unless you have external backups!               ║"
    danger "║                                                                              ║"
    danger "║  Production Database: $PROD_DB_NAME@$PROD_SERVER                             ║"
    danger "║                                                                              ║"
    danger "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo
    
    # First confirmation
    echo -e "${RED}${BOLD}Are you absolutely sure you want to DESTROY the production database?${NC}"
    echo "Type 'DESTROY PRODUCTION DATABASE' exactly (case sensitive) to continue:"
    read -r first_confirm
    
    if [ "$first_confirm" != "DESTROY PRODUCTION DATABASE" ]; then
        info "Operation cancelled - confirmation text did not match exactly"
        exit 0
    fi
    
    # Second confirmation with database name
    echo
    echo -e "${RED}${BOLD}Second confirmation required.${NC}"
    echo "Type the production database name '$PROD_DB_NAME' to confirm:"
    read -r second_confirm
    
    if [ "$second_confirm" != "$PROD_DB_NAME" ]; then
        info "Operation cancelled - database name did not match"
        exit 0
    fi
    
    # Final countdown
    echo
    warn "Final confirmation: This will permanently delete production data in 5 seconds..."
    for i in 5 4 3 2 1; do
        echo -e "${RED}$i...${NC}"
        sleep 1
    done
    
    log "Confirmations complete - proceeding with database replacement"
}

# Create production backup
backup_production_database() {
    log "Creating backup of production database..."
    
    BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="prod_backup_before_dev_sync_$BACKUP_TIMESTAMP.sql"
    
    ssh $PROD_SERVER "
        cd ~/padmakara-backend
        mkdir -p backups
        export PGPASSWORD='$PROD_DB_PASSWORD'
        pg_dump -h $PROD_DB_HOST -p $PROD_DB_PORT -U $PROD_DB_USER -d $PROD_DB_NAME > backups/$BACKUP_FILE
        echo 'Production backup saved to: ~/padmakara-backend/backups/$BACKUP_FILE'
        ls -lh backups/$BACKUP_FILE
    "
    
    log "Production database backup completed"
}

# Create local database dump
create_local_dump() {
    log "Creating local PostgreSQL dump..."
    
    cd "$LOCAL_PROJECT_PATH"
    mkdir -p dumps
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    LOCAL_DUMP_FILE="dumps/local_to_prod_$TIMESTAMP.sql"
    
    export PGPASSWORD="$LOCAL_DB_PASSWORD"
    pg_dump -h $LOCAL_DB_HOST -p $LOCAL_DB_PORT -U $LOCAL_DB_USER -d $LOCAL_DB_NAME \
        --clean \
        --no-owner \
        --no-privileges \
        > "$LOCAL_DUMP_FILE"
    
    log "Local database dump created: $LOCAL_DUMP_FILE"
}

# Transfer and import to production
import_to_production() {
    log "Importing local database to production..."
    
    cd "$LOCAL_PROJECT_PATH"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    LOCAL_DUMP_FILE="dumps/local_to_prod_$TIMESTAMP.sql"
    
    # Ensure dumps directory exists on production
    ssh $PROD_SERVER "mkdir -p ~/padmakara-backend/dumps"
    
    # Transfer dump to production
    scp "$LOCAL_DUMP_FILE" "$PROD_SERVER:~/padmakara-backend/dumps/"
    
    ssh $PROD_SERVER "
        cd ~/padmakara-backend
        mkdir -p dumps
        
        echo 'Importing local database dump to production...'
        export PGPASSWORD='$PROD_DB_PASSWORD'
        
        # Import the dump
        psql -h $PROD_DB_HOST -p $PROD_DB_PORT -U $PROD_DB_USER -d $PROD_DB_NAME < dumps/local_to_prod_$TIMESTAMP.sql
        
        echo 'Database import completed successfully'
    "
    
    log "Local database imported to production successfully"
}

# Restart production services
restart_production_services() {
    log "Restarting production services..."
    
    ssh $PROD_SERVER "
        sudo supervisorctl restart padmakara-backend
        sleep 3
        sudo supervisorctl status padmakara-backend
    " || warn "Could not restart services - you may need to do this manually"
    
    log "Production services restart completed"
}

# Verify import success
verify_import() {
    log "Verifying import success..."
    
    echo
    echo -e "${BOLD}=== PRODUCTION DATABASE AFTER IMPORT ===${NC}"
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
    
    # Test admin login
    info "Testing admin interface access..."
    if curl -s --max-time 10 "http://212.227.131.117/admin/" | grep -q "Django administration" ; then
        log "✓ Admin interface is accessible"
    else
        warn "⚠ Admin interface may not be responding correctly"
    fi
    
    log "Import verification completed"
}

# Clean up local temporary files
cleanup_local() {
    log "Cleaning up local temporary files..."
    
    cd "$LOCAL_PROJECT_PATH"
    
    # Keep last 3 dump files
    find dumps/ -name "local_to_prod_*.sql" -type f | sort -r | tail -n +4 | xargs rm -f 2>/dev/null || true
    
    log "Local cleanup completed"
}

# Main execution
main() {
    echo -e "${BOLD}Development to Production Database Sync (PostgreSQL → PostgreSQL)${NC}"
    echo "=========================================================================="
    echo
    
    check_environment
    test_connections
    show_database_info
    confirm_destructive_operation
    backup_production_database
    create_local_dump
    import_to_production
    restart_production_services
    verify_import
    cleanup_local
    
    echo
    log "🎉 Development database successfully synced to production!"
    warn "Don't forget: Production backup is saved on the server in ~/padmakara-backend/backups/"
    echo
}

# Run main function
main "$@"