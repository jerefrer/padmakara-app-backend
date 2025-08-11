"""
Management command to test S3 configuration and basic functionality
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.base import ContentFile
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


class Command(BaseCommand):
    help = 'Test S3 configuration, permissions, and basic functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed AWS permission testing',
        )

    def handle(self, *args, **options):
        self.detailed = options.get('detailed', False)
        
        self.stdout.write(self.style.HTTP_INFO("🔍 Testing S3 Configuration..."))
        self.stdout.write("=" * 50)
        
        # Check basic settings
        if not self._check_basic_settings():
            return
            
        # Test AWS connection
        if not self._test_aws_connection():
            return
            
        # Test file operations
        if not self._test_file_operations():
            return
            
        # Test presigned URL basics
        if self.detailed:
            self._test_presigned_url_basics()
            
        self.stdout.write(self.style.SUCCESS("\n🎉 Basic S3 configuration is working!"))
        self.stdout.write(self.style.HTTP_INFO("💡 Run 'python manage.py test_s3_complete' for comprehensive testing"))

    def _check_basic_settings(self):
        """Check basic S3 configuration"""
        self.stdout.write(self.style.HTTP_INFO("\n1. Configuration Check"))
        self.stdout.write("-" * 30)
        
        use_s3 = getattr(settings, 'USE_S3_FOR_MEDIA', False)
        if not use_s3:
            self.stdout.write(self.style.ERROR("❌ S3 is disabled (USE_S3_FOR_MEDIA=False)"))
            self.stdout.write("💡 To enable S3: set USE_S3=True in your .env file")
            return False
            
        self.stdout.write(self.style.SUCCESS("✅ S3 is enabled"))
        
        # Check required settings
        aws_settings = {
            'AWS_ACCESS_KEY_ID': 'Access Key ID',
            'AWS_SECRET_ACCESS_KEY': 'Secret Access Key', 
            'AWS_STORAGE_BUCKET_NAME': 'Bucket Name',
            'AWS_S3_REGION_NAME': 'Region'
        }
        
        missing = []
        for setting_name, description in aws_settings.items():
            value = getattr(settings, setting_name, None)
            if value:
                if 'SECRET' in setting_name:
                    display = "[CONFIGURED - HIDDEN]"
                elif 'KEY' in setting_name and len(value) > 8:
                    display = f"{value[:4]}...{value[-4:]}"
                else:
                    display = value
                self.stdout.write(f"✅ {description}: {display}")
            else:
                self.stdout.write(self.style.ERROR(f"❌ {description}: [NOT SET]"))
                missing.append(setting_name)
        
        if missing:
            self.stdout.write(self.style.ERROR(f"\n❌ Missing: {', '.join(missing)}"))
            return False
            
        return True

    def _test_aws_connection(self):
        """Test AWS connection and bucket access"""
        self.stdout.write(self.style.HTTP_INFO("\n2. AWS Connection & Bucket Test"))
        self.stdout.write("-" * 30)
        
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            
            # Test bucket access directly (no need to list all buckets)
            bucket = settings.AWS_STORAGE_BUCKET_NAME
            try:
                s3_client.head_bucket(Bucket=bucket)
                self.stdout.write(self.style.SUCCESS(f"✅ Bucket accessible: {bucket}"))
                self.stdout.write(self.style.SUCCESS("✅ AWS credentials valid"))
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404':
                    self.stdout.write(self.style.ERROR(f"❌ Bucket not found: {bucket}"))
                elif error_code == '403':
                    self.stdout.write(self.style.ERROR(f"❌ Access denied to bucket: {bucket}"))
                    self.stdout.write("💡 Check IAM permissions for the bucket")
                else:
                    self.stdout.write(self.style.ERROR(f"❌ Bucket error: {error_code}"))
                return False
                
            # Test bucket region
            try:
                region = s3_client.get_bucket_location(Bucket=bucket)['LocationConstraint']
                if region is None:
                    region = 'us-east-1'  # Default region
                    
                if region == settings.AWS_S3_REGION_NAME:
                    self.stdout.write(self.style.SUCCESS(f"✅ Region match: {region}"))
                else:
                    self.stdout.write(self.style.WARNING(f"⚠️  Region mismatch: bucket={region}, config={settings.AWS_S3_REGION_NAME}"))
            except ClientError:
                self.stdout.write(self.style.WARNING("⚠️  Cannot verify bucket region (may not have ListBucket permission)"))
                
            return True
            
        except NoCredentialsError:
            self.stdout.write(self.style.ERROR("❌ AWS credentials not found or invalid"))
            return False
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'InvalidAccessKeyId':
                self.stdout.write(self.style.ERROR("❌ Invalid AWS Access Key ID"))
            elif error_code == 'SignatureDoesNotMatch':
                self.stdout.write(self.style.ERROR("❌ Invalid AWS Secret Access Key"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ AWS connection failed: {error_code}"))
            return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Unexpected error: {e}"))
            return False

    def _test_file_operations(self):
        """Test file upload, download, and delete operations"""
        self.stdout.write(self.style.HTTP_INFO("\n3. File Operations Test"))
        self.stdout.write("-" * 30)
        
        test_key = "test/config_test.txt"
        
        try:
            # Test using Django storage
            from utils.storage import RetreatMediaStorage
            storage = RetreatMediaStorage()
            
            # Create test content
            test_content = b"Padmakara S3 configuration test"
            test_file = ContentFile(test_content, name="config_test.txt")
            
            # Test upload
            file_path = storage.save(test_key, test_file)
            self.stdout.write(self.style.SUCCESS(f"✅ Upload successful: {file_path}"))
            
            # Test exists
            if storage.exists(file_path):
                self.stdout.write(self.style.SUCCESS("✅ File exists in S3"))
            else:
                self.stdout.write(self.style.ERROR("❌ File not found after upload"))
                return False
            
            # Test URL generation
            try:
                url = storage.url(file_path)
                if url and url.startswith('https://'):
                    self.stdout.write(self.style.SUCCESS("✅ URL generated"))
                    if self.detailed:
                        self.stdout.write(f"   URL: {url[:60]}...")
                else:
                    self.stdout.write(self.style.ERROR("❌ Invalid URL generated"))
                    return False
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ URL generation failed: {e}"))
                return False
            
            # Test delete
            storage.delete(file_path)
            if not storage.exists(file_path):
                self.stdout.write(self.style.SUCCESS("✅ File deleted successfully"))
            else:
                self.stdout.write(self.style.ERROR("❌ File deletion failed"))
                
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ File operations failed: {str(e)}"))
            self.stdout.write("💡 Check IAM permissions: s3:GetObject, s3:PutObject, s3:DeleteObject")
            return False

    def _test_presigned_url_basics(self):
        """Test basic presigned URL generation"""
        self.stdout.write(self.style.HTTP_INFO("\n4. Presigned URL Test"))
        self.stdout.write("-" * 30)
        
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            
            # Test presigned URL generation (doesn't require file to exist)
            test_key = "test/presigned_test.mp3"
            
            # Test GET presigned URL
            get_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                    'Key': test_key
                },
                ExpiresIn=3600
            )
            
            if get_url and 'Signature=' in get_url:
                self.stdout.write(self.style.SUCCESS("✅ GET presigned URL generated"))
            else:
                self.stdout.write(self.style.ERROR("❌ GET presigned URL invalid"))
                
            # Test PUT presigned URL
            put_url = s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                    'Key': test_key
                },
                ExpiresIn=3600
            )
            
            if put_url and 'Signature=' in put_url:
                self.stdout.write(self.style.SUCCESS("✅ PUT presigned URL generated"))
            else:
                self.stdout.write(self.style.ERROR("❌ PUT presigned URL invalid"))
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            self.stdout.write(self.style.ERROR(f"❌ Presigned URL generation failed: {error_code}"))
            if error_code == 'AccessDenied':
                self.stdout.write("💡 Check IAM permissions for the bucket and objects")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Presigned URL test failed: {e}"))

    def _print_next_steps(self):
        """Print next steps for comprehensive testing"""
        self.stdout.write(self.style.HTTP_INFO("\n📋 Next Steps"))
        self.stdout.write("-" * 30)
        self.stdout.write("Run comprehensive tests:")
        self.stdout.write("  python manage.py test_s3_complete")
        self.stdout.write("\nTest with actual retreat audio:")
        self.stdout.write("  python manage.py test_presigned_url")
        self.stdout.write("\nCheck CORS configuration:")
        self.stdout.write("  python manage.py check_s3_cors")