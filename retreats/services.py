from typing import Optional, Dict, List
from django.db import transaction
from django.contrib.auth import get_user_model
from .models import (
    Retreat, 
    Track, 
    UserLanguagePreference
)

User = get_user_model()


class UserLanguageService:
    """Service for managing user language preferences - app language only (content language is client-side)"""
    
    DEFAULT_APP_LANGUAGE = 'en'
    
    @classmethod
    def set_user_app_language(cls, user: User, language: str) -> None:
        """Set app language preference for a user (UI language from registration)"""
        user_pref, created = UserLanguagePreference.objects.get_or_create(
            user=user,
            defaults={'app_language': language}
        )
        if not created:
            user_pref.app_language = language
            user_pref.save()
    
    @classmethod
    def get_user_app_language(cls, user: User) -> str:
        """Get user's app language preference (UI language)"""
        try:
            user_pref = UserLanguagePreference.objects.get(user=user)
            return user_pref.app_language
        except UserLanguagePreference.DoesNotExist:
            return cls.DEFAULT_APP_LANGUAGE
    
    @classmethod
    def get_available_languages_for_retreat(cls, retreat: Retreat) -> List[Dict[str, str]]:
        """
        Get all available languages for a retreat based on existing tracks.
        Returns list of language codes with display names.
        """
        # Get distinct languages from tracks in this retreat
        languages = set()
        for session in retreat.sessions.all():
            session_languages = Track.objects.filter(session=session).values_list('language', flat=True).distinct()
            languages.update(session_languages)
        
        # Map language codes to display names
        language_map = {
            'en': 'English',
            'pt': 'Português',
            'es': 'Español', 
            'fr': 'Français',
            'de': 'Deutsch',
            'it': 'Italiano'
        }
        
        return [
            {'code': lang, 'name': language_map.get(lang, lang.upper())}
            for lang in sorted(languages) if lang
        ]
    
    @classmethod
    def get_tracks_for_session_and_language(cls, session, language_mode: str) -> List[Track]:
        """
        Get tracks for a session filtered by language preference.
        Returns original tracks + translation tracks for the specified language mode.
        """
        tracks = Track.objects.filter(session=session).order_by('track_number', 'is_original')
        
        if language_mode == 'en':
            # English only - return just original tracks
            return list(tracks.filter(is_original=True))
        elif language_mode == 'en-pt':
            # English + Portuguese - return original + translation tracks
            filtered_tracks = []
            track_numbers_seen = set()
            
            for track in tracks:
                # Include original English tracks
                if track.is_original and track.language == 'en':
                    filtered_tracks.append(track)
                    track_numbers_seen.add(track.track_number)
                # Include Portuguese translation tracks
                elif not track.is_original and track.language == 'pt':
                    # Only include if we have the original track too
                    if track.track_number in track_numbers_seen:
                        filtered_tracks.append(track)
                    else:
                        # Add original track first if it exists
                        try:
                            original_track = tracks.get(
                                track_number=track.track_number, 
                                is_original=True
                            )
                            filtered_tracks.append(original_track)
                            track_numbers_seen.add(track.track_number)
                            filtered_tracks.append(track)
                        except Track.DoesNotExist:
                            # Translation track without original, skip
                            continue
            
            return filtered_tracks
        elif language_mode == 'pt':
            # Portuguese only - return just Portuguese translation tracks
            return list(tracks.filter(is_original=False, language='pt'))
        else:
            # Fallback to English only for unknown language modes
            return list(tracks.filter(is_original=True))
    
    @classmethod
    def get_user_language_preferences_summary(cls, user: User) -> Dict:
        """Get user's app language preference only (content language is client-side)"""
        try:
            user_pref = UserLanguagePreference.objects.get(user=user)
            return {
                'app_language': user_pref.app_language,
                'default_app_language': cls.DEFAULT_APP_LANGUAGE,
                'note': 'Content language preferences handled client-side per device'
            }
        except UserLanguagePreference.DoesNotExist:
            return {
                'app_language': cls.DEFAULT_APP_LANGUAGE,
                'default_app_language': cls.DEFAULT_APP_LANGUAGE,
                'note': 'Using defaults - user preferences not set'
            }