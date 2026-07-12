import time
import json
import threading
from datetime import datetime
from django.core.cache import cache

class ImportProgressTracker:
    """Track import progress in real-time"""
    
    def __init__(self, session_id):
        self.session_id = session_id
        self.cache_key = f'import_progress_{session_id}'
        self.data = {
            'total': 0,
            'processed': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'duplicate': 0,
            'current': '',
            'status': 'idle',  # idle, processing, completed, error
            'message': '',
            'start_time': None,
            'end_time': None,
            'logs': [],
            'progress': 0,
            'estimated_time': 0,
            'speed': 0,  # leads per second
            'phone_numbers': []
        }
        self.save()
    
    def save(self):
        """Save progress to cache - Thread safe"""
        try:
            cache.set(self.cache_key, json.dumps(self.data), 3600)  # 1 hour
        except Exception as e:
            print(f"Cache save error: {e}")
    
    def get_data(self):
        """Get progress data"""
        try:
            cached = cache.get(self.cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            print(f"Cache get error: {e}")
        return self.data
    
    def start(self, total):
        """Start processing"""
        self.data['total'] = total
        self.data['status'] = 'processing'
        self.data['start_time'] = datetime.now().isoformat()
        self.data['message'] = f'Starting import of {total} leads...'
        self.save()
    
    def update(self, processed, success, failed, skipped, duplicate, current_lead='', phone=''):
        """Update progress - Thread safe"""
        self.data['processed'] = processed
        self.data['success'] = success
        self.data['failed'] = failed
        self.data['skipped'] = skipped
        self.data['duplicate'] = duplicate
        self.data['current'] = current_lead
        
        if phone:
            if len(self.data['phone_numbers']) < 1000:  # Limit to 1000 numbers
                self.data['phone_numbers'].append(phone)
        
        # Calculate progress percentage
        if self.data['total'] > 0:
            self.data['progress'] = int((processed / self.data['total']) * 100)
        
        # Calculate speed and estimated time
        if self.data['start_time']:
            try:
                elapsed = (datetime.now() - datetime.fromisoformat(self.data['start_time'])).total_seconds()
                if elapsed > 0 and processed > 0:
                    self.data['speed'] = processed / elapsed
                    remaining = self.data['total'] - processed
                    if self.data['speed'] > 0:
                        self.data['estimated_time'] = int(remaining / self.data['speed'])
            except:
                pass
        
        # Add log (limit to 200 logs)
        self.data['logs'].append({
            'time': datetime.now().strftime('%H:%M:%S'),
            'lead': current_lead[:50],
            'phone': phone,
            'status': 'success' if success > 0 else 'failed' if failed > 0 else 'skipped',
        })
        
        if len(self.data['logs']) > 200:
            self.data['logs'] = self.data['logs'][-200:]
        
        self.save()
    
    def complete(self, success, failed, skipped, duplicate):
        """Mark as complete"""
        self.data['status'] = 'completed'
        self.data['end_time'] = datetime.now().isoformat()
        self.data['progress'] = 100
        self.data['message'] = f'✅ Import completed! {success} successful, {failed} failed, {skipped} skipped, {duplicate} duplicates'
        self.save()
    
    def error(self, message):
        """Mark as error"""
        self.data['status'] = 'error'
        self.data['message'] = f'❌ Error: {message}'
        self.save()
    
    @classmethod
    def get_progress(cls, session_id):
        """Get progress for a session"""
        cache_key = f'import_progress_{session_id}'
        try:
            cached = cache.get(cache_key)
            if cached:
                return json.loads(cached)
        except:
            pass
        return None
    
    @classmethod
    def clear(cls, session_id):
        """Clear progress data"""
        cache_key = f'import_progress_{session_id}'
        try:
            cache.delete(cache_key)
        except:
            pass