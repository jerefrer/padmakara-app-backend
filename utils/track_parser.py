"""
Utilities for parsing track information from filenames
"""
import re
import os
from pathlib import Path


def parse_track_filename(filename):
    """
    Parse track information from filename
    Expected formats: 
    - "001 JKR How to relate to our mind-(12 April AM_part_1).mp3"
    - "001 TRAD A pratica diaria em tres partes.mp3"
    
    Returns dict with:
    - track_number: int
    - title: str (cleaned)
    - original_filename: str
    - is_translation: bool
    - language_code: str ('en' for originals/JKR, 'pt' for translations/TRAD)
    - speaker_code: str ('JKR', 'TRAD', etc.)
    """
    # Remove file extension
    name_without_ext = Path(filename).stem
    
    # Initialize default values
    track_number = None
    title = name_without_ext
    is_translation = False
    language_code = 'en'  # Default to English
    speaker_code = None
    
    # Enhanced patterns to capture speaker codes (JKR, TRAD, etc.)
    patterns = [
        # Pattern 1: "001 JKR Title-(date info).mp3"
        r'^(\d+)\s+([A-Z]+)\s+(.+?)-\([^)]+\)$',
        # Pattern 2: "001 JKR Title (date info).mp3"  
        r'^(\d+)\s+([A-Z]+)\s+(.+?)\s*\([^)]+\)$',
        # Pattern 3: "001 JKR Title.mp3"
        r'^(\d+)\s+([A-Z]+)\s+(.+)$',
        # Pattern 4: "001 Title-(date info).mp3" (no speaker code)
        r'^(\d+)\s+(.+?)-\([^)]+\)$',
        # Pattern 5: "001 Title (date info).mp3" (no speaker code)
        r'^(\d+)\s+(.+?)\s*\([^)]+\)$',
        # Pattern 6: "001 Title.mp3" (no speaker code)
        r'^(\d+)\s+(.+)$',
        # Pattern 7: "JKR Title-(date info).mp3" (speaker but no number)
        r'^([A-Z]+)\s+(.+?)-\([^)]+\)$',
        # Pattern 8: "JKR Title.mp3" (speaker but no number)
        r'^([A-Z]+)\s+(.+)$',
        # Pattern 9: "Title-(date info).mp3"
        r'^(.+?)-\([^)]+\)$',
        # Pattern 10: "Title (date info).mp3"
        r'^(.+?)\s*\([^)]+\)$',
        # Pattern 11: Just the title
        r'^(.+)$'
    ]
    
    for i, pattern in enumerate(patterns):
        match = re.match(pattern, name_without_ext)
        if match:
            groups = match.groups()
            
            if i <= 2:  # Patterns 1-3: number + speaker + title
                track_number = int(groups[0])
                speaker_code = groups[1]
                title = groups[2].strip()
            elif i <= 5:  # Patterns 4-6: number + title (no speaker)
                track_number = int(groups[0])
                title = groups[1].strip()
            elif i <= 7:  # Patterns 7-8: speaker + title (no number)
                speaker_code = groups[0]
                title = groups[1].strip()
            else:  # Patterns 9-11: just title
                title = groups[0].strip()
            break
    
    # Determine if this is a translation based on speaker code or filename content
    if speaker_code:
        is_translation = speaker_code.upper() in ['TRAD', 'TRADUCAO', 'PT', 'POR']
        if is_translation:
            language_code = 'pt'
        else:
            language_code = 'en'
    else:
        # Fallback: check filename content for translation indicators
        filename_upper = filename.upper()
        if any(indicator in filename_upper for indicator in ['TRAD', 'TRADUCAO', 'PORTUGUESE', 'PORTUGUES']):
            is_translation = True
            language_code = 'pt'
    
    # Clean up title (but preserve speaker code for context)
    if speaker_code:
        title = clean_track_title(title, preserve_speaker=False)
    else:
        title = clean_track_title(title)
    
    # If no track number found, try to extract from start of title
    if track_number is None:
        number_match = re.match(r'^(\d+)\.?\s*(.+)', title)
        if number_match:
            track_number = int(number_match.group(1))
            title = number_match.group(2).strip()
    
    # Default track number if none found
    if track_number is None:
        track_number = 1
    
    return {
        'track_number': track_number,
        'title': title,
        'original_filename': filename,
        'is_translation': is_translation,
        'language_code': language_code,
        'speaker_code': speaker_code
    }


def clean_track_title(title, preserve_speaker=True):
    """
    Clean up track title by removing common prefixes and unnecessary characters
    
    Args:
        title (str): The title to clean
        preserve_speaker (bool): Whether to preserve speaker codes like JKR, TRAD
    """
    if not preserve_speaker:
        # Remove common speaker initials (like "JKR", "TRAD")
        title = re.sub(r'^[A-Z]{2,4}\s+', '', title)
    
    # Remove multiple spaces
    title = re.sub(r'\s+', ' ', title)
    
    # Remove leading/trailing dashes and spaces
    title = title.strip(' -_')
    
    # Capitalize first letter
    if title:
        title = title[0].upper() + title[1:]
    
    return title


def detect_translation_pairs(filenames):
    """
    Analyze a list of filenames to detect translation pairs
    
    Args:
        filenames (list): List of filenames to analyze
        
    Returns:
        dict: {
            'pairs': [(original_filename, translation_filename), ...],
            'singles': [filename, ...],  # Files without pairs
            'track_groups': {track_number: [filenames...], ...}
        }
    """
    parsed_files = {}
    track_groups = {}
    
    # Parse all files
    for filename in filenames:
        parsed = parse_track_filename(filename)
        parsed_files[filename] = parsed
        track_num = parsed['track_number']
        
        if track_num not in track_groups:
            track_groups[track_num] = []
        track_groups[track_num].append(filename)
    
    pairs = []
    singles = []
    
    # Find pairs within each track number group
    for track_num, group_files in track_groups.items():
        originals = [f for f in group_files if not parsed_files[f]['is_translation']]
        translations = [f for f in group_files if parsed_files[f]['is_translation']]
        
        # Try to pair originals with translations
        paired_originals = set()
        paired_translations = set()
        
        for original in originals:
            for translation in translations:
                if translation not in paired_translations:
                    pairs.append((original, translation))
                    paired_originals.add(original)
                    paired_translations.add(translation)
                    break
        
        # Add unpaired files to singles
        for original in originals:
            if original not in paired_originals:
                singles.append(original)
        
        for translation in translations:
            if translation not in paired_translations:
                singles.append(translation)
    
    return {
        'pairs': pairs,
        'singles': singles,
        'track_groups': track_groups
    }


def validate_audio_file(filename):
    """
    Validate if file is a supported audio format
    """
    allowed_extensions = {'.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg'}
    file_ext = Path(filename).suffix.lower()
    return file_ext in allowed_extensions


def get_file_size_mb(file):
    """
    Get file size in MB
    """
    if hasattr(file, 'size'):
        return round(file.size / (1024 * 1024), 2)
    return 0


def estimate_duration_from_filename(filename):
    """
    Try to extract duration info from filename if available
    Returns duration in minutes or None
    """
    # Look for patterns like "45min" or "1h30m" in filename
    duration_patterns = [
        r'(\d+)min',
        r'(\d+)h(\d+)m',
        r'(\d+)h',
        r'(\d+)_min',
    ]
    
    for pattern in duration_patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 2:  # Hours and minutes
                return int(groups[0]) * 60 + int(groups[1])
            else:  # Just minutes or hours
                value = int(groups[0])
                if 'h' in pattern:
                    return value * 60
                else:
                    return value
    
    return None