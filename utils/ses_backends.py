"""
Amazon SES Email Backend for Django
Provides production email sending through Amazon Simple Email Service
"""
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import sanitize_address
import logging

logger = logging.getLogger(__name__)


class SESEmailBackend(BaseEmailBackend):
    """
    Amazon SES email backend for production use.
    
    Uses boto3 to send emails through Amazon Simple Email Service.
    Supports HTML emails, attachments, and proper error handling.
    """
    
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.ses_client = None
        self._initialize_ses_client()
    
    def _initialize_ses_client(self):
        """Initialize the SES client with AWS credentials"""
        try:
            # Get AWS SES-specific configuration from settings
            aws_access_key = getattr(settings, 'AWS_SES_ACCESS_KEY_ID', None)
            aws_secret_key = getattr(settings, 'AWS_SES_SECRET_ACCESS_KEY', None) 
            aws_region = getattr(settings, 'AWS_SES_REGION_NAME', 'us-east-1')
            
            if aws_access_key and aws_secret_key:
                # Use explicit credentials
                self.ses_client = boto3.client(
                    'ses',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=aws_region
                )
            else:
                # Use IAM role or environment credentials
                self.ses_client = boto3.client('ses', region_name=aws_region)
                
            logger.info(f"SES client initialized for region: {aws_region}")
            
        except (NoCredentialsError, ClientError) as e:
            logger.error(f"Failed to initialize SES client: {e}")
            if not self.fail_silently:
                raise
    
    def send_messages(self, email_messages):
        """
        Send a list of email messages through Amazon SES.
        Returns the number of messages sent successfully.
        """
        if not email_messages:
            return 0
            
        if not self.ses_client:
            logger.error("SES client not initialized")
            return 0
        
        sent_count = 0
        
        for message in email_messages:
            try:
                if self._send_message(message):
                    sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send email '{message.subject}': {e}")
                if not self.fail_silently:
                    raise
        
        return sent_count
    
    def _send_message(self, message):
        """Send a single email message through SES"""
        try:
            # Prepare destination
            destination = {
                'ToAddresses': [sanitize_address(addr, message.encoding) for addr in message.to],
            }
            
            if message.cc:
                destination['CcAddresses'] = [sanitize_address(addr, message.encoding) for addr in message.cc]
            
            if message.bcc:
                destination['BccAddresses'] = [sanitize_address(addr, message.encoding) for addr in message.bcc]
            
            # Prepare message content
            email_content = {
                'Subject': {
                    'Data': message.subject,
                    'Charset': message.encoding or 'UTF-8'
                },
            }
            
            # Handle both plain text and HTML content
            if hasattr(message, 'alternatives') and message.alternatives:
                # Email has HTML alternative
                html_content = None
                for content, content_type in message.alternatives:
                    if content_type == 'text/html':
                        html_content = content
                        break
                
                if html_content:
                    email_content['Body'] = {
                        'Text': {
                            'Data': message.body,
                            'Charset': message.encoding or 'UTF-8'
                        },
                        'Html': {
                            'Data': html_content,
                            'Charset': message.encoding or 'UTF-8'
                        }
                    }
                else:
                    email_content['Body'] = {
                        'Text': {
                            'Data': message.body,
                            'Charset': message.encoding or 'UTF-8'
                        }
                    }
            else:
                # Plain text only
                email_content['Body'] = {
                    'Text': {
                        'Data': message.body,
                        'Charset': message.encoding or 'UTF-8'
                    }
                }
            
            # Prepare email parameters
            email_params = {
                'Source': sanitize_address(message.from_email, message.encoding),
                'Destination': destination,
                'Message': email_content
            }
            
            # Add configuration set only if specified and not empty
            config_set = getattr(settings, 'AWS_SES_CONFIGURATION_SET', None)
            if config_set and config_set.strip():
                email_params['ConfigurationSetName'] = config_set
            
            # Send the email
            response = self.ses_client.send_email(**email_params)
            
            message_id = response['MessageId']
            logger.info(f"Email sent successfully via SES. Subject: '{message.subject}', MessageId: {message_id}")
            
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            # Handle specific SES errors
            if error_code == 'MessageRejected':
                logger.error(f"SES rejected email '{message.subject}': {error_message}")
            elif error_code == 'MailFromDomainNotVerifiedException':
                logger.error(f"Domain not verified for email '{message.subject}': {error_message}")
            elif error_code == 'ConfigurationSetDoesNotExistException':
                logger.error(f"SES configuration set not found: {error_message}")
            else:
                logger.error(f"SES error for email '{message.subject}': {error_code} - {error_message}")
            
            if not self.fail_silently:
                raise
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error sending email '{message.subject}': {e}")
            if not self.fail_silently:
                raise
            return False


class SESEmailBackendWithAttachments(SESEmailBackend):
    """
    Extended SES backend that supports email attachments using raw email sending.
    Uses send_raw_email for complex emails with attachments.
    """
    
    def _send_message(self, message):
        """Send email with potential attachments using raw email"""
        try:
            # If no attachments, use the regular method for better deliverability
            if not hasattr(message, 'attachments') or not message.attachments:
                return super()._send_message(message)
            
            # For emails with attachments, use send_raw_email
            raw_message = message.message()
            
            # Prepare raw email parameters
            raw_params = {
                'Source': sanitize_address(message.from_email, message.encoding),
                'RawMessage': {'Data': raw_message.as_bytes()},
                'Destinations': [
                    sanitize_address(addr, message.encoding) 
                    for addr in (message.to + message.cc + message.bcc)
                ]
            }
            
            # Add configuration set only if specified and not empty
            config_set = getattr(settings, 'AWS_SES_CONFIGURATION_SET', None)
            if config_set and config_set.strip():
                raw_params['ConfigurationSetName'] = config_set
            
            response = self.ses_client.send_raw_email(**raw_params)
            
            message_id = response['MessageId']
            logger.info(f"Email with attachments sent via SES. Subject: '{message.subject}', MessageId: {message_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email with attachments '{message.subject}': {e}")
            if not self.fail_silently:
                raise
            return False