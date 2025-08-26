"""
Management command to calculate and populate accurate track durations for existing tracks
Note: New tracks should have duration calculated by the client during upload
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from retreats.models import Track
import boto3
import logging
from mutagen import File as MutagenFile
from io import BytesIO
import tempfile
import os


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Calculate and populate accurate durations for audio tracks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--track-id',
            type=str,
            help='Calculate duration for specific track ID (optional)',
        )
        parser.add_argument(
            '--force-update',
            action='store_true',
            help='Update duration even if already set',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of tracks to process in each batch',
        )

    def handle(self, *args, **options):
        track_id = options.get('track_id')
        force_update = options.get('force_update', False)
        batch_size = options.get('batch_size', 10)
        
        self.stdout.write(self.style.HTTP_INFO("🎵 Calculating Track Durations..."))
        self.stdout.write("=" * 60)
        
        # Get tracks to process
        if track_id:
            try:
                tracks = Track.objects.filter(id=track_id, audio_file__isnull=False)
                if not tracks.exists():
                    self.stdout.write(self.style.ERROR(f"❌ Track {track_id} not found or has no audio file"))
                    return
            except Track.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ Track {track_id} does not exist"))
                return
        else:
            # Get tracks without duration_seconds or with force_update
            if force_update:
                tracks = Track.objects.filter(audio_file__isnull=False)
            else:
                tracks = Track.objects.filter(audio_file__isnull=False, duration_seconds=0)
        
        total_tracks = tracks.count()
        if total_tracks == 0:
            self.stdout.write(self.style.SUCCESS("✅ No tracks need duration calculation"))
            return
            
        self.stdout.write(f"📊 Found {total_tracks} tracks to process")
        
        # Process tracks in batches
        processed = 0
        updated = 0
        errors = 0
        
        for i in range(0, total_tracks, batch_size):
            batch = tracks[i:i + batch_size]
            
            for track in batch:
                try:
                    duration = self._calculate_track_duration(track)
                    if duration:
                        track.duration_seconds = duration
                        track.save(update_fields=['duration_seconds'])
                        updated += 1
                        self.stdout.write(
                            f"✅ Track {track.id}: {track.title} - {self._format_duration(duration)}"
                        )
                    else:
                        errors += 1
                        self.stdout.write(
                            f"❌ Track {track.id}: Could not calculate duration"
                        )
                        
                except Exception as e:
                    errors += 1
                    self.stdout.write(
                        f"❌ Track {track.id}: Error - {str(e)}"
                    )
                    
                processed += 1
                
            # Progress update
            if total_tracks > batch_size:
                progress = (processed / total_tracks) * 100
                self.stdout.write(f"📈 Progress: {processed}/{total_tracks} ({progress:.1f}%)")
        
        # Final summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("🎉 Duration Calculation Complete!"))
        self.stdout.write(f"📊 Processed: {processed}")
        self.stdout.write(f"✅ Updated: {updated}")
        self.stdout.write(f"❌ Errors: {errors}")
        
        if errors > 0:
            self.stdout.write("\n💡 Tracks with errors may have:")
            self.stdout.write("   - Missing or corrupted audio files")
            self.stdout.write("   - Unsupported audio formats")
            self.stdout.write("   - Network connectivity issues")

    def _calculate_track_duration(self, track):
        """Calculate duration of an audio track"""
        if not track.audio_file:
            return None
            
        try:
            # Check if using S3 storage by examining the file URL
            if track.audio_file.url.startswith('https://') and 's3' in track.audio_file.url:
                return self._calculate_s3_duration(track)
            else:
                return self._calculate_local_duration(track)
                
        except Exception as e:
            logger.error(f"Error calculating duration for track {track.id}: {e}")
            return None

    def _calculate_s3_duration(self, track):
        """Calculate duration for S3-stored audio file"""
        try:
            # Create S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            
            # Download file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                try:
                    s3_client.download_fileobj(
                        settings.AWS_STORAGE_BUCKET_NAME,
                        track.audio_file.name,
                        temp_file
                    )
                    temp_file.flush()
                    
                    # Use mutagen to get duration
                    audio_file = MutagenFile(temp_file.name)
                    if audio_file and hasattr(audio_file, 'info') and hasattr(audio_file.info, 'length'):
                        duration = int(audio_file.info.length)
                        return duration
                    
                finally:
                    # Clean up temp file
                    os.unlink(temp_file.name)
                    
        except Exception as e:
            logger.error(f"S3 duration calculation failed for track {track.id}: {e}")
            
        return None

    def _calculate_local_duration(self, track):
        """Calculate duration for locally-stored audio file"""
        try:
            file_path = track.audio_file.path
            audio_file = MutagenFile(file_path)
            
            if audio_file and hasattr(audio_file, 'info') and hasattr(audio_file.info, 'length'):
                duration = int(audio_file.info.length)
                return duration
                
        except Exception as e:
            logger.error(f"Local duration calculation failed for track {track.id}: {e}")
            
        return None

    def _format_duration(self, seconds):
        """Format duration in human-readable format"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"