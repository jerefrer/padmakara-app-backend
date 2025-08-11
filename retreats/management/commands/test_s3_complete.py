"""
Comprehensive S3 configuration test including presigned URLs and public access
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.base import ContentFile
import tempfile
import os
import time
import requests


class Command(BaseCommand):
    help = 'Comprehensive test of S3 configuration, presigned URLs, and public access'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-cleanup',
            action='store_true',
            help='Skip cleanup of test files (useful for debugging)',
        )

    def handle(self, *args, **options):
        self.skip_cleanup = options.get('skip_cleanup', False)
        self.test_file_key = None
        
        self.stdout.write(self.style.HTTP_INFO("🔍 Comprehensive S3 Configuration Test"))
        self.stdout.write("=" * 60)
        
        # Check basic configuration
        if not self._check_basic_config():
            return
            
        # Test S3 connection and permissions
        if not self._test_s3_connection():
            return
            
        # Test presigned URL generation
        if not self._test_presigned_urls():
            return
            
        # Test public access via presigned URLs
        if not self._test_public_access():
            return
            
        # Cleanup
        if not self.skip_cleanup:
            self._cleanup_test_files()
        else:
            self.stdout.write(self.style.WARNING("⚠️  Skipping cleanup - test file remains in S3"))
            
        self.stdout.write(self.style.SUCCESS("\n🎉 All S3 tests passed! Configuration is working correctly."))

    def _check_basic_config(self):
        """Check basic S3 configuration settings"""
        self.stdout.write(self.style.HTTP_INFO("\n1. Checking Basic Configuration"))
        self.stdout.write("-" * 40)
        
        use_s3 = getattr(settings, 'USE_S3_FOR_MEDIA', False)
        if not use_s3:
            self.stdout.write(self.style.ERROR("❌ S3 is disabled (USE_S3_FOR_MEDIA=False)"))
            self.stdout.write("💡 Enable S3 by setting USE_S3=True in your .env file")
            return False
            
        self.stdout.write(self.style.SUCCESS("✅ S3 is enabled"))
        
        # Check required AWS settings
        aws_settings = {
            'AWS_ACCESS_KEY_ID': 'AWS Access Key ID',
            'AWS_SECRET_ACCESS_KEY': 'AWS Secret Access Key', 
            'AWS_STORAGE_BUCKET_NAME': 'S3 Bucket Name',
            'AWS_S3_REGION_NAME': 'S3 Region'
        }
        
        missing_settings = []
        for setting_name, description in aws_settings.items():
            value = getattr(settings, setting_name, None)
            if value:
                # Mask sensitive values
                if 'SECRET' in setting_name or 'KEY' in setting_name:
                    display_value = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "[CONFIGURED]"
                else:
                    display_value = value
                self.stdout.write(f"✅ {description}: {display_value}")
            else:
                self.stdout.write(self.style.ERROR(f"❌ {description}: [NOT SET]"))
                missing_settings.append(setting_name)
        
        if missing_settings:
            self.stdout.write(self.style.ERROR(f"\n❌ Missing required settings: {', '.join(missing_settings)}"))
            return False
            
        return True

    def _test_s3_connection(self):
        """Test S3 connection and basic operations"""
        self.stdout.write(self.style.HTTP_INFO("\n2. Testing S3 Connection & Upload"))
        self.stdout.write("-" * 40)
        
        try:
            # Create test content
            test_content = b"Padmakara S3 Test File - " + str(time.time()).encode()
            test_file = ContentFile(test_content, name="s3_test.txt")
            
            # Get storage backend
            from utils.storage import RetreatMediaStorage
            storage = RetreatMediaStorage()
            
            # Test upload
            self.test_file_key = storage.save("test-uploads/s3_config_test.txt", test_file)
            self.stdout.write(self.style.SUCCESS(f"✅ File uploaded successfully: {self.test_file_key}"))
            
            # Test file existence
            if storage.exists(self.test_file_key):
                self.stdout.write(self.style.SUCCESS("✅ File exists in S3"))
            else:
                self.stdout.write(self.style.ERROR("❌ File upload failed - file not found"))
                return False
                
            # Test file size
            file_size = storage.size(self.test_file_key)
            expected_size = len(test_content)
            if file_size == expected_size:
                self.stdout.write(self.style.SUCCESS(f"✅ File size correct: {file_size} bytes"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ File size mismatch: expected {expected_size}, got {file_size}"))
                return False
                
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ S3 connection test failed: {str(e)}"))
            self.stdout.write("💡 Check your AWS credentials, bucket permissions, and network connectivity")
            return False

    def _test_presigned_urls(self):
        """Test presigned URL generation"""
        self.stdout.write(self.style.HTTP_INFO("\n3. Testing Presigned URL Generation"))
        self.stdout.write("-" * 40)
        
        try:
            from utils.storage import RetreatMediaStorage
            import boto3
            from botocore.exceptions import ClientError
            
            # Create boto3 client directly to test presigned URL generation
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            
            # Test presigned URL for GET (download)
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                    'Key': self.test_file_key
                },
                ExpiresIn=3600  # 1 hour
            )
            
            if presigned_url and presigned_url.startswith('https://'):
                self.stdout.write(self.style.SUCCESS("✅ Presigned GET URL generated successfully"))
                self.stdout.write(f"   URL: {presigned_url[:60]}...")
                self.presigned_url = presigned_url
            else:
                self.stdout.write(self.style.ERROR("❌ Invalid presigned URL generated"))
                return False
                
            # Test presigned URL for PUT (upload) - this tests the complete permissions
            try:
                put_url = s3_client.generate_presigned_url(
                    'put_object',
                    Params={
                        'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                        'Key': 'test-uploads/presigned_put_test.txt',
                        'ContentType': 'text/plain'
                    },
                    ExpiresIn=3600
                )
                self.stdout.write(self.style.SUCCESS("✅ Presigned PUT URL generated successfully"))
            except ClientError as e:
                self.stdout.write(self.style.ERROR(f"❌ Presigned PUT URL generation failed: {e}"))
                self.stdout.write("💡 Your IAM user may lack s3:PutObject permissions")
                return False
                
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Presigned URL generation failed: {str(e)}"))
            return False

    def _test_public_access(self):
        """Test public access via presigned URL"""
        self.stdout.write(self.style.HTTP_INFO("\n4. Testing Public Access via Presigned URL"))
        self.stdout.write("-" * 40)
        
        if not hasattr(self, 'presigned_url'):
            self.stdout.write(self.style.ERROR("❌ No presigned URL available for testing"))
            return False
            
        try:
            # Test HTTP GET request to presigned URL
            self.stdout.write("🌐 Testing HTTP request to presigned URL...")
            response = requests.get(self.presigned_url, timeout=30)
            
            if response.status_code == 200:
                self.stdout.write(self.style.SUCCESS(f"✅ HTTP GET successful (status: {response.status_code})"))
                
                # Verify content
                content = response.content
                if b"Padmakara S3 Test File" in content:
                    self.stdout.write(self.style.SUCCESS("✅ File content verified"))
                else:
                    self.stdout.write(self.style.WARNING("⚠️  File content doesn't match expected"))
                    
                # Test headers
                content_type = response.headers.get('content-type', '')
                if 'text' in content_type.lower():
                    self.stdout.write(self.style.SUCCESS(f"✅ Content-Type header: {content_type}"))
                else:
                    self.stdout.write(f"ℹ️  Content-Type: {content_type}")
                    
            elif response.status_code == 403:
                self.stdout.write(self.style.ERROR(f"❌ HTTP GET failed with 403 Forbidden"))
                self.stdout.write("💡 This indicates S3 bucket permissions or IAM policy issues")
                self.stdout.write("   Check that your IAM user has s3:GetObject permissions")
                self.stdout.write("   Check that your S3 bucket policy allows access")
                return False
            else:
                self.stdout.write(self.style.ERROR(f"❌ HTTP GET failed (status: {response.status_code})"))
                self.stdout.write(f"   Response: {response.text[:200]}...")
                return False
                
            # Test CORS headers for web access
            self._test_cors_headers(response)
                
            return True
            
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f"❌ HTTP request failed: {str(e)}"))
            self.stdout.write("💡 Check network connectivity and S3 bucket configuration")
            return False

    def _test_cors_headers(self, response):
        """Test CORS headers in the response"""
        self.stdout.write(self.style.HTTP_INFO("\n   🌐 CORS Headers Check:"))
        
        cors_headers = {
            'Access-Control-Allow-Origin': 'Allows cross-origin requests',
            'Access-Control-Allow-Methods': 'Allowed HTTP methods',
            'Access-Control-Allow-Headers': 'Allowed request headers',
            'Access-Control-Expose-Headers': 'Headers exposed to client',
        }
        
        found_cors = False
        for header, description in cors_headers.items():
            value = response.headers.get(header)
            if value:
                self.stdout.write(f"   ✅ {header}: {value}")
                found_cors = True
            else:
                self.stdout.write(f"   ⚪ {header}: [not present]")
                
        if not found_cors:
            self.stdout.write(self.style.WARNING("   ⚠️  No CORS headers found"))
            self.stdout.write("   💡 Configure CORS on your S3 bucket for web app access")
        else:
            self.stdout.write(self.style.SUCCESS("   ✅ CORS headers are configured"))

    def _cleanup_test_files(self):
        """Clean up test files from S3"""
        self.stdout.write(self.style.HTTP_INFO("\n5. Cleaning Up Test Files"))
        self.stdout.write("-" * 40)
        
        if not self.test_file_key:
            self.stdout.write("ℹ️  No test files to clean up")
            return
            
        try:
            from utils.storage import RetreatMediaStorage
            storage = RetreatMediaStorage()
            
            if storage.exists(self.test_file_key):
                storage.delete(self.test_file_key)
                self.stdout.write(self.style.SUCCESS(f"✅ Test file deleted: {self.test_file_key}"))
            else:
                self.stdout.write("ℹ️  Test file already removed")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Cleanup failed: {str(e)}"))
            self.stdout.write(f"💡 Manually delete test file: {self.test_file_key}")

    def _print_troubleshooting_guide(self):
        """Print troubleshooting guide for common issues"""
        self.stdout.write(self.style.HTTP_INFO("\n🔧 Troubleshooting Guide"))
        self.stdout.write("=" * 60)
        
        self.stdout.write("""
Common Issues and Solutions:

1. 403 Forbidden Errors:
   - Check IAM user permissions (s3:GetObject, s3:PutObject, s3:DeleteObject)
   - Verify S3 bucket policy allows your IAM user
   - Ensure bucket is in the correct region

2. CORS Issues (for web apps):
   - Configure CORS policy on your S3 bucket
   - Allow origins: localhost:8081, your production domain
   - Allow methods: GET, PUT, POST, DELETE, HEAD

3. Connection Issues:
   - Verify AWS credentials are correct
   - Check network connectivity to AWS
   - Ensure region setting matches bucket location

4. Permission Denied:
   - IAM user needs s3:ListBucket on bucket resource
   - IAM user needs s3:GetObject, s3:PutObject on bucket/* resource
   - Check for any explicit DENY policies
        """)