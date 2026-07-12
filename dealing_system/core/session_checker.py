import os
import pickle
import json
from pathlib import Path

def find_whatsapp_session():
    """
    Find WhatsApp Web session files from various locations
    """
    session_locations = [
        # PyWhatKit default
        Path.home() / '.pywhatkit',
        Path.home() / '.config' / 'pywhatkit',
        # Windows
        Path(os.environ.get('APPDATA', '')) / 'pywhatkit',
        Path(os.environ.get('LOCALAPPDATA', '')) / 'pywhatkit',
        # Current directory
        Path.cwd() / '.pywhatkit',
    ]
    
    for location in session_locations:
        if location.exists():
            for file in location.iterdir():
                if file.suffix in ['.pkl', '.json', '.dat']:
                    # Check if file has content (not empty)
                    if file.stat().st_size > 100:
                        return True
    return False


def get_whatsapp_status():
    """
    Get detailed WhatsApp Web status
    """
    has_session = find_whatsapp_session()
    
    # Try to verify with a quick test
    try:
        import pywhatkit as kit
        # This will raise exception if not logged in
        # We'll use a very short timeout
        import sys
        import subprocess
        
        result = subprocess.run(
            [sys.executable, "-c", 
             "import pywhatkit; pywhatkit.sendwhatmsg_instantly('1234567890', 'test', wait_time=2)"],
            capture_output=True,
            timeout=5
        )
        
        # If it returns without error, session is valid
        if result.returncode == 0:
            return {'connected': True, 'session_exists': True, 'verified': True}
        else:
            # Check if error message indicates not logged in
            error = result.stderr.decode('utf-8', errors='ignore').lower()
            if 'not logged' in error or 'login' in error:
                return {'connected': False, 'session_exists': has_session, 'verified': False, 'error': 'Not logged in'}
            
    except Exception as e:
        print(f"Verification error: {e}")
    
    return {'connected': has_session, 'session_exists': has_session, 'verified': False}