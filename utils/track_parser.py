"""
Utilities for parsing track information from filenames
"""
import re
import os
from pathlib import Path


def parse_track_filename(filename):
    """
    Parse track information from filename
    Expected format: "001 JKR How to relate to our mind-(12 April AM_part_1).mp3"
    
    Returns dict with:
    - track_number: int
    - title: str (cleaned)
    - original_filename: str
    """
    # Remove file extension
    name_without_ext = Path(filename).stem
    
    # Pattern to match: number at start, then title, optional date/part info in parentheses
    patterns = [
        # Pattern 1: "001 Title-(date info).mp3"
        r'^(\d+)\s+(.+?)-\([^)]+\)$',
        # Pattern 2: "001 Title (date info).mp3"
        r'^(\d+)\s+(.+?)\s*\([^)]+\)$',
        # Pattern 3: "001 Title.mp3"
        r'^(\d+)\s+(.+)$',
        # Pattern 4: "Title-(date info).mp3"
        r'^(.+?)-\([^)]+\)$',
        # Pattern 5: "Title (date info).mp3"
        r'^(.+?)\s*\([^)]+\)$',
        # Pattern 6: Just the title
        r'^(.+)$'
    ]
    
    track_number = None
    title = name_without_ext
    
    for pattern in patterns:
        match = re.match(pattern, name_without_ext)
        if match:
            groups = match.groups()
            if len(groups) >= 2 and groups[0].isdigit():
                # Has track number
                track_number = int(groups[0])
                title = groups[1].strip()
            elif len(groups) >= 1:
                # No track number, use full title
                title = groups[0].strip()
            break
    
    # Clean up title
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
        'original_filename': filename
    }


def clean_track_title(title):
    """
    Clean up track title by removing common prefixes and unnecessary characters
    """
    # Remove common speaker initials (like "JKR")
    title = re.sub(r'^[A-Z]{2,4}\s+', '', title)
    
    # Remove multiple spaces
    title = re.sub(r'\s+', ' ', title)
    
    # Remove leading/trailing dashes and spaces
    title = title.strip(' -_')
    
    # Capitalize first letter
    if title:
        title = title[0].upper() + title[1:]
    
    return title


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