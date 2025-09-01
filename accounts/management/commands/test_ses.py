"""
Management command to test Amazon SES email configuration
"""
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


class Command(BaseCommand):
    help = 'Test Amazon SES email configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to-email',
            type=str,
            help='Email address to send test email to',
            required=True
        )
        parser.add_argument(
            '--check-domain',
            type=str,
            help='Check if domain is verified in SES',
        )

    def handle(self, *args, **options):
        self.stdout.write('🔍 Testing Amazon SES Configuration...\n')
        
        # Test 1: Check SES client initialization
        self.test_ses_client()
        
        # Test 2: Check domain verification
        if options['check_domain']:
            self.test_domain_verification(options['check_domain'])
        else:
            # Extract domain from DEFAULT_FROM_EMAIL
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '')
            if '@' in from_email:
                domain = from_email.split('@')[1]
                self.test_domain_verification(domain)
        
        # Test 3: Send test email
        self.test_send_email(options['to_email'])
        
        self.stdout.write(
            self.style.SUCCESS('\n✅ SES testing completed!')
        )

    def test_ses_client(self):
        """Test SES client initialization"""
        self.stdout.write('1. Testing SES Client Initialization...')
        
        try:
            # Get AWS SES-specific configuration
            aws_access_key = getattr(settings, 'AWS_SES_ACCESS_KEY_ID', None)
            aws_secret_key = getattr(settings, 'AWS_SES_SECRET_ACCESS_KEY', None) 
            aws_region = getattr(settings, 'AWS_SES_REGION_NAME', 'us-east-1')
            
            self.stdout.write(f'   Region: {aws_region}')
            self.stdout.write(f'   Access Key: {"✓ Set" if aws_access_key else "✗ Missing"}')
            self.stdout.write(f'   Secret Key: {"✓ Set" if aws_secret_key else "✗ Missing"}')
            
            # Initialize client
            if aws_access_key and aws_secret_key:
                client = boto3.client(
                    'ses',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=aws_region
                )
            else:
                client = boto3.client('ses', region_name=aws_region)
            
            # Test connection by getting sending quota
            quota = client.get_send_quota()
            
            self.stdout.write(
                self.style.SUCCESS(f'   ✅ SES Client connected successfully!')
            )
            self.stdout.write(f'   Daily sending quota: {quota["Max24HourSend"]:.0f}')
            self.stdout.write(f'   Emails sent today: {quota["SentLast24Hours"]:.0f}')
            self.stdout.write(f'   Send rate per second: {quota["MaxSendRate"]:.1f}')
            
            return client
            
        except NoCredentialsError:
            self.stdout.write(
                self.style.ERROR('   ✗ AWS credentials not found or invalid')
            )
            return None
        except ClientError as e:
            self.stdout.write(
                self.style.ERROR(f'   ✗ AWS SES error: {e}')
            )
            return None
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'   ✗ Unexpected error: {e}')
            )
            return None

    def test_domain_verification(self, domain):
        """Test if domain is verified in SES"""
        self.stdout.write(f'\n2. Testing Domain Verification: {domain}...')
        
        try:
            # Use SES-specific credentials if available
            aws_access_key = getattr(settings, 'AWS_SES_ACCESS_KEY_ID', None)
            aws_secret_key = getattr(settings, 'AWS_SES_SECRET_ACCESS_KEY', None)
            aws_region = getattr(settings, 'AWS_SES_REGION_NAME', 'us-east-1')
            
            if aws_access_key and aws_secret_key:
                client = boto3.client(
                    'ses',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=aws_region
                )
            else:
                client = boto3.client('ses', region_name=aws_region)
            
            # Get verified domains
            response = client.list_verified_email_addresses()
            verified_emails = response.get('VerifiedEmailAddresses', [])
            
            # Get verified domains
            domain_response = client.get_identity_verification_attributes(Identities=[domain])
            domain_status = domain_response['VerificationAttributes'].get(domain, {})
            
            if domain_status.get('VerificationStatus') == 'Success':
                self.stdout.write(
                    self.style.SUCCESS(f'   ✅ Domain {domain} is verified')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'   ⚠️  Domain {domain} is not verified')
                )
                self.stdout.write(f'   Status: {domain_status.get("VerificationStatus", "Unknown")}')
                
                # Suggest verification steps
                self.stdout.write('\n   To verify your domain:')
                self.stdout.write('   1. Go to AWS SES Console')
                self.stdout.write('   2. Navigate to "Verified identities"')
                self.stdout.write(f'   3. Add domain: {domain}')
                self.stdout.write('   4. Add the DNS records provided by AWS')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'   ✗ Error checking domain verification: {e}')
            )

    def test_send_email(self, to_email):
        """Test sending an actual email"""
        self.stdout.write(f'\n3. Testing Email Sending to: {to_email}...')
        
        try:
            subject = 'Padmakara SES Test Email'
            message = """
This is a test email sent from Padmakara using Amazon SES.

If you received this email, your SES configuration is working correctly!

System Information:
- Environment: Production
- Backend: Amazon SES
- Region: {}
- From: {}

Best regards,
Padmakara System
            """.format(
                getattr(settings, 'AWS_SES_REGION_NAME', 'us-east-1'),
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@padmakara.pt')
            )
            
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@padmakara.pt')
            
            # Send the email
            result = send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=[to_email],
                fail_silently=False
            )
            
            if result == 1:
                self.stdout.write(
                    self.style.SUCCESS('   ✅ Test email sent successfully!')
                )
                self.stdout.write(f'   Check {to_email} for the test message')
            else:
                self.stdout.write(
                    self.style.ERROR('   ✗ Email sending failed')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'   ✗ Error sending test email: {e}')
            )
            self.stdout.write('\n   Common issues:')
            self.stdout.write('   - Domain not verified in SES')
            self.stdout.write('   - Email address not verified (sandbox mode)')
            self.stdout.write('   - Incorrect AWS credentials')
            self.stdout.write('   - SES service not available in region')