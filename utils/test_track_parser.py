"""
Test script for track parser functionality
"""
from track_parser import parse_track_filename

def test_track_parser():
    """Test the track filename parser with various formats"""
    
    test_cases = [
        "001 JKR How to relate to our mind-(12 April AM_part_1).mp3",
        "002 Introduction to Meditation (Morning Session).mp3", 
        "003 Guided Practice.mp3",
        "004 Q&A Session-(Evening).mp3",
        "Introduction to Mindfulness (Day 1).mp3",
        "Closing Remarks.mp3",
        "010 Advanced Techniques-(Final Day).mp3"
    ]
    
    print("Testing Track Parser:")
    print("=" * 60)
    
    for filename in test_cases:
        result = parse_track_filename(filename)
        print(f"Filename: {filename}")
        print(f"  → Track Number: {result['track_number']}")
        print(f"  → Title: {result['title']}")
        print(f"  → Original: {result['original_filename']}")
        print()

if __name__ == "__main__":
    test_track_parser()