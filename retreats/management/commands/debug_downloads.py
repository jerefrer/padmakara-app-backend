from django.core.management.base import BaseCommand
from django.utils import timezone
from retreats.models import DownloadRequest
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Debug and manage download requests'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--list-stuck',
            action='store_true',
            help='List downloads stuck in pending status',
        )
        parser.add_argument(
            '--reset-stuck',
            action='store_true',
            help='Reset downloads stuck for more than 5 minutes',
        )
        parser.add_argument(
            '--test-lambda',
            type=int,
            help='Test Lambda trigger for specific request ID',
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show overall download statistics',
        )
    
    def handle(self, *args, **options):
        if options['list_stuck']:
            self.list_stuck_downloads()
        elif options['reset_stuck']:
            self.reset_stuck_downloads()
        elif options['test_lambda']:
            self.test_lambda_trigger(options['test_lambda'])
        elif options['status']:
            self.show_download_status()
        else:
            self.stdout.write(self.style.ERROR('Please specify an action: --list-stuck, --reset-stuck, --test-lambda ID, or --status'))
    
    def list_stuck_downloads(self):
        """List downloads stuck in pending status"""
        stuck_downloads = DownloadRequest.objects.filter(
            status='pending',
            created_at__lt=timezone.now() - timezone.timedelta(minutes=5)
        ).select_related('user', 'retreat')
        
        if not stuck_downloads:
            self.stdout.write(self.style.SUCCESS('No stuck downloads found'))
            return
        
        self.stdout.write(self.style.WARNING(f'Found {stuck_downloads.count()} stuck downloads:'))
        
        for download in stuck_downloads:
            age_minutes = int((timezone.now() - download.created_at).total_seconds() / 60)
            self.stdout.write(
                f'ID {download.id}: {download.retreat.name} by {download.user.username} '
                f'(stuck for {age_minutes} min)'
            )
    
    def reset_stuck_downloads(self):
        """Reset downloads stuck for more than 5 minutes"""
        stuck_downloads = DownloadRequest.objects.filter(
            status='pending',
            created_at__lt=timezone.now() - timezone.timedelta(minutes=5)
        )
        
        count = stuck_downloads.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No stuck downloads to reset'))
            return
        
        # Mark as failed with explanation
        updated = stuck_downloads.update(
            status='failed',
            error_message='Reset due to Lambda trigger timeout - check AWS IAM permissions'
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Reset {updated} stuck downloads')
        )
    
    def test_lambda_trigger(self, request_id):
        """Test Lambda trigger for specific request"""
        from retreats.views import trigger_lambda_zip_generation
        
        try:
            download_request = DownloadRequest.objects.get(id=request_id)
            self.stdout.write(f'Testing Lambda trigger for request {request_id}...')
            
            # Show current status
            self.stdout.write(f'Current status: {download_request.status}')
            self.stdout.write(f'Created: {download_request.created_at}')
            self.stdout.write(f'Processing started: {download_request.processing_started_at}')
            
            # Test Lambda trigger
            success = trigger_lambda_zip_generation(download_request)
            
            if success:
                self.stdout.write(self.style.SUCCESS('Lambda trigger successful'))
            else:
                self.stdout.write(self.style.ERROR('Lambda trigger failed'))
                download_request.refresh_from_db()
                self.stdout.write(f'Error: {download_request.error_message}')
                
        except DownloadRequest.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Download request {request_id} not found'))
    
    def show_download_status(self):
        """Show overall download statistics"""
        from django.db.models import Count
        
        stats = DownloadRequest.objects.values('status').annotate(count=Count('id'))
        
        self.stdout.write(self.style.SUCCESS('Download Request Statistics:'))
        
        for stat in stats:
            self.stdout.write(f"{stat['status']}: {stat['count']}")
        
        # Show recent activity
        recent = DownloadRequest.objects.filter(
            created_at__gte=timezone.now() - timezone.timedelta(hours=24)
        ).order_by('-created_at')[:10]
        
        self.stdout.write(self.style.SUCCESS('\nRecent Downloads (last 24h):'))
        for req in recent:
            age = timezone.now() - req.created_at
            age_str = f"{int(age.total_seconds() / 3600)}h" if age.total_seconds() > 3600 else f"{int(age.total_seconds() / 60)}m"
            self.stdout.write(
                f"ID {req.id}: {req.status} - {req.retreat.name} ({age_str} ago)"
            )