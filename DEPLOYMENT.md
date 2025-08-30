# Padmakara Backend - Deployment Guide

This guide covers deploying the Padmakara Django backend to a Ubuntu server using the deploy user's home directory.

## Server Information

- **Server**: 212.227.131.117
- **User**: deploy
- **Deploy Path**: `/home/deploy/padmakara-backend/`
- **Python Version**: 3.12 (server), 3.12 (local)
- **Database**: PostgreSQL (production) / SQLite (development)

## Prerequisites

### Local Machine

- Python 3.12+
- rsync installed
- SSH access to server as `deploy` user

### Server Requirements

- Ubuntu 20.04+
- Python 3.10+
- PostgreSQL
- Nginx
- Supervisor

## Initial Server Setup

### 1. Connect to Server

```bash
ssh deploy@212.227.131.117
```

### 2. Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv python3-dev \
    postgresql postgresql-contrib nginx supervisor \
    python-is-python3 build-essential libpq-dev
```

### 3. Create Project Directory

```bash
mkdir -p ~/padmakara-backend
cd ~/padmakara-backend
```

## Initial Deployment

### 4. Transfer Code (Run from Local Machine)

```bash
# Navigate to your local project
cd /Users/jeremy/Documents/Programming/padmakara-backend-frontend/padmakara-backend

# Deploy using the deployment script
./deploy.sh initial
```

### 5. Server Setup (Run on Server)

```bash
ssh deploy@212.227.131.117
cd ~/padmakara-backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Environment file is automatically copied from .env.production
# Review and edit if needed:
nano .env
```

### 6. Database Setup

```bash
# Create PostgreSQL database
sudo -u postgres createdb padmakara_db
sudo -u postgres createuser padmakara_user
sudo -u postgres psql -c "ALTER USER padmakara_user WITH PASSWORD 'your_secure_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE padmakara_db TO padmakara_user;"

# Update .env with database URL
echo "DATABASE_URL=postgresql://padmakara_user:your_secure_password@localhost:5432/padmakara_db" >> .env
```

### 7. Django Setup

```bash
source venv/bin/activate

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Test application
python manage.py check
```

### 8. Production Configuration

#### Gunicorn Configuration

```bash
cat > ~/padmakara-backend/gunicorn_config.py << 'EOF'
bind = "127.0.0.1:8000"
workers = 3
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 5
preload_app = True
user = "deploy"
group = "deploy"
EOF
```

#### Supervisor Configuration

```bash
sudo tee /etc/supervisor/conf.d/padmakara-backend.conf << 'EOF'
[program:padmakara-backend]
command=/home/deploy/padmakara-backend/venv/bin/gunicorn --config /home/deploy/padmakara-backend/gunicorn_config.py padmakara.wsgi
directory=/home/deploy/padmakara-backend
user=deploy
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/padmakara-backend.log
environment=PATH="/home/deploy/padmakara-backend/venv/bin"
EOF

# Create log file with proper permissions
sudo touch /var/log/padmakara-backend.log
sudo chown deploy:deploy /var/log/padmakara-backend.log

# Start the service
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start padmakara-backend
```

#### Nginx Configuration

```bash
sudo tee /etc/nginx/sites-available/padmakara-backend << 'EOF'
server {
    listen 80;
    server_name 212.227.131.117;

    client_max_body_size 100M;

    # Static files
    location /static/ {
        alias /home/deploy/padmakara-backend/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Media files (if serving locally)
    location /media/ {
        alias /home/deploy/padmakara-backend/media/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Django application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 30;
        proxy_send_timeout 30;
        proxy_read_timeout 30;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/padmakara-backend /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

#### Firewall Setup

```bash
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
```

## Environment Configuration

### .env File Template

```bash
# Django Settings
SECRET_KEY=your-production-secret-key-here-make-it-long-and-random
DEBUG=False
ALLOWED_HOSTS=212.227.131.117,your-domain.com,localhost

# Database
DATABASE_URL=postgresql://padmakara_user:your_secure_password@localhost:5432/padmakara_db

# S3 Configuration
USE_S3=True
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_STORAGE_BUCKET_NAME=padmakara-content
AWS_S3_REGION_NAME=eu-west-1

# Lambda Configuration
SITE_URL=http://212.227.131.117
AWS_LAMBDA_FUNCTION_NAME=padmakara-zip-generator
TEMP_S3_BUCKET=padmakara-pt-temp-downloads

# Localization
LANGUAGE_CODE=pt-pt
TIME_ZONE=Europe/Lisbon
```

## Deployment Updates

### Automated Deployment

```bash
# From your local machine, run:
./deploy.sh update
```

### Manual Update Process

```bash
# 1. Sync code from local machine
rsync -avz --exclude='venv' --exclude='*.pyc' --exclude='__pycache__' --exclude='.git' \
  /path/to/padmakara-backend/ \
  deploy@212.227.131.117:~/padmakara-backend/

# 2. On server - apply updates
ssh deploy@212.227.131.117
cd ~/padmakara-backend
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo supervisorctl restart padmakara-backend
```

## Monitoring and Maintenance

### Log Files

```bash
# Application logs
sudo tail -f /var/log/padmakara-backend.log

# Nginx logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# System logs
sudo journalctl -f -u nginx
sudo journalctl -f -u supervisor
```

### Service Management

```bash
# Check service status
sudo supervisorctl status padmakara-backend
sudo systemctl status nginx

# Restart services
sudo supervisorctl restart padmakara-backend
sudo systemctl reload nginx

# Stop/Start services
sudo supervisorctl stop padmakara-backend
sudo supervisorctl start padmakara-backend
```

### Database Maintenance

```bash
# Connect to database
psql -U padmakara_user -d padmakara_db -h localhost

# Backup database
pg_dump -U padmakara_user -h localhost padmakara_db > backup_$(date +%Y%m%d).sql

# Restore database
psql -U padmakara_user -h localhost padmakara_db < backup_file.sql
```

## SSL/HTTPS Setup (Optional)

### Install Certbot

```bash
sudo apt install certbot python3-certbot-nginx
```

### Get SSL Certificate

```bash
# Replace with your actual domain
sudo certbot --nginx -d your-domain.com
```

### Auto-renewal

```bash
# Test renewal
sudo certbot renew --dry-run

# Cron job is automatically created
sudo crontab -l
```

## Troubleshooting

### Common Issues

#### 1. Permission Errors

```bash
# Fix file permissions
sudo chown -R deploy:deploy /home/deploy/padmakara-backend/
chmod -R 755 /home/deploy/padmakara-backend/
```

#### 2. Python Version Issues

```bash
# Check Python version
python3 --version

# If using wrong Python, recreate venv
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 3. Database Connection Issues

```bash
# Test database connection
python manage.py dbshell

# Check PostgreSQL status
sudo systemctl status postgresql
```

#### 4. Static Files Not Loading

```bash
# Recollect static files
python manage.py collectstatic --noinput --clear

# Check nginx configuration
sudo nginx -t
```

### Health Check Commands

```bash
# Django health check
cd ~/padmakara-backend
source venv/bin/activate
python manage.py check

# Test endpoints
curl http://localhost:8000/admin/
curl http://212.227.131.117/admin/

# Check processes
ps aux | grep gunicorn
ps aux | grep nginx
```

## Performance Optimization

### Database Optimization

```bash
# Analyze database performance
python manage.py dbshell
# Run: ANALYZE;
# Run: VACUUM;
```

### Static File Optimization

- Enable gzip compression in Nginx
- Set proper cache headers
- Use CDN for static files (optional)

### Monitoring

- Set up log rotation
- Monitor disk space
- Monitor memory usage
- Set up alerts for service failures

## Security Considerations

1. **Environment Variables**: Never commit .env files
2. **Database**: Use strong passwords, limit access
3. **Firewall**: Only open necessary ports
4. **SSL**: Always use HTTPS in production
5. **Updates**: Keep system packages updated
6. **Backups**: Regular database and code backups

## Backup Strategy

### Automated Backup Script

```bash
#!/bin/bash
# Save as ~/backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/deploy/backups"
mkdir -p $BACKUP_DIR

# Database backup
pg_dump -U padmakara_user -h localhost padmakara_db > $BACKUP_DIR/db_$DATE.sql

# Code backup (optional)
tar -czf $BACKUP_DIR/code_$DATE.tar.gz ~/padmakara-backend --exclude=venv --exclude=__pycache__

# Clean old backups (keep last 7 days)
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

### Cron Job for Backups

```bash
# Add to crontab
crontab -e

# Add line for daily backup at 2 AM
0 2 * * * /home/deploy/backup.sh
```
