#!/bin/bash
# Setup passwordless sudo for deployment operations
# Run this script ON THE SERVER as a user with sudo access

set -e

echo "Setting up passwordless sudo for deployment user..."

# Check if we're running as root or with sudo
if [[ $EUID -ne 0 ]] && ! sudo -n true 2>/dev/null; then
    echo "This script needs to be run with sudo privileges"
    echo "Usage: sudo $0"
    exit 1
fi

# Create the sudoers file
sudo tee /etc/sudoers.d/deploy << 'EOF'
# Sudoers configuration for padmakara deployment user
# Allow deploy user to run specific commands without password

deploy ALL=(ALL) NOPASSWD: /bin/systemctl reload nginx
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart nginx
deploy ALL=(ALL) NOPASSWD: /bin/systemctl status nginx
deploy ALL=(ALL) NOPASSWD: /usr/bin/supervisorctl restart padmakara-backend
deploy ALL=(ALL) NOPASSWD: /usr/bin/supervisorctl status padmakara-backend
deploy ALL=(ALL) NOPASSWD: /usr/bin/supervisorctl status
deploy ALL=(ALL) NOPASSWD: /usr/bin/tail -[0-9]* /var/log/padmakara-backend.log
deploy ALL=(ALL) NOPASSWD: /usr/bin/tail -[0-9]* /var/log/nginx/error.log
deploy ALL=(ALL) NOPASSWD: /usr/bin/tail -[0-9]* /var/log/supervisor/padmakara_backend_error.log
deploy ALL=(ALL) NOPASSWD: /usr/bin/tail -[0-9]* /var/log/supervisor/padmakara_backend_access.log
EOF

# Set proper permissions
sudo chmod 440 /etc/sudoers.d/deploy

# Test the configuration
sudo visudo -c -f /etc/sudoers.d/deploy

if [ $? -eq 0 ]; then
    echo "✅ Sudoers configuration installed successfully!"
    echo ""
    echo "The deploy user can now run these commands without a password:"
    echo "  - systemctl reload/restart/status nginx"
    echo "  - supervisorctl restart/status padmakara-backend"  
    echo "  - tail log files"
    echo ""
    echo "Test it with: sudo -u deploy sudo supervisorctl status"
else
    echo "❌ Error in sudoers configuration!"
    sudo rm -f /etc/sudoers.d/deploy
    exit 1
fi