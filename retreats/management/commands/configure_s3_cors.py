"""
Management command to configure S3 CORS policy for direct uploads
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import boto3
import json


class Command(BaseCommand):
    help = 'Configure S3 CORS policy for direct browser uploads'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Apply the CORS configuration to S3 bucket',
        )
        parser.add_argument(
            '--domain',
            type=str,
            default='localhost:8000',
            help='Domain to allow for CORS (default: localhost:8000)',
        )

    def handle(self, *args, **options):
        self.stdout.write("🔧 Configuring S3 CORS for Direct Uploads...")
        
        # Check if S3 is enabled
        use_s3 = getattr(settings, 'USE_S3_FOR_MEDIA', False)
        if not use_s3:
            self.stdout.write("❌ S3 is not enabled. Cannot configure CORS.")
            return
        
        domain = options['domain']
        apply_config = options['apply']
        
        # Generate CORS configuration
        cors_config = {
            'CORSRules': [
                {
                    'AllowedOrigins': [
                        f'http://{domain}',
                        f'https://{domain}',
                        'http://localhost:8000',
                        'http://127.0.0.1:8000',
                    ],
                    'AllowedMethods': ['GET', 'PUT', 'POST', 'DELETE', 'HEAD'],
                    'AllowedHeaders': ['*'],
                    'ExposeHeaders': ['ETag', 'x-amz-version-id'],
                    'MaxAgeSeconds': 3000
                }
            ]
        }
        
        self.stdout.write("📋 Generated CORS Configuration:")
        self.stdout.write(json.dumps(cors_config, indent=2))
        
        if not apply_config:
            self.stdout.write("\n💡 To apply this configuration, run:")
            self.stdout.write(f"   python manage.py configure_s3_cors --apply --domain {domain}")
            self.stdout.write("\n⚠️  This will overwrite any existing CORS configuration on your S3 bucket!")
            return
        
        try:
            # Apply CORS configuration
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME
            
            self.stdout.write(f"\n🔄 Applying CORS configuration to bucket: {bucket_name}")
            
            # Set CORS configuration
            s3_client.put_bucket_cors(
                Bucket=bucket_name,
                CORSConfiguration=cors_config
            )
            
            self.stdout.write("✅ CORS configuration applied successfully!")
            
            # Verify the configuration
            self.stdout.write("\n🔍 Verifying CORS configuration...")
            response = s3_client.get_bucket_cors(Bucket=bucket_name)
            
            self.stdout.write("✅ Current CORS configuration:")
            self.stdout.write(json.dumps(response['CORSRules'], indent=2))
            
        except Exception as e:
            self.stdout.write(f"❌ Failed to configure CORS: {str(e)}")
            if "NoSuchCORSConfiguration" in str(e):
                self.stdout.write("💡 This bucket has no existing CORS configuration.")
            elif "AccessDenied" in str(e):
                self.stdout.write("💡 Check that your AWS credentials have s3:PutBucketCORS permission.")
            
        self.stdout.write("\n✅ CORS configuration process completed!")
        self.stdout.write("\n📝 Next steps:")
        self.stdout.write("1. Test the upload functionality with enhanced error logging")
        self.stdout.write("2. Check browser console for detailed error messages")
        self.stdout.write("3. If issues persist, check AWS CloudTrail logs for S3 API errors")