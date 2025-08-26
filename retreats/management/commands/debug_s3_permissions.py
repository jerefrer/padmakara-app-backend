"""
Debug S3 permissions for presigned URLs
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from retreats.models import Track
import boto3
import requests
import xml.etree.ElementTree as ET


class Command(BaseCommand):
    help = 'Debug S3 permissions for presigned URLs'

    def handle(self, *args, **options):
        self.stdout.write("🔍 Debugging S3 Permissions for Presigned URLs...")
        
        # Get a test track
        track = Track.objects.filter(audio_file__isnull=False).first()
        if not track:
            self.stdout.write("❌ No tracks found")
            return
            
        self.stdout.write(f"🎵 Testing with track: {track.title}")
        self.stdout.write(f"📁 S3 Key: {track.audio_file.name}")
        
        # Generate presigned URL
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
        
        self.stdout.write(f"🔗 Generated URL: {presigned_url[:80]}...")
        
        # Test different request types and analyze errors
        self._test_request_types(presigned_url)

    def _test_request_types(self, url):
        """Test different request types and analyze S3 errors"""
        
        tests = [
            ("HEAD request", "HEAD", {}),
            ("GET request", "GET", {}),
            ("Range request", "GET", {"Range": "bytes=0-1023"}),
            ("GET with User-Agent", "GET", {"User-Agent": "React-Native"}),
            ("HEAD with User-Agent", "HEAD", {"User-Agent": "React-Native"}),
        ]
        
        for test_name, method, headers in tests:
            self.stdout.write(f"\n🧪 {test_name}:")
            
            try:
                if method == "HEAD":
                    response = requests.head(url, headers=headers, timeout=10)
                else:
                    response = requests.get(url, headers=headers, timeout=10)
                    
                self.stdout.write(f"   Status: {response.status_code}")
                
                if response.status_code == 403:
                    # Parse S3 error response
                    self._parse_s3_error(response)
                elif response.status_code in [200, 206]:
                    self.stdout.write(f"   ✅ Success!")
                    self.stdout.write(f"   Content-Type: {response.headers.get('Content-Type', 'N/A')}")
                    self.stdout.write(f"   Content-Length: {response.headers.get('Content-Length', 'N/A')}")
                else:
                    self.stdout.write(f"   ⚠️ Unexpected status: {response.status_code}")
                    
            except Exception as e:
                self.stdout.write(f"   ❌ Request failed: {e}")

    def _parse_s3_error(self, response):
        """Parse S3 XML error response"""
        try:
            xml_content = response.text
            root = ET.fromstring(xml_content)
            
            # Extract S3 error details
            error_code = root.find('Code')
            error_message = root.find('Message')
            request_id = root.find('RequestId')
            
            if error_code is not None:
                self.stdout.write(f"   ❌ S3 Error Code: {error_code.text}")
            if error_message is not None:
                self.stdout.write(f"   📝 S3 Error Message: {error_message.text}")
            if request_id is not None:
                self.stdout.write(f"   🆔 S3 Request ID: {request_id.text}")
                
            # Provide specific guidance based on error
            if error_code is not None and error_code.text == 'AccessDenied':
                self.stdout.write(f"   💡 AccessDenied suggests bucket policy issue")
                self.stdout.write(f"   💡 Presigned URLs require anonymous access permissions")
                
        except ET.ParseError:
            self.stdout.write(f"   ❌ Could not parse S3 error response")
            self.stdout.write(f"   Raw response: {response.text[:200]}...")
        except Exception as e:
            self.stdout.write(f"   ❌ Error parsing S3 response: {e}")
            
        # Show current bucket policy recommendation
        self._show_bucket_policy_recommendation()

    def _show_bucket_policy_recommendation(self):
        """Show recommended bucket policy for presigned URLs"""
        self.stdout.write("\n" + "="*60)
        self.stdout.write("📋 RECOMMENDED BUCKET POLICY FOR PRESIGNED URLS:")
        self.stdout.write("="*60)
        
        policy = f"""{{
    "Version": "2012-10-17",
    "Statement": [
        {{
            "Effect": "Allow",
            "Principal": {{
                "AWS": "arn:aws:iam::117845023176:user/padmakara-backend"
            }},
            "Action": [
                "s3:GetObject",
                "s3:PutObject", 
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::{settings.AWS_STORAGE_BUCKET_NAME}/*"
        }},
        {{
            "Effect": "Allow",
            "Principal": {{
                "AWS": "arn:aws:iam::117845023176:user/padmakara-backend"  
            }},
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::{settings.AWS_STORAGE_BUCKET_NAME}"
        }},
        {{
            "Sid": "AllowPresignedURLAccess",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::{settings.AWS_STORAGE_BUCKET_NAME}/*",
            "Condition": {{
                "StringEquals": {{
                    "s3:ExistingObjectTag/PresignedURLAccess": "allowed"
                }}
            }}
        }}
    ]
}}"""
        
        self.stdout.write(policy)
        self.stdout.write("\n" + "="*60)
        self.stdout.write("📝 ALTERNATIVE SIMPLER POLICY (LESS SECURE):")
        self.stdout.write("="*60)
        
        simple_policy = f"""{{
    "Version": "2012-10-17", 
    "Statement": [
        {{
            "Effect": "Allow",
            "Principal": {{
                "AWS": "arn:aws:iam::117845023176:user/padmakara-backend"
            }},
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::{settings.AWS_STORAGE_BUCKET_NAME}",
                "arn:aws:s3:::{settings.AWS_STORAGE_BUCKET_NAME}/*"
            ]
        }},
        {{
            "Sid": "AllowPresignedURLs",
            "Effect": "Allow", 
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::{settings.AWS_STORAGE_BUCKET_NAME}/*"
        }}
    ]
}}"""
        
        self.stdout.write(simple_policy)
        self.stdout.write("\n💡 The simpler policy allows anonymous access to all objects via presigned URLs")
        self.stdout.write("💡 This is standard practice for applications using presigned URLs for content delivery")