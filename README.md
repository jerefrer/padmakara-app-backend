# Padmakara Django Backend

A comprehensive Buddhist retreat management system built with Django 5.2.4, designed to support retreat centers, teachers, and practitioners in their spiritual journey.

## Features

### 🧘‍♂️ User Management
- **Custom User Model** with Buddhist-specific fields (dharma name, years practicing, favorite teacher)
- **Subscription Management** with different plans (basic, premium, lifetime)
- **User Preferences** for personalized experience
- **Activity Tracking** for engagement analytics

### 🏔️ Retreat Management
- **Retreat Groups** for organizing by teacher or center
- **Complete Retreat Lifecycle** (draft → upcoming → ongoing → completed)
- **Session Management** with flexible scheduling
- **Multi-track Audio Content** with transcript support
- **Participant Management** with registration and progress tracking

### 📚 Content Management
- **Progress Tracking** for audio listening
- **Bookmarks** for important moments in teachings
- **PDF Transcripts** with highlighting support
- **Offline Downloads** for mobile access
- **Personal Notes** system

### 📊 Analytics & Insights
- **Daily Usage Statistics** for administrators
- **Popular Content** tracking and recommendations
- **User Engagement** metrics and scoring
- **System Health** monitoring
- **Content Recommendations** based on user behavior

### 🌐 Multi-language Support
- **Portuguese/English** interface
- **Content in multiple languages**
- **Localized admin interface**

### 🎨 Beautiful Admin Interface
- **Modern Portuguese Admin** with django-admin-interface
- **Import/Export** functionality
- **Advanced filtering** and search
- **Inline editing** for related models
- **Rich media support**

## Technology Stack

- **Backend**: Django 5.2.4, Python 3.10+
- **Database**: SQLite (development), PostgreSQL (production)
- **API**: Django REST Framework with JWT authentication
- **File Storage**: Local files or AWS S3
- **Background Tasks**: Celery with Redis
- **Admin Interface**: Django Admin with beautiful themes
- **Import/Export**: django-import-export

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Git

### Installation

1. **Clone the repository**
   ```bash
   cd backend
   ```

2. **Run the setup script**
   ```bash
   python setup.py
   ```
   
   This will:
   - Create a virtual environment
   - Install all dependencies
   - Create database migrations
   - Set up configuration files
   - Create a superuser account
   - Run tests

3. **Activate virtual environment**
   ```bash
   source venv/bin/activate  # macOS/Linux
   # or
   venv\Scripts\activate     # Windows
   ```

4. **Start the development server**
   ```bash
   python manage.py runserver
   ```

5. **Access the admin interface**
   - Open http://127.0.0.1:8000/admin/
   - Login with your superuser credentials

## Configuration

### Environment Variables

The setup script creates a `.env` file with all necessary configuration. Key settings:

```env
# Django Core
SECRET_KEY=auto-generated-secure-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=sqlite:///db.sqlite3

# Language/Timezone
LANGUAGE_CODE=pt-pt
TIME_ZONE=Europe/Lisbon

# AWS S3 (Optional)
USE_S3=False
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_STORAGE_BUCKET_NAME=your-bucket

# Email
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Redis (for background tasks)
REDIS_URL=redis://localhost:6379/0
```

### Production Deployment

For production deployment:

1. **Update environment variables**
   ```env
   DEBUG=False
   ALLOWED_HOSTS=your-domain.com
   DATABASE_URL=postgres://user:pass@host:5432/dbname
   USE_S3=True
   # Add your AWS credentials
   ```

2. **Install production dependencies**
   ```bash
   pip install gunicorn whitenoise
   ```

3. **Collect static files**
   ```bash
   python manage.py collectstatic --noinput
   ```

4. **Run with Gunicorn**
   ```bash
   gunicorn padmakara.wsgi:application --bind 0.0.0.0:8000
   ```

## API Documentation

### Authentication

The API uses JWT (JSON Web Tokens) for authentication.

**Login**
```bash
POST /api/auth/login/
{
  "email": "user@example.com",
  "password": "password"
}
```

**Register**
```bash
POST /api/auth/register/
{
  "email": "user@example.com",
  "password": "password",
  "first_name": "John",
  "last_name": "Doe",
  "dharma_name": "Mindful Walker"
}
```

### Main Endpoints

- **Users**: `/api/auth/` - User management and authentication
- **Retreats**: `/api/retreats/` - Retreat groups, retreats, sessions, tracks
- **Content**: `/api/content/` - Progress, bookmarks, downloads, notes
- **Analytics**: `/api/analytics/` - Usage statistics and insights

## Development

### Running Tests

```bash
python manage.py test
```

### Creating Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Admin Interface

Access the beautiful Portuguese admin interface at `/admin/` with features:

- **User Management** with Buddhist-specific fields
- **Retreat Organization** with full lifecycle management
- **Content Management** with file uploads
- **Analytics Dashboard** with usage insights
- **Import/Export** functionality for bulk operations

### Database Schema

The system includes four main Django apps:

1. **accounts** - User management and authentication
2. **retreats** - Retreat groups, retreats, sessions, and tracks
3. **content** - User progress, bookmarks, and content interaction
4. **analytics** - Usage statistics and recommendations

## Project Structure

```
backend/
├── accounts/           # User management
├── retreats/          # Retreat management
├── content/           # Content tracking
├── analytics/         # Analytics and insights
├── padmakara/         # Django project settings
├── static/            # Static files
├── media/             # User uploads
├── logs/              # Application logs
├── requirements.txt   # Python dependencies
├── setup.py          # Automated setup script
└── manage.py         # Django management
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is designed for Buddhist retreat centers and spiritual communities. Please use it mindfully and in service of the dharma.

## Support

For questions or support:
- Check the Django documentation
- Review the code comments and docstrings
- Open an issue on the repository

---

🙏 *May this software serve the spreading of wisdom and compassion*