from django.core.management.base import BaseCommand
from django.conf import settings
import boto3
import json
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Check AWS Lambda function status and recent invocations'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--function-name',
            default='padmakara-zip-generator',
            help='Lambda function name (default: padmakara-zip-generator)',
        )
        parser.add_argument(
            '--logs',
            action='store_true',
            help='Show recent Lambda logs',
        )
        parser.add_argument(
            '--test-invoke',
            action='store_true',
            help='Test invoke Lambda with sample payload',
        )
    
    def handle(self, *args, **options):
        function_name = options.get('function_name') or getattr(settings, 'AWS_LAMBDA_FUNCTION_NAME', 'padmakara-zip-generator')
        
        try:
            # Create Lambda client
            lambda_client = boto3.client(
                'lambda',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            
            # Get function info
            self.stdout.write(f'Checking Lambda function: {function_name}')
            
            try:
                response = lambda_client.get_function(FunctionName=function_name)
                config = response['Configuration']
                
                self.stdout.write(self.style.SUCCESS('✓ Function exists'))
                self.stdout.write(f"  Runtime: {config.get('Runtime', 'Unknown')}")
                self.stdout.write(f"  State: {config.get('State', 'Unknown')}")
                self.stdout.write(f"  Last Modified: {config.get('LastModified', 'Unknown')}")
                self.stdout.write(f"  Timeout: {config.get('Timeout', 'Unknown')}s")
                self.stdout.write(f"  Memory: {config.get('MemorySize', 'Unknown')}MB")
                
                if config.get('State') != 'Active':
                    self.stdout.write(self.style.WARNING(f"⚠ Function state is {config.get('State')}, expected 'Active'"))
                    
            except lambda_client.exceptions.ResourceNotFoundException:
                self.stdout.write(self.style.ERROR(f'✗ Function {function_name} not found'))
                return
            
            # Show recent invocations if requested
            if options['logs']:
                self.show_recent_logs(function_name)
            
            # Test invoke if requested
            if options['test_invoke']:
                self.test_invoke_lambda(lambda_client, function_name)
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error checking Lambda: {str(e)}'))            # Create Lambda client\n            lambda_client = boto3.client(\n                'lambda',\n                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,\n                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,\n                region_name=settings.AWS_S3_REGION_NAME\n            )\n            \n            # Get function info\n            self.stdout.write(f'Checking Lambda function: {function_name}')\n            \n            try:\n                response = lambda_client.get_function(FunctionName=function_name)\n                config = response['Configuration']\n                \n                self.stdout.write(self.style.SUCCESS('✓ Function exists'))\n                self.stdout.write(f\"  Runtime: {config.get('Runtime', 'Unknown')}\")\n                self.stdout.write(f\"  State: {config.get('State', 'Unknown')}\")\n                self.stdout.write(f\"  Last Modified: {config.get('LastModified', 'Unknown')}\")\n                self.stdout.write(f\"  Timeout: {config.get('Timeout', 'Unknown')}s\")\n                self.stdout.write(f\"  Memory: {config.get('MemorySize', 'Unknown')}MB\")\n                \n                if config.get('State') != 'Active':\n                    self.stdout.write(self.style.WARNING(f\"⚠ Function state is {config.get('State')}, expected 'Active'\"))\n                    \n            except lambda_client.exceptions.ResourceNotFoundException:\n                self.stdout.write(self.style.ERROR(f'✗ Function {function_name} not found'))\n                return\n            \n            # Show recent invocations if requested\n            if options['logs']:\n                self.show_recent_logs(function_name)\n            \n            # Test invoke if requested\n            if options['test_invoke']:\n                self.test_invoke_lambda(lambda_client, function_name)\n                \n        except Exception as e:\n            self.stdout.write(self.style.ERROR(f'Error checking Lambda: {str(e)}'))\n    \n    def show_recent_logs(self, function_name):\n        \"\"\"Show recent CloudWatch logs for the Lambda function\"\"\"\n        try:\n            logs_client = boto3.client(\n                'logs',\n                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,\n                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,\n                region_name=settings.AWS_S3_REGION_NAME\n            )\n            \n            log_group = f'/aws/lambda/{function_name}'\n            self.stdout.write(f'\\nRecent logs from {log_group}:')\n            \n            # Get recent log events (last 1 hour)\n            import time\n            end_time = int(time.time() * 1000)\n            start_time = end_time - (60 * 60 * 1000)  # 1 hour ago\n            \n            response = logs_client.filter_log_events(\n                logGroupName=log_group,\n                startTime=start_time,\n                endTime=end_time,\n                limit=50\n            )\n            \n            events = response.get('events', [])\n            if not events:\n                self.stdout.write('  No recent log events found')\n            else:\n                for event in events[-10:]:  # Show last 10 events\n                    timestamp = datetime.fromtimestamp(event['timestamp'] / 1000, tz=timezone.utc)\n                    message = event['message'].strip()\n                    self.stdout.write(f\"  {timestamp}: {message}\")\n                    \n        except Exception as e:\n            self.stdout.write(self.style.WARNING(f'Could not fetch logs: {str(e)}'))\n    \n    def test_invoke_lambda(self, lambda_client, function_name):\n        \"\"\"Test invoke the Lambda function with sample payload\"\"\"\n        self.stdout.write(f'\\nTesting Lambda invocation...')\n        \n        test_payload = {\n            'request_id': 999,  # Test request ID\n            'retreat_name': 'Test Retreat',\n            'audio_files': ['test1.mp3', 'test2.mp3'],\n            'webhook_url': f\"{getattr(settings, 'SITE_URL', 'http://localhost:8000')}/api/retreats/download-webhook/\"\n        }\n        \n        try:\n            response = lambda_client.invoke(\n                FunctionName=function_name,\n                InvocationType='Event',  # Async\n                Payload=json.dumps(test_payload)\n            )\n            \n            if response['StatusCode'] == 202:\n                self.stdout.write(self.style.SUCCESS('✓ Lambda invocation successful'))\n                self.stdout.write(f\"  Response: {response}\")\n            else:\n                self.stdout.write(self.style.ERROR(f'✗ Lambda invocation failed: {response}'))\n                \n        except Exception as e:\n            self.stdout.write(self.style.ERROR(f'✗ Lambda invocation error: {str(e)}'))