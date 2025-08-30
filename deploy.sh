#!/bin/bash
# Padmakara Backend Deployment Script
# Usage: ./deploy.sh [initial|update|rollback|status]

set -e  # Exit on any error

# Configuration
SERVER_HOST="212.227.131.117"
SERVER_USER="deploy"
SERVER_PATH="/home/deploy/padmakara-backend"
LOCAL_PATH="/Users/jeremy/Documents/Programming/padmakara-backend-frontend/padmakara-backend"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
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

# Check if rsync is available
check_dependencies() {
    if ! command -v rsync &> /dev/null; then
        error "rsync is required but not installed. Install with: brew install rsync"
    fi
    
    if ! command -v ssh &> /dev/null; then
        error "ssh is required but not installed."
    fi
}

# Test SSH connection
test_connection() {
    info "Testing SSH connection to ${SERVER_USER}@${SERVER_HOST}..."
    if ssh -o ConnectTimeout=10 ${SERVER_USER}@${SERVER_HOST} "echo 'Connection successful'" &> /dev/null; then
        log "SSH connection successful"
    else
        error "Cannot connect to server. Check your SSH configuration."
    fi
}

# Copy production environment file
copy_production_env() {
    log "Copying .env.production to server..."
    if [ -f "${LOCAL_PATH}/.env.production" ]; then
        info "Using existing .env.production file"
    else
        error ".env.production file not found. Please create it first."
    fi
}

# Sync code to server
sync_code() {
    log "Syncing code to server..."
    rsync -avz --progress \
        --exclude='venv/' \
        --exclude='*.pyc' \
        --exclude='__pycache__/' \
        --exclude='.git/' \
        --exclude='*.log' \
        --exclude='db.sqlite3' \
        --exclude='.env' \
        --exclude='media/' \
        --exclude='staticfiles/' \
        --exclude='.DS_Store' \
        "${LOCAL_PATH}/" \
        "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/"
    
    # Copy .env.production as .env on server
    if [ -f "${LOCAL_PATH}/.env.production" ]; then
        log "Copying .env.production to server as .env..."
        scp "${LOCAL_PATH}/.env.production" "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/.env"
    fi
    
    log "Code sync completed"
}

# Run server setup commands
server_setup() {
    local action=$1
    
    log "Running server setup commands..."
    
    ssh ${SERVER_USER}@${SERVER_HOST} << EOF
cd ${SERVER_PATH}

# Activate virtual environment
source venv/bin/activate

# Install/upgrade dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run Django commands
python manage.py collectstatic --noinput
python manage.py migrate

# Check for any issues
python manage.py check

echo "Server setup completed successfully"
EOF
}

# Restart services
restart_services() {
    log "Restarting services..."
    
    ssh ${SERVER_USER}@${SERVER_HOST} << 'EOF'
# Restart application
sudo supervisorctl restart padmakara-backend

# Check status
sleep 2
sudo supervisorctl status padmakara-backend

# Reload nginx
sudo systemctl reload nginx

echo "Services restarted successfully"
EOF

    log "Services restart completed"
}

# Check deployment status
check_status() {
    info "Checking deployment status..."
    
    ssh ${SERVER_USER}@${SERVER_HOST} << 'EOF'
echo "=== System Status ==="
echo "Date: $(date)"
echo "Uptime: $(uptime)"
echo ""

echo "=== Service Status ==="
sudo supervisorctl status padmakara-backend
sudo systemctl status nginx --no-pager -l

echo ""
echo "=== Application Health ==="
cd ~/padmakara-backend
source venv/bin/activate
python manage.py check

echo ""
echo "=== Disk Usage ==="
df -h /home/deploy

echo ""
echo "=== Process Information ==="
ps aux | grep -E "(gunicorn|nginx)" | grep -v grep

echo ""
echo "=== Recent Logs ==="
echo "--- Application Logs (last 10 lines) ---"
sudo tail -10 /var/log/padmakara-backend.log

echo ""
echo "--- Nginx Error Logs (last 5 lines) ---"
sudo tail -5 /var/log/nginx/error.log
EOF
}

# Test deployment
test_deployment() {
    log "Testing deployment..."
    
    # Test local connection to server
    if curl -s --max-time 10 "http://${SERVER_HOST}/admin/" > /dev/null; then
        log "✓ Application is responding to HTTP requests"
    else
        warn "⚠ Application may not be responding correctly"
    fi
    
    # Test from server itself
    ssh ${SERVER_USER}@${SERVER_HOST} << 'EOF'
echo "Testing from server..."

# Test local connection
if curl -s --max-time 10 "http://localhost:8000/admin/" > /dev/null; then
    echo "✓ Local application is responding"
else
    echo "✗ Local application is not responding"
fi

# Test database connection
cd ~/padmakara-backend
source venv/bin/activate
if python manage.py shell -c "from django.db import connection; connection.ensure_connection(); print('✓ Database connection successful')"; then
    echo "✓ Database is accessible"
else
    echo "✗ Database connection failed"
fi
EOF
}

# Create backup before deployment
create_backup() {
    log "Creating backup before deployment..."
    
    ssh ${SERVER_USER}@${SERVER_HOST} << 'EOF'
BACKUP_DIR="/home/deploy/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database if using PostgreSQL
if grep -q "postgresql" ~/padmakara-backend/.env 2>/dev/null; then
    echo "Backing up PostgreSQL database..."
    pg_dump -U padmakara_user -h localhost padmakara_db > $BACKUP_DIR/db_pre_deploy_$DATE.sql
    echo "Database backup saved to: $BACKUP_DIR/db_pre_deploy_$DATE.sql"
fi

# Backup current code
echo "Backing up current application code..."
tar -czf $BACKUP_DIR/code_pre_deploy_$DATE.tar.gz ~/padmakara-backend \
    --exclude=venv --exclude=__pycache__ --exclude=*.pyc --exclude=.git

echo "Code backup saved to: $BACKUP_DIR/code_pre_deploy_$DATE.tar.gz"

# Clean old backups (keep last 5)
cd $BACKUP_DIR
ls -t db_pre_deploy_*.sql 2>/dev/null | tail -n +6 | xargs rm -f
ls -t code_pre_deploy_*.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f

echo "Backup completed"
EOF
}

# Initial deployment
initial_deployment() {
    log "Starting initial deployment..."
    
    check_dependencies
    test_connection
    copy_production_env
    
    log "Creating server directory structure..."
    ssh ${SERVER_USER}@${SERVER_HOST} "mkdir -p ${SERVER_PATH}"
    
    sync_code
    
    log "Setting up virtual environment on server..."
    ssh ${SERVER_USER}@${SERVER_HOST} << EOF
cd ${SERVER_PATH}

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

echo "Virtual environment created. Next steps:"
echo "1. Review and update .env file on server if needed"
echo "2. Run: ssh ${SERVER_USER}@${SERVER_HOST}"
echo "3. Run: cd ${SERVER_PATH} && source venv/bin/activate"
echo "4. Run: pip install -r requirements.txt"
echo "5. Set up your database and run migrations"
echo "6. Configure nginx and supervisor (see DEPLOYMENT.md)"
EOF
    
    log "Initial deployment completed!"
    warn "Don't forget to:"
    warn "1. Review .env file on server (already copied from .env.production)"
    warn "2. Set up database, nginx, and supervisor"
    warn "3. Run the update deployment once configured"
}

# Update deployment
update_deployment() {
    log "Starting update deployment..."
    
    check_dependencies
    test_connection
    create_backup
    sync_code
    server_setup
    restart_services
    
    sleep 5  # Give services time to start
    test_deployment
    
    log "Update deployment completed successfully!"
}

# Rollback deployment
rollback_deployment() {
    warn "Rolling back to previous version..."
    
    ssh ${SERVER_USER}@${SERVER_HOST} << 'EOF'
BACKUP_DIR="/home/deploy/backups"

# Find the latest backup
LATEST_CODE_BACKUP=$(ls -t $BACKUP_DIR/code_pre_deploy_*.tar.gz 2>/dev/null | head -n 1)
LATEST_DB_BACKUP=$(ls -t $BACKUP_DIR/db_pre_deploy_*.sql 2>/dev/null | head -n 1)

if [ -z "$LATEST_CODE_BACKUP" ]; then
    echo "No code backup found for rollback!"
    exit 1
fi

echo "Rolling back code from: $LATEST_CODE_BACKUP"

# Backup current state before rollback
DATE=$(date +%Y%m%d_%H%M%S)
tar -czf $BACKUP_DIR/code_before_rollback_$DATE.tar.gz ~/padmakara-backend \
    --exclude=venv --exclude=__pycache__ --exclude=*.pyc --exclude=.git

# Extract backup
cd /home/deploy
tar -xzf $LATEST_CODE_BACKUP

echo "Code rollback completed"

# Rollback database if backup exists
if [ ! -z "$LATEST_DB_BACKUP" ] && grep -q "postgresql" ~/padmakara-backend/.env 2>/dev/null; then
    echo "Rolling back database from: $LATEST_DB_BACKUP"
    psql -U padmakara_user -h localhost padmakara_db < $LATEST_DB_BACKUP
    echo "Database rollback completed"
fi
EOF
    
    # Restart services after rollback
    restart_services
    test_deployment
    
    warn "Rollback completed. Please verify your application is working correctly."
}

# Main script logic
main() {
    local command=${1:-help}
    
    case $command in
        "initial")
            initial_deployment
            ;;
        "update")
            update_deployment
            ;;
        "rollback")
            rollback_deployment
            ;;
        "status")
            check_status
            ;;
        "test")
            test_deployment
            ;;
        "backup")
            create_backup
            ;;
        "help"|*)
            echo "Padmakara Backend Deployment Script"
            echo ""
            echo "Usage: $0 [command]"
            echo ""
            echo "Commands:"
            echo "  initial   - Initial deployment setup"
            echo "  update    - Deploy updates (default)"
            echo "  rollback  - Rollback to previous version"
            echo "  status    - Check deployment status"
            echo "  test      - Test current deployment"
            echo "  backup    - Create backup"
            echo "  help      - Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 initial    # First time deployment"
            echo "  $0 update     # Deploy new changes"
            echo "  $0 status     # Check if everything is working"
            echo ""
            ;;
    esac
}

# Run main function with all arguments
main "$@"