"""
Management command to test S3 presigned URL generation
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from retreats.models import Retreat, Session, Track, RetreatGroup, Place, Teacher
from datetime import date
import json


class Command(BaseCommand):
    help = 'Test S3 presigned URL generation for direct uploads'

    def handle(self, *args, **options):
        self.stdout.write("🧪 Testing S3 Presigned URL Generation...")
        
        # Check if S3 is enabled
        use_s3 = getattr(settings, 'USE_S3_FOR_MEDIA', False)
        if not use_s3:
            self.stdout.write("❌ S3 is not enabled. Cannot test presigned URLs.")
            return
        
        self.stdout.write("✅ S3 is enabled, proceeding with test...")
        
        try:
            # Create test data
            group, _ = RetreatGroup.objects.get_or_create(
                name="Test Presigned Group", 
                defaults={'description': 'Test group for presigned URL testing'}
            )
            
            place, _ = Place.objects.get_or_create(
                name="Test Presigned Center",
                defaults={'abbreviation': 'TPC'}
            )
            
            teacher, _ = Teacher.objects.get_or_create(
                name="Test Presigned Teacher",
                defaults={'abbreviation': 'TPT'}
            )
            
            retreat = Retreat.objects.create(
                name="Test Presigned URL Retreat",
                description="This retreat is for testing presigned URL functionality",
                start_date=date.today(),
                end_date=date.today(),
                retreat_type='online',
                status='draft'
            )
            retreat.groups.add(group)
            retreat.places.add(place)
            retreat.teachers.add(teacher)
            
            session = Session.objects.create(
                retreat=retreat,
                title="Test Presigned Session",
                session_date=date.today(),
                session_number=1
            )
            
            self.stdout.write(f"✅ Created test session: {session.title}")
            
            # Test presigned URL generation
            from retreats.views import generate_s3_presigned_url
            from django.test import RequestFactory
            from django.contrib.auth import get_user_model
            import json
            
            User = get_user_model()
            
            # Create a test request
            factory = RequestFactory()
            test_data = {
                'filename': 'test_track_001.mp3',
                'file_size': 5000000  # 5MB
            }
            
            request = factory.post(
                f'/session/{session.id}/generate-presigned-url/',
                data=json.dumps(test_data),
                content_type='application/json'
            )
            
            # Add a staff user to the request
            user = User.objects.filter(is_staff=True).first()
            if not user:
                user = User.objects.create_user(
                    email='test_presigned_user@example.com',
                    is_staff=True
                )
            request.user = user
            
            # Test the presigned URL generation
            response = generate_s3_presigned_url(request, session.id)
            
            if response.status_code == 200:
                import json
                data = json.loads(response.content)
                
                self.stdout.write("✅ Presigned URL generated successfully!")
                self.stdout.write(f"   S3 Key: {data.get('s3_key', 'Not found')}")
                self.stdout.write(f"   Upload ID: {data.get('upload_id', 'Not found')}")
                self.stdout.write(f"   Presigned URL: {data.get('presigned_post', {}).get('url', 'Not found')[:50]}...")
                
                # Check track info parsing
                track_info = data.get('track_info', {})
                self.stdout.write(f"   Track Number: {track_info.get('track_number', 'Not found')}")
                self.stdout.write(f"   Track Title: {track_info.get('title', 'Not found')}")
                
            else:
                self.stdout.write(f"❌ Presigned URL generation failed: HTTP {response.status_code}")
                self.stdout.write(f"   Response: {response.content.decode()}")
            
            # Clean up test data
            retreat.delete()
            if 'Test' in group.name:
                group.delete()
            if 'Test' in place.name:
                place.delete()
            if 'Test' in teacher.name:
                teacher.delete()
            if user.email == 'test_presigned_user@example.com':
                user.delete()
                
            self.stdout.write("🧹 Cleaned up test data")
            
        except Exception as e:
            self.stdout.write(f"❌ Test failed: {str(e)}")
            import traceback
            self.stdout.write(traceback.format_exc())
        
        self.stdout.write("✅ Presigned URL test completed!")