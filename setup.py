#!/usr/bin/env python3
"""
Setup script for Padmakara Django Backend
A comprehensive Buddhist retreat management system built with Django 5.2.4
"""

import os
import sys
import subprocess
import secrets
from pathlib import Path


def run_command(command, description, capture_output=True):
    """Run a command and handle errors"""
    print(f"\n🔧 {description}...")
    try:
        if capture_output:
            result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
            print(f"✅ {description} completed successfully")
            return result.stdout
        else:
            subprocess.run(command, shell=True, check=True)
            print(f"✅ {description} completed successfully")
            return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        if capture_output and e.stderr:
            print(f"Error output: {e.stderr}")
        return False


def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major != 3 or version.minor < 10:
        print("❌ Python 3.10+ is required. Current version:", f"{version.major}.{version.minor}.{version.micro}")
        sys.exit(1)
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} detected")


def create_virtual_environment():
    """Create virtual environment if it doesn't exist"""
    if not Path("venv").exists():
        if not run_command("python -m venv venv", "Creating virtual environment"):
            print("❌ Failed to create virtual environment")
            sys.exit(1)
        print("📝 To activate the virtual environment, run:")
        print("   source venv/bin/activate  # On macOS/Linux")
        print("   venv\\Scripts\\activate     # On Windows")
    else:
        print("✅ Virtual environment already exists")


def install_dependencies():
    """Install Python dependencies"""
    python_path = "venv/bin/python" if os.name != 'nt' else "venv\\Scripts\\python"
    pip_path = "venv/bin/pip" if os.name != 'nt' else "venv\\Scripts\\pip"
    
    if not run_command(f"{pip_path} install --upgrade pip", "Upgrading pip"):
        return False
    
    if not run_command(f"{pip_path} install -r requirements.txt", "Installing Python dependencies"):
        return False
    
    return True


def create_env_file():
    """Create .env file if it doesn't exist"""
    if not Path(".env").exists():
        print("\n📝 Creating .env configuration file...")
        
        # Generate a secure secret key
        secret_key = secrets.token_urlsafe(50)
        
        env_content = f"""# Django Settings
SECRET_KEY={secret_key}
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
ENVIRONMENT=development

# Database Configuration (SQLite for development)
DATABASE_URL=sqlite:///db.sqlite3

# For production PostgreSQL, use:
# DATABASE_URL=postgres://username:password@localhost:5432/padmakara

# Language and Timezone
LANGUAGE_CODE=pt-pt
TIME_ZONE=Europe/Lisbon

# AWS S3 Configuration (Optional - uses local storage if disabled)
USE_S3=False
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_STORAGE_BUCKET_NAME=padmakara-media-files
AWS_S3_REGION_NAME=eu-west-1

# Email Configuration (for user notifications)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@padmakara.pt

# Redis Configuration (for Celery background tasks)
REDIS_URL=redis://localhost:6379/0

# Security Settings
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False

# Sentry Error Tracking (Optional)
# SENTRY_DSN=your-sentry-dsn-here

# JWT Settings
JWT_ACCESS_TOKEN_LIFETIME=60
JWT_REFRESH_TOKEN_LIFETIME=1440
"""
        
        with open(".env", "w") as f:
            f.write(env_content)
        
        print("✅ .env file created with secure settings")
    else:
        print("✅ .env file already exists")


def create_directories():
    """Create necessary directories"""
    directories = ['logs', 'media', 'static', 'staticfiles']
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
    
    print("✅ Created necessary directories")


def run_migrations():
    """Create and apply database migrations"""
    python_path = "venv/bin/python" if os.name != 'nt' else "venv\\Scripts\\python"
    
    # Create migrations
    if not run_command(f"{python_path} manage.py makemigrations", "Creating database migrations"):
        return False
    
    # Apply migrations
    if not run_command(f"{python_path} manage.py migrate", "Applying database migrations"):
        return False
    
    return True


def collect_static_files():
    """Collect static files"""
    python_path = "venv/bin/python" if os.name != 'nt' else "venv\\Scripts\\python"
    
    return run_command(f"{python_path} manage.py collectstatic --noinput", "Collecting static files")


def create_superuser():
    """Create Django superuser"""
    python_path = "venv/bin/python" if os.name != 'nt' else "venv\\Scripts\\python"
    
    print("\n👤 Creating Django superuser...")
    print("You'll need this to access the admin interface")
    
    # Check if superuser already exists
    check_user_cmd = f'echo "from accounts.models import User; print(User.objects.filter(is_superuser=True).exists())" | {python_path} manage.py shell'
    result = run_command(check_user_cmd, "Checking for existing superuser")
    
    if result and "True" in result:
        print("✅ Superuser already exists")
        return True
    
    print("\n📝 Please enter superuser details:")
    
    # Interactive superuser creation
    return run_command(f"{python_path} manage.py createsuperuser", "Creating superuser", capture_output=False)


def run_tests():
    """Run Django tests"""
    python_path = "venv/bin/python" if os.name != 'nt' else "venv\\Scripts\\python"
    
    print("\n🧪 Running Django tests...")
    result = run_command(f"{python_path} manage.py test", "Running tests")
    
    if result:
        print("✅ All tests passed!")
    else:
        print("⚠️  Some tests failed. Check the output above.")
    
    return result


def show_next_steps():
    """Show next steps to the user"""
    print(f"\n{'='*60}")
    print("🎉 Padmakara Django Backend Setup Complete!")
    print(f"{'='*60}")
    
    print("\n📝 Next steps:")
    print("1. Activate virtual environment:")
    if os.name != 'nt':
        print("   source venv/bin/activate")
    else:
        print("   venv\\Scripts\\activate")
    
    print("\n2. Start the development server:")
    print("   python manage.py runserver")
    
    print("\n3. Access the admin interface:")
    print("   http://127.0.0.1:8000/admin/")
    print("   Use the superuser credentials you created")
    
    print("\n4. API endpoints will be available at:")
    print("   http://127.0.0.1:8000/api/")
    
    print("\n📚 Additional commands:")
    print("   python manage.py help              - Show all available commands")
    print("   python manage.py shell             - Django interactive shell")
    print("   python manage.py dbshell           - Database shell")
    print("   python manage.py test              - Run tests")
    
    print(f"\n{'='*60}")
    print("🙏 May your Buddhist retreat management be peaceful and efficient!")
    print(f"{'='*60}")


def main():
    """Main setup function"""
    print("🙏 Welcome to Padmakara Django Backend Setup")
    print("A comprehensive Buddhist retreat management system")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("manage.py").exists():
        print("❌ manage.py not found. Are you in the backend directory?")
        sys.exit(1)
    
    # Check Python version
    check_python_version()
    
    # Setup steps
    create_virtual_environment()
    
    if not install_dependencies():
        print("❌ Failed to install dependencies")
        sys.exit(1)
    
    create_env_file()
    create_directories()
    
    if not run_migrations():
        print("❌ Failed to run migrations")
        sys.exit(1)
    
    collect_static_files()
    
    # Create superuser (interactive)
    create_superuser()
    
    # Run tests
    run_tests()
    
    # Show completion message
    show_next_steps()


if __name__ == "__main__":
    main()