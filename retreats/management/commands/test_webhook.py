from django.core.management.base import BaseCommand
from django.test import Client
import json
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Test the webhook endpoint with sample data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--request-id',
            type=int,
            required=True,
            help='Download request ID to test with',
        )
        parser.add_argument(
            '--status',
            default='processing',
            choices=['processing', 'ready', 'failed'],
            help='Status to test (default: processing)',
        )
    
    def handle(self, *args, **options):
        request_id = options['request_id']
        status_type = options['status']
        
        # Create test payload based on status
        if status_type == 'processing':
            payload = {
                'request_id': request_id,
                'status': 'processing',
                'lambda_request_id': 'test-lambda-123',
                'progress_percent': 25,
                'processed_files': 2,
                'total_files': 7,
                'total_size_mb': 150.5
            }
        elif status_type == 'ready':
            payload = {
                'request_id': request_id,
                'status': 'ready',
                'lambda_request_id': 'test-lambda-123',
                'download_url': 'https://test-bucket.s3.amazonaws.com/test.zip',
                's3_key': 'test/test.zip',
                'file_size': 50000000,  # 50MB
                'original_size': 150000000,  # 150MB
                'compression_ratio': 66.7,
                'processing_time_seconds': 45,
                'files_processed': 7,
                'performance': {
                    'compression_time': 30,
                    'upload_time': 15,
                    'total_files': 7
                }
            }
        else:  # failed
            payload = {
                'request_id': request_id,
                'status': 'failed',
                'lambda_request_id': 'test-lambda-123',
                'error_message': 'Test failure - Lambda function timeout'
            }
        
        # Make webhook request
        client = Client()
        
        self.stdout.write(f'Testing webhook with payload: {json.dumps(payload, indent=2)}')
        
        response = client.post(
            '/api/retreats/download-webhook/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.stdout.write(f'Webhook response status: {response.status_code}')
        
        if response.status_code == 200:
            self.stdout.write(self.style.SUCCESS('✓ Webhook test successful'))
            response_data = response.json()
            self.stdout.write(f'Response: {response_data}')
        else:
            self.stdout.write(self.style.ERROR(f'✗ Webhook test failed: {response.status_code}'))
            try:
                error_data = response.json()
                self.stdout.write(f'Error: {error_data}')
            except:
                self.stdout.write(f'Raw response: {response.content.decode()}')