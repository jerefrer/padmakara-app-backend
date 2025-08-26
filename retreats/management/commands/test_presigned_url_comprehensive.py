"""
Comprehensive test for presigned URL generation and access from different contexts
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from retreats.models import Track
import boto3
import requests
import json


class Command(BaseCommand):
    help = 'Comprehensive test of presigned URL generation and access'

    def add_arguments(self, parser):
        parser.add_argument(
            '--track-id',
            type=str,
            help='Specific track ID to test (optional)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO("🧪 Comprehensive Presigned URL Testing..."))
        self.stdout.write("=" * 60)
        
        track_id = options.get('track_id')
        
        if track_id:
            try:
                track = Track.objects.get(id=track_id)
                self.test_track(track)
            except Track.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ Track {track_id} not found"))
                return
        else:
            # Test first few tracks
            tracks = Track.objects.filter(audio_file__isnull=False)[:3]
            if not tracks:
                self.stdout.write(self.style.ERROR("❌ No tracks with audio files found"))
                return
                
            for track in tracks:
                self.test_track(track)
                self.stdout.write("-" * 40)

    def test_track(self, track):
        """Test presigned URL generation and access for a specific track"""
        self.stdout.write(self.style.HTTP_INFO(f"\n🎵 Testing Track: {track.title} (ID: {track.id})"))
        self.stdout.write(f"📁 Audio file path: {track.audio_file.name}")
        
        # Step 1: Test S3 configuration
        if not self._test_s3_config():
            return
            
        # Step 2: Test presigned URL generation
        presigned_url = self._generate_presigned_url(track)
        if not presigned_url:
            return
            
        # Step 3: Test different access methods
        self._test_access_methods(presigned_url)
        
        # Step 4: Test CORS compliance
        self._test_cors_headers(presigned_url)

    def _test_s3_config(self):
        """Test S3 configuration"""
        self.stdout.write("\n1️⃣ Testing S3 Configuration...")
        
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            
            # Test bucket access
            s3_client.head_bucket(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
            self.stdout.write("✅ S3 bucket accessible")
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ S3 configuration failed: {e}"))
            return False

    def _generate_presigned_url(self, track):
        """Generate presigned URL"""
        self.stdout.write("\n2️⃣ Generating Presigned URL...")
        
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                    'Key': track.audio_file.name
                },
                ExpiresIn=3600
            )
            
            self.stdout.write("✅ Presigned URL generated successfully")
            self.stdout.write(f"🔗 URL: {presigned_url[:80]}...")
            self.stdout.write(f"🔒 Contains signature: {'Signature=' in presigned_url}")
            self.stdout.write(f"⏰ Contains expiration: {'Expires=' in presigned_url}")
            
            return presigned_url
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Presigned URL generation failed: {e}"))
            return None

    def _test_access_methods(self, presigned_url):
        """Test different ways of accessing the presigned URL"""
        self.stdout.write("\n3️⃣ Testing Access Methods...")
        
        # Test 1: Simple HEAD request (backend context)
        self._test_head_request(presigned_url)
        
        # Test 2: Simple GET request with range (audio streaming simulation)
        self._test_range_request(presigned_url)
        
        # Test 3: Requests with different User-Agent (React Native simulation)
        self._test_react_native_request(presigned_url)

    def _test_head_request(self, url):
        """Test basic HEAD request"""
        self.stdout.write("\n   📡 HEAD Request Test:")
        try:
            response = requests.head(url, timeout=10)
            self.stdout.write(f"      Status: {response.status_code}")
            self.stdout.write(f"      Content-Length: {response.headers.get('Content-Length', 'Not set')}")
            self.stdout.write(f"      Content-Type: {response.headers.get('Content-Type', 'Not set')}")
            
            if response.status_code == 200:
                self.stdout.write("      ✅ HEAD request successful")
            else:
                self.stdout.write(self.style.WARNING(f"      ⚠️ HEAD request failed: {response.status_code}"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"      ❌ HEAD request error: {e}"))

    def _test_range_request(self, url):
        """Test range request (important for audio streaming)"""
        self.stdout.write("\n   📡 Range Request Test:")
        try:
            headers = {'Range': 'bytes=0-1023'}  # First 1KB
            response = requests.get(url, headers=headers, timeout=10)
            self.stdout.write(f"      Status: {response.status_code}")
            self.stdout.write(f"      Content-Range: {response.headers.get('Content-Range', 'Not set')}")
            self.stdout.write(f"      Accept-Ranges: {response.headers.get('Accept-Ranges', 'Not set')}")
            
            if response.status_code == 206:  # Partial Content
                self.stdout.write("      ✅ Range request successful")
            elif response.status_code == 200:
                self.stdout.write("      ⚠️ Range request returned full content (may not support ranges)")
            else:
                self.stdout.write(self.style.WARNING(f"      ⚠️ Range request failed: {response.status_code}"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"      ❌ Range request error: {e}"))

    def _test_react_native_request(self, url):
        """Test request with React Native-like headers"""
        self.stdout.write("\n   📱 React Native Simulation Test:")
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
                'Accept': 'audio/*,*/*',
                'Origin': 'http://localhost:8000'
            }
            response = requests.head(url, headers=headers, timeout=10)
            self.stdout.write(f"      Status: {response.status_code}")
            self.stdout.write(f"      CORS headers present: {'Access-Control-Allow-Origin' in response.headers}")
            
            if response.status_code == 200:
                self.stdout.write("      ✅ React Native simulation successful")
            else:
                self.stdout.write(self.style.WARNING(f"      ⚠️ React Native simulation failed: {response.status_code}"))
                if response.status_code == 403:
                    self.stdout.write("      💡 This suggests CORS configuration issues")
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"      ❌ React Native simulation error: {e}"))

    def _test_cors_headers(self, url):
        """Test CORS configuration"""
        self.stdout.write("\n4️⃣ Testing CORS Configuration...")
        
        try:
            # Test preflight request (OPTIONS)
            headers = {
                'Origin': 'http://localhost:8000',
                'Access-Control-Request-Method': 'GET',
                'Access-Control-Request-Headers': 'Range'
            }
            
            response = requests.options(url, headers=headers, timeout=10)
            self.stdout.write(f"   Preflight Status: {response.status_code}")
            
            cors_headers = {
                'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
                'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
                'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers'),
                'Access-Control-Max-Age': response.headers.get('Access-Control-Max-Age'),
            }
            
            self.stdout.write("   CORS Headers:")
            for header, value in cors_headers.items():
                status = "✅" if value else "❌"
                self.stdout.write(f"      {status} {header}: {value or 'Not set'}")
            
            # Check if CORS is properly configured
            if cors_headers['Access-Control-Allow-Origin']:
                self.stdout.write("   ✅ CORS appears to be configured")
            else:
                self.stdout.write("   ❌ CORS not configured - this is likely the problem!")
                self.stdout.write("   💡 React Native requests will be blocked without proper CORS")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ CORS test error: {e}"))
            
        # Final diagnosis
        self._print_diagnosis()

    def _print_diagnosis(self):
        """Print final diagnosis and recommendations"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.HTTP_INFO("🔬 DIAGNOSIS & RECOMMENDATIONS:"))
        self.stdout.write("=" * 60)
        
        self.stdout.write("\n🔍 Issue Analysis:")
        self.stdout.write("   • Presigned URLs generate successfully from backend")
        self.stdout.write("   • Backend can access S3 files directly") 
        self.stdout.write("   • Frontend requests likely blocked by CORS policy")
        
        self.stdout.write("\n💡 Solutions:")
        self.stdout.write("   1. Request AWS IAM permission: s3:PutBucketCORS")
        self.stdout.write("   2. Apply CORS configuration with: python manage.py configure_s3_cors --apply")
        self.stdout.write("   3. Verify CORS with: python manage.py check_s3_cors")
        
        self.stdout.write("\n📱 React Native Requirements:")
        self.stdout.write("   • AllowedOrigins: ['*'] (for mobile apps)")
        self.stdout.write("   • AllowedMethods: ['GET', 'HEAD']")
        self.stdout.write("   • AllowedHeaders: ['Range', 'Authorization', 'Content-Type']")
        self.stdout.write("   • ExposeHeaders: ['Content-Range', 'Content-Length', 'Accept-Ranges']")