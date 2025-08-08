# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **Padmakara**, a comprehensive Buddhist retreat management system built with Django 5.2.4. The system manages retreats, sessions, audio tracks, user progress, and provides analytics for Buddhist centers and practitioners.

## Setup and Development Commands

### Initial Setup
```bash
python setup.py                    # Run complete setup (creates venv, installs deps, migrations, superuser)
source venv/bin/activate           # Activate virtual environment (macOS/Linux)
venv\Scripts\activate              # Activate virtual environment (Windows)
```

### Development Commands
```bash
python manage.py runserver         # Start development server
python manage.py test              # Run all tests
python manage.py makemigrations    # Create new migrations
python manage.py migrate           # Apply database migrations
python manage.py collectstatic     # Collect static files
python manage.py shell             # Django shell
python manage.py createsuperuser   # Create admin user
```

### Management Commands (Custom)
```bash
python manage.py check_s3_cors            # Check S3 CORS configuration
python manage.py configure_s3_cors        # Configure S3 CORS settings
python manage.py test_presigned_url       # Test S3 presigned URL generation
python manage.py test_s3_cleanup          # Test S3 file cleanup
python manage.py test_s3_config           # Test S3 configuration
```

## Architecture Overview

### Django Apps Structure
- **accounts/** - User management with Buddhist-specific fields (dharma names, subscription plans)
- **retreats/** - Core retreat management (groups, retreats, sessions, tracks, places, teachers)
- **content/** - User interaction with content (progress, bookmarks, PDF highlights, downloads, notes)
- **analytics/** - Usage statistics, popular content tracking, recommendations, system health
- **utils/** - Shared utilities (S3 storage, track filename parsing)

### Key Models & Relationships

**Core Hierarchy:**
```
RetreatGroup → Retreat → Session → Track
    ↓              ↓        ↓       ↓
  Places      Teachers  Progress  Bookmarks
```

**User Models:**
- `User` (custom auth with dharma_name, subscription fields)
- `UserPreferences` (theme, audio settings, notifications)
- `UserActivity` (activity tracking)
- `UserGroupMembership` (group membership management)

**Content Models:**
- `UserProgress` (audio tracking with completion percentage)
- `Bookmark` (position-based bookmarks in tracks)
- `PDFHighlight` (highlights in transcript PDFs)
- `DownloadedContent` (offline content management)
- `UserNotes` (personal notes on tracks/retreats)

### File Storage System

**S3 Organization:**
Audio files are stored in structured folders:
```
2025.04.12-13 - GROUP - PLACE - TEACHER/
├── SESSION NAME/
│   ├── original_filename.mp3
│   └── other_tracks.mp3
└── transcripts/
    └── SESSION NAME/
        └── transcript.pdf
```

**Storage Classes:**
- `RetreatMediaStorage` - Custom S3 storage with private files and signed URLs
- Upload path functions in `utils/storage.py` handle automatic folder organization

### Admin Interface

Uses **Django Unfold** for modern Portuguese admin interface with:
- Step-by-step workflow (Retreat → Sessions → Tracks)
- Bulk audio file upload with automatic track parsing
- Visual status indicators and progress tracking
- Enhanced fieldsets with contextual help
- Import/export functionality

### Key Features

1. **Multi-language Support** (Portuguese/English)
2. **S3 Integration** with automatic file cleanup
3. **Audio Progress Tracking** with precise position saving
4. **PDF Transcript System** with highlighting and bookmarks
5. **User Analytics** with engagement scoring
6. **Content Recommendations** based on user behavior
7. **Subscription Management** (basic, premium, lifetime)
8. **Retreat Lifecycle Management** (draft → upcoming → ongoing → completed)

## Development Guidelines

### Database Configuration
- **Development:** SQLite (default)
- **Production:** PostgreSQL via `DATABASE_URL`
- Custom user model: `accounts.User`
- Timezone: Europe/Lisbon (configurable)

### File Handling
- Audio files: MP3, WAV, M4A, AAC, FLAC, OGG
- Transcripts: PDF files stored in `transcripts/` subfolder
- Images: Retreat images and user avatars
- **S3 Configuration:** Set `USE_S3=True` in .env for S3 storage

### Important Patterns

**Custom Admin Forms:**
- Use `UnfoldAdminCheckboxSelectMultiple` for many-to-many fields
- Implement step-by-step workflows (avoid complex inlines)
- Add visual status indicators and next-step guidance

**File Upload Processing:**
- Use `utils/track_parser.py` for filename parsing
- Extract track numbers and clean titles automatically
- Handle audio file validation and duration estimation

**S3 File Cleanup:**
- Override model `delete()` methods for proper S3 cleanup
- Use Django signals for bulk delete operations
- Clean up empty folders after file deletion

**Progress Tracking:**
- Update `UserProgress` models for listening activity
- Use completion percentage (95%+ = completed)
- Track total listening time and play counts

### Environment Configuration

Key environment variables (see `.env.example`):
```bash
SECRET_KEY=generated-key
DEBUG=True|False
DATABASE_URL=sqlite:///db.sqlite3 OR postgres://...
USE_S3=True|False
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_STORAGE_BUCKET_NAME=bucket-name
AWS_S3_REGION_NAME=eu-west-1
LANGUAGE_CODE=pt-pt
TIME_ZONE=Europe/Lisbon
```

### Testing
- Run tests with `python manage.py test`
- Test files in `utils/test_track_parser.py` for filename parsing
- S3 management commands for testing storage integration

### Common Workflows

1. **Creating Retreats:**
   - Create RetreatGroup, Place, Teacher (if needed)
   - Create Retreat with basic info
   - Add Sessions to the retreat
   - Bulk upload audio tracks to sessions

2. **User Management:**
   - Custom User model with subscription fields
   - UserPreferences automatically created via OneToOne
   - Activity tracking via UserActivity model

3. **Content Interaction:**
   - Track progress via UserProgress updates
   - Handle bookmarks at specific positions
   - Manage PDF highlights with position data
   - Track downloads for offline access

## Production Considerations

- Use `gunicorn` for WSGI server
- Configure `whitenoise` for static file serving
- Set up Redis for Celery background tasks
- Enable Sentry for error tracking
- Configure SSL/TLS certificates
- Set proper CORS origins for frontend integration

This system is designed to serve Buddhist communities with features tailored for retreat audio content, meditation tracking, and spiritual progress monitoring.