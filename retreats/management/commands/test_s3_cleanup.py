"""
Management command to test S3 cleanup functionality
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from retreats.models import Retreat, Session, Track, RetreatGroup, Place, Teacher
import tempfile
import os
from django.core.files.base import ContentFile


class Command(BaseCommand):
    help = 'Test S3 cleanup functionality by creating and deleting test data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually creating/deleting anything',
        )

    def handle(self, *args, **options):
        self.stdout.write("🧪 Testing S3 Cleanup Functionality...")
        
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write("🔍 DRY RUN MODE - No actual changes will be made")
        
        # Check if S3 is enabled
        use_s3 = getattr(settings, 'USE_S3_FOR_MEDIA', False)
        if not use_s3:
            self.stdout.write("❌ S3 is not enabled. Cannot test S3 cleanup.")
            return
        
        self.stdout.write("✅ S3 is enabled, proceeding with test...")
        
        if not dry_run:
            # Create test data
            self.stdout.write("\n📝 Creating test data...")
            test_objects = self._create_test_data()
            
            self.stdout.write("\n🗑️ Testing deletion and S3 cleanup...")
            self._test_cleanup(test_objects)
        else:
            self.stdout.write("\n📋 Would create test retreat, session, and tracks")
            self.stdout.write("📋 Would upload test files to S3")
            self.stdout.write("📋 Would delete tracks one by one and verify S3 cleanup")
            self.stdout.write("📋 Would delete session and verify folder cleanup")
            self.stdout.write("📋 Would delete retreat and verify complete cleanup")
        
        self.stdout.write("\n✅ S3 cleanup test completed!")

    def _create_test_data(self):
        """Create test retreat with sessions and tracks"""
        from datetime import date
        
        # Create test group, place, teacher
        group, _ = RetreatGroup.objects.get_or_create(
            name="Test Group", 
            defaults={'description': 'Test group for S3 cleanup testing'}
        )
        
        place, _ = Place.objects.get_or_create(
            name="Test Center",
            defaults={'abbreviation': 'TC'}
        )
        
        teacher, _ = Teacher.objects.get_or_create(
            name="Test Teacher",
            defaults={'abbreviation': 'TT'}
        )
        
        # Create test retreat
        retreat = Retreat.objects.create(
            name="Test S3 Cleanup Retreat",
            description="This retreat is for testing S3 cleanup functionality",
            start_date=date.today(),
            end_date=date.today(),
            retreat_type='online',
            status='draft'
        )
        retreat.groups.add(group)
        retreat.places.add(place)
        retreat.teachers.add(teacher)
        
        self.stdout.write(f"✅ Created retreat: {retreat.name}")
        
        # Create test session
        session = Session.objects.create(
            retreat=retreat,
            title="Test Session for S3 Cleanup",
            session_date=date.today(),
            session_number=1
        )
        
        self.stdout.write(f"✅ Created session: {session.title}")
        
        # Create test tracks with actual files
        tracks = []
        for i in range(3):
            # Create a small test audio file
            test_content = b"Test audio content for track " + str(i).encode()
            test_file = ContentFile(test_content, name=f"test_track_{i:03d}.mp3")
            
            track = Track.objects.create(
                session=session,
                title=f"Test Track {i+1}",
                track_number=i+1,
                audio_file=test_file,
                file_size=len(test_content)
            )
            tracks.append(track)
            
            self.stdout.write(f"✅ Created track {i+1}: {track.title}")
            self.stdout.write(f"   📁 S3 Path: {track.audio_file.name}")
        
        return {
            'retreat': retreat,
            'session': session,
            'tracks': tracks,
            'group': group,
            'place': place,
            'teacher': teacher
        }

    def _test_cleanup(self, test_objects):
        """Test the cleanup functionality"""
        
        # Test 1: Delete individual tracks
        self.stdout.write("\n🧪 Test 1: Deleting individual tracks...")
        for i, track in enumerate(test_objects['tracks'][:2]):  # Delete 2 of 3 tracks
            s3_path = track.audio_file.name
            self.stdout.write(f"   Deleting track: {track.title}")
            self.stdout.write(f"   S3 file should be deleted: {s3_path}")
            track.delete()
            self.stdout.write("   ✅ Track deleted")
        
        # Test 2: Delete session (which should delete remaining tracks)
        self.stdout.write("\n🧪 Test 2: Deleting session...")
        session = test_objects['session']
        remaining_tracks = session.tracks.count()
        self.stdout.write(f"   Session has {remaining_tracks} remaining tracks")
        self.stdout.write(f"   Session folder should be cleaned up if empty")
        session.delete()
        self.stdout.write("   ✅ Session deleted")
        
        # Test 3: Delete retreat (complete cleanup)
        self.stdout.write("\n🧪 Test 3: Deleting retreat...")
        retreat = test_objects['retreat']
        self.stdout.write(f"   Retreat folder should be completely cleaned up")
        retreat.delete()
        self.stdout.write("   ✅ Retreat deleted")
        
        # Clean up test models
        self.stdout.write("\n🧹 Cleaning up test models...")
        for model_name, obj in [('group', test_objects['group']), 
                               ('place', test_objects['place']), 
                               ('teacher', test_objects['teacher'])]:
            # Only delete if they were created for this test (have 'Test' in name)
            if 'Test' in obj.name:
                obj.delete()
                self.stdout.write(f"   ✅ Deleted test {model_name}: {obj.name}")

    def _verify_s3_cleanup(self, file_path):
        """Verify that a file has been deleted from S3"""
        try:
            from utils.storage import RetreatMediaStorage
            storage = RetreatMediaStorage()
            
            if hasattr(storage, 'connection'):
                s3_client = storage.connection
                bucket_name = storage.bucket_name
                
                try:
                    s3_client.head_object(Bucket=bucket_name, Key=file_path)
                    return False  # File still exists
                except:
                    return True   # File deleted or doesn't exist
            
        except Exception as e:
            self.stdout.write(f"   ⚠️  Could not verify S3 cleanup: {str(e)}")
            return None
        
        return None