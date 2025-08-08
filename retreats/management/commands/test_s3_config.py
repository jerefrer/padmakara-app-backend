"""
Management command to test S3 configuration without exposing credentials
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.base import ContentFile
from retreats.models import Track
import tempfile
import os


class Command(BaseCommand):
    help = 'Test S3 configuration and upload functionality'

    def handle(self, *args, **options):
        self.stdout.write("🔍 Testing S3 Configuration...")
        
        # Check basic settings
        use_s3 = getattr(settings, 'USE_S3_FOR_MEDIA', False)
        self.stdout.write(f"USE_S3_FOR_MEDIA: {use_s3}")
        
        default_storage = getattr(settings, 'DEFAULT_FILE_STORAGE', 'Not set')
        self.stdout.write(f"DEFAULT_FILE_STORAGE: {default_storage}")
        
        # Check AWS settings (without showing values)
        aws_settings = [
            'AWS_ACCESS_KEY_ID',
            'AWS_SECRET_ACCESS_KEY', 
            'AWS_STORAGE_BUCKET_NAME',
            'AWS_S3_REGION_NAME'
        ]
        
        for setting_name in aws_settings:
            value = getattr(settings, setting_name, None)
            if value:
                self.stdout.write(f"✅ {setting_name}: [CONFIGURED]")
            else:
                self.stdout.write(f"❌ {setting_name}: [NOT SET]")
        
        # Test file storage
        if use_s3:
            self.stdout.write("\n🧪 Testing S3 Upload...")
            try:
                # Create a small test file
                test_content = b"Test file for S3 upload verification"
                test_file = ContentFile(test_content, name="test_upload.txt")
                
                # Try to get storage backend
                from utils.storage import RetreatMediaStorage
                storage = RetreatMediaStorage()
                
                # Test upload
                file_path = storage.save("test/test_upload.txt", test_file)
                self.stdout.write(f"✅ Test upload successful: {file_path}")
                
                # Test URL generation
                url = storage.url(file_path)
                self.stdout.write(f"✅ File URL generated: {url[:50]}...")
                
                # Clean up test file
                storage.delete(file_path)
                self.stdout.write("✅ Test file cleaned up")
                
                self.stdout.write("🎉 S3 configuration is working correctly!")
                
            except Exception as e:
                self.stdout.write(f"❌ S3 test failed: {str(e)}")
                self.stdout.write("💡 Check your AWS credentials and bucket configuration")
        else:
            self.stdout.write("ℹ️  S3 is disabled (USE_S3_FOR_MEDIA=False)")
            self.stdout.write("💡 To enable S3: set USE_S3=True in your .env file")
        
        self.stdout.write("\n📋 Configuration Summary:")
        if use_s3:
            self.stdout.write("- S3 storage is ENABLED")
            self.stdout.write("- Files will be uploaded to S3 bucket")
            self.stdout.write("- Directory structure: YYYY.MM.DD-DD — Retreat Name/Session/Track.mp3")
        else:
            self.stdout.write("- Local storage is ACTIVE") 
            self.stdout.write("- Files will be saved to local media directory")
            self.stdout.write("- To use S3: configure AWS credentials in .env")