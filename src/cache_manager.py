"""Cache Manager - Handles DNS response caching with TTL support."""

import time
import threading
import json
from collections import defaultdict


class CacheManager:
    """Manages DNS response caching with TTL-based expiration."""
    
    def __init__(self, max_size=1000, cleanup_interval=60):
        """Initialize cache manager.
        
        Args:
            max_size: Maximum number of cache entries
            cleanup_interval: Cleanup interval in seconds
        """
        self.max_size = max_size
        self.cleanup_interval = cleanup_interval
        
        # Cache storage: {key: {'data': response, 'expires': timestamp}}
        self._cache = {}
        
        # Statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'cleanups': 0
        }
        
        # Thread lock for thread safety
        self._lock = threading.RLock()
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
    
    def get(self, key):
        """Get cached DNS response.
        
        Args:
            key: Cache key (usually domain:type:server)
            
        Returns:
            dict or None: Cached response if found and not expired, None otherwise
        """
        with self._lock:
            if key not in self._cache:
                self._stats['misses'] += 1
                return None
            
            entry = self._cache[key]
            current_time = time.time()
            
            # Check if entry has expired
            if current_time >= entry['expires']:
                del self._cache[key]
                self._stats['misses'] += 1
                return None
            
            # Cache hit
            self._stats['hits'] += 1
            return entry['data'].copy()  # Return copy to prevent modification
    
    def set(self, key, data, ttl):
        """Set cached DNS response.
        
        Args:
            key: Cache key
            data: DNS response data to cache
            ttl: Time to live in seconds
        """
        if ttl <= 0:
            return  # Don't cache entries with zero or negative TTL
        
        with self._lock:
            current_time = time.time()
            expires = current_time + ttl
            
            # Check if we need to evict entries
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_oldest()
            
            # Store the entry
            self._cache[key] = {
                'data': data.copy(),  # Store copy to prevent external modification
                'expires': expires,
                'created': current_time
            }
    
    def is_cached(self, key):
        """Check if key is cached and not expired.
        
        Args:
            key: Cache key to check
            
        Returns:
            bool: True if cached and not expired, False otherwise
        """
        with self._lock:
            if key not in self._cache:
                return False
            
            current_time = time.time()
            entry = self._cache[key]
            
            if current_time >= entry['expires']:
                del self._cache[key]
                return False
            
            return True
    
    def get_ttl(self, key):
        """Get remaining TTL for a cached entry.
        
        Args:
            key: Cache key
            
        Returns:
            int: Remaining TTL in seconds, 0 if not cached or expired
        """
        with self._lock:
            if key not in self._cache:
                return 0
            
            current_time = time.time()
            entry = self._cache[key]
            
            if current_time >= entry['expires']:
                del self._cache[key]
                return 0
            
            return int(entry['expires'] - current_time)
    
    def delete(self, key):
        """Delete a cached entry.
        
        Args:
            key: Cache key to delete
            
        Returns:
            bool: True if entry was deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear_cache(self):
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            # Reset hit/miss stats but keep other stats
            self._stats['hits'] = 0
            self._stats['misses'] = 0
    
    def get_stats(self):
        """Get cache statistics.
        
        Returns:
            dict: Cache statistics including hit ratio, size, etc.
        """
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_ratio = self._stats['hits'] / total_requests if total_requests > 0 else 0
            
            # Calculate memory usage (rough estimate)
            memory_usage = 0
            for entry in self._cache.values():
                memory_usage += len(str(entry['data']))
            memory_usage_kb = memory_usage / 1024
            
            return {
                'total_entries': len(self._cache),
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'hit_ratio': hit_ratio,
                'evictions': self._stats['evictions'],
                'cleanups': self._stats['cleanups'],
                'memory_usage': memory_usage_kb,
                'max_size': self.max_size
            }
    
    def get_cache_contents(self):
        """Get current cache contents (for debugging).
        
        Returns:
            dict: Current cache contents with TTL information
        """
        with self._lock:
            current_time = time.time()
            contents = {}
            
            for key, entry in self._cache.items():
                ttl_remaining = max(0, int(entry['expires'] - current_time))
                contents[key] = {
                    'ttl_remaining': ttl_remaining,
                    'created': entry['created'],
                    'expires': entry['expires'],
                    'data_size': len(str(entry['data']))
                }
            
            return contents
    
    def _evict_oldest(self):
        """Evict the oldest cache entry."""
        if not self._cache:
            return
        
        # Find oldest entry by creation time
        oldest_key = min(self._cache.keys(), 
                        key=lambda k: self._cache[k]['created'])
        
        del self._cache[oldest_key]
        self._stats['evictions'] += 1
    
    def _cleanup_expired(self):
        """Remove expired entries from cache."""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self._cache.items():
            if current_time >= entry['expires']:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            self._stats['cleanups'] += 1
        
        return len(expired_keys)
    
    def _cleanup_loop(self):
        """Background cleanup loop."""
        while True:
            try:
                time.sleep(self.cleanup_interval)
                with self._lock:
                    self._cleanup_expired()
            except Exception:
                # Ignore exceptions in cleanup thread
                pass
    
    def export_cache(self, filename):
        """Export cache contents to a JSON file.
        
        Args:
            filename: Output filename
        """
        with self._lock:
            export_data = {
                'timestamp': time.time(),
                'stats': self.get_stats(),
                'entries': {}
            }
            
            current_time = time.time()
            for key, entry in self._cache.items():
                if current_time < entry['expires']:  # Only export non-expired entries
                    export_data['entries'][key] = {
                        'data': entry['data'],
                        'ttl_remaining': int(entry['expires'] - current_time),
                        'created': entry['created']
                    }
            
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
    
    def import_cache(self, filename):
        """Import cache contents from a JSON file.
        
        Args:
            filename: Input filename
        """
        try:
            with open(filename, 'r') as f:
                import_data = json.load(f)
            
            current_time = time.time()
            
            with self._lock:
                for key, entry in import_data.get('entries', {}).items():
                    ttl_remaining = entry.get('ttl_remaining', 0)
                    if ttl_remaining > 0:
                        self._cache[key] = {
                            'data': entry['data'],
                            'expires': current_time + ttl_remaining,
                            'created': current_time
                        }
        
        except Exception as e:
            raise Exception(f"Failed to import cache: {e}")