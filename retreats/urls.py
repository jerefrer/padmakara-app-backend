"""
URL patterns for retreat views
"""
from django.urls import path
from . import views

app_name = 'retreats'

urlpatterns = [
    path('session/<int:session_id>/bulk-upload/', views.bulk_upload_tracks_view, name='bulk_upload_tracks'),
    path('session/<int:session_id>/generate-presigned-url/', views.generate_s3_presigned_url, name='generate_s3_presigned_url'),
    path('session/<int:session_id>/complete-s3-upload/', views.complete_s3_upload, name='complete_s3_upload'),
    path('session/<int:session_id>/upload-file/', views.upload_track_file, name='upload_track_file'),
    path('session/<int:session_id>/progress/', views.check_upload_progress, name='check_upload_progress'),
]