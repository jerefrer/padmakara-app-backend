"""
Management command to check existing S3 CORS configuration
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import boto3
import json


class Command(BaseCommand):
    help = 'Check existing S3 CORS configuration'

    def handle(self, *args, **options):
        self.stdout.write("🔍 Checking S3 CORS Configuration...")
        
        # Check if S3 is enabled
        use_s3 = getattr(settings, 'USE_S3_FOR_MEDIA', False)
        if not use_s3:
            self.stdout.write("❌ S3 is not enabled. Cannot check CORS.")
            return
        
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME
            self.stdout.write(f"📦 Bucket: {bucket_name}")
            
            # Get current CORS configuration
            try:
                response = s3_client.get_bucket_cors(Bucket=bucket_name)
                
                self.stdout.write("✅ Current CORS Configuration Found:")
                self.stdout.write("=" * 50)
                
                for i, rule in enumerate(response['CORSRules'], 1):
                    self.stdout.write(f"\n📋 CORS Rule #{i}:")
                    self.stdout.write(f"   AllowedOrigins: {rule.get('AllowedOrigins', [])}")
                    self.stdout.write(f"   AllowedMethods: {rule.get('AllowedMethods', [])}")
                    self.stdout.write(f"   AllowedHeaders: {rule.get('AllowedHeaders', [])}")
                    self.stdout.write(f"   ExposeHeaders: {rule.get('ExposeHeaders', [])}")
                    self.stdout.write(f"   MaxAgeSeconds: {rule.get('MaxAgeSeconds', 'Not set')}")
                
                self.stdout.write("\n" + "=" * 50)
                self.stdout.write("📄 Raw JSON:")
                self.stdout.write(json.dumps(response['CORSRules'], indent=2))
                
                # Check if localhost is already allowed
                localhost_allowed = False
                for rule in response['CORSRules']:
                    origins = rule.get('AllowedOrigins', [])
                    if any('localhost' in origin or '127.0.0.1' in origin for origin in origins):
                        localhost_allowed = True
                        break
                
                if localhost_allowed:
                    self.stdout.write("\n✅ Localhost access is already configured!")
                else:
                    self.stdout.write("\n⚠️  Localhost access is NOT configured in existing CORS rules")
                    self.stdout.write("💡 You may need to add localhost origins for direct uploads to work")
                
            except s3_client.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchCORSConfiguration':
                    self.stdout.write("ℹ️  No CORS configuration exists on this bucket")
                    self.stdout.write("💡 This means you can safely apply a new CORS configuration")
                else:
                    raise e
                    
        except Exception as e:
            self.stdout.write(f"❌ Failed to check CORS configuration: {str(e)}")
            if "AccessDenied" in str(e):
                self.stdout.write("💡 Check that your AWS credentials have s3:GetBucketCors permission")
            
        self.stdout.write("\n✅ CORS check completed!")