"""
URL patterns for retreat views
"""
from django.urls import path
from . import views

app_name = 'retreats'

urlpatterns = [
    # Admin views
    path('session/<int:session_id>/bulk-upload/', views.bulk_upload_tracks_view, name='bulk_upload_tracks'),
    path('session/<int:session_id>/generate-presigned-url/', views.generate_s3_presigned_url, name='generate_s3_presigned_url'),
    path('session/<int:session_id>/complete-s3-upload/', views.complete_s3_upload, name='complete_s3_upload'),
    path('session/<int:session_id>/upload-file/', views.upload_track_file, name='upload_track_file'),
    path('session/<int:session_id>/progress/', views.check_upload_progress, name='check_upload_progress'),
    
    # API endpoints
    path('user-retreats/', views.user_retreats, name='user_retreats'),
    path('<int:retreat_id>/', views.retreat_details, name='retreat_details'),
    path('sessions/<int:session_id>/', views.session_details, name='session_details'),
    path('presigned-url/<int:track_id>/', views.track_presigned_url, name='track_presigned_url'),
    
    # Language preference endpoints
    path('user-language-preferences/', views.user_language_preferences, name='user_language_preferences'),
    path('sessions/<int:session_id>/clear-language-preference/', views.clear_session_language_preference, name='clear_session_language_preference'),
    
    # Download ZIP endpoints
    path('<int:retreat_id>/request-download/', views.request_retreat_download, name='request_retreat_download'),
    path('download-requests/<int:request_id>/status/', views.download_request_status, name='download_request_status'),
    path('download-requests/<int:request_id>/download/', views.download_file, name='download_file'),
    path('download-requests/<int:request_id>/extend-lifecycle/', views.extend_zip_lifecycle, name='extend_zip_lifecycle'),
    path('download-webhook/', views.download_webhook, name='download_webhook'),
    path('debug-downloads/', views.debug_download_requests, name='debug_download_requests'),
]