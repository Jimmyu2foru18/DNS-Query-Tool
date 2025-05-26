"""Tests for Cache Manager functionality."""

import pytest
import time
import threading
import tempfile
import os
import json
import sys

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cache_manager import CacheManager


class TestCacheManager:
    """Test cases for CacheManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cache = CacheManager(max_size=10, cleanup_interval=1)
        
        # Sample DNS response for testing
        self.sample_response = {
            'query_name': 'example.com',
            'query_type': 'A',
            'status': 'NOERROR',
            'answers': [{
                'name': 'example.com',
                'type': 'A',
                'data': '192.168.1.1',
                'ttl': 300
            }]
        }
    
    def teardown_method(self):
        """Clean up after tests."""
        self.cache.clear_cache()
    
    def test_init(self):
        """Test cache manager initialization."""
        cache = CacheManager(max_size=100, cleanup_interval=30)
        assert cache.max_size == 100
        assert cache.cleanup_interval == 30
        assert len(cache._cache) == 0
        assert cache._stats['hits'] == 0
        assert cache._stats['misses'] == 0
    
    def test_set_and_get_basic(self):
        """Test basic set and get operations."""
        key = "example.com:A:8.8.8.8"
        ttl = 300
        
        # Set cache entry
        self.cache.set(key, self.sample_response, ttl)
        
        # Get cache entry
        result = self.cache.get(key)
        
        assert result is not None
        assert result['query_name'] == 'example.com'
        assert result['status'] == 'NOERROR'
        
        # Verify it's a copy (not the same object)
        assert result is not self.sample_response
    
    def test_get_nonexistent_key(self):
        """Test getting non-existent cache key."""
        result = self.cache.get("nonexistent:A:8.8.8.8")
        assert result is None
    
    def test_cache_expiration(self):
        """Test cache entry expiration."""
        key = "example.com:A:8.8.8.8"
        ttl = 1  # 1 second TTL
        
        # Set cache entry
        self.cache.set(key, self.sample_response, ttl)
        
        # Should be available immediately
        result = self.cache.get(key)
        assert result is not None
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be expired now
        result = self.cache.get(key)
        assert result is None
    
    def test_zero_ttl(self):
        """Test that zero TTL entries are not cached."""
        key = "example.com:A:8.8.8.8"
        
        # Set with zero TTL
        self.cache.set(key, self.sample_response, 0)
        
        # Should not be cached
        result = self.cache.get(key)
        assert result is None
    
    def test_negative_ttl(self):
        """Test that negative TTL entries are not cached."""
        key = "example.com:A:8.8.8.8"
        
        # Set with negative TTL
        self.cache.set(key, self.sample_response, -10)
        
        # Should not be cached
        result = self.cache.get(key)
        assert result is None
    
    def test_is_cached(self):
        """Test is_cached method."""
        key = "example.com:A:8.8.8.8"
        
        # Initially not cached
        assert not self.cache.is_cached(key)
        
        # Set cache entry
        self.cache.set(key, self.sample_response, 300)
        
        # Should be cached now
        assert self.cache.is_cached(key)
        
        # Test with expired entry
        expired_key = "expired.com:A:8.8.8.8"
        self.cache.set(expired_key, self.sample_response, 1)
        time.sleep(1.1)
        
        # Should not be cached (expired)
        assert not self.cache.is_cached(expired_key)
    
    def test_get_ttl(self):
        """Test getting remaining TTL."""
        key = "example.com:A:8.8.8.8"
        ttl = 10
        
        # Set cache entry
        self.cache.set(key, self.sample_response, ttl)
        
        # Get TTL immediately
        remaining_ttl = self.cache.get_ttl(key)
        assert remaining_ttl <= ttl
        assert remaining_ttl > 0
        
        # Wait a bit and check again
        time.sleep(1)
        remaining_ttl2 = self.cache.get_ttl(key)
        assert remaining_ttl2 < remaining_ttl
        
        # Test non-existent key
        assert self.cache.get_ttl("nonexistent:A:8.8.8.8") == 0
    
    def test_delete(self):
        """Test deleting cache entries."""
        key = "example.com:A:8.8.8.8"
        
        # Set cache entry
        self.cache.set(key, self.sample_response, 300)
        assert self.cache.is_cached(key)
        
        # Delete entry
        result = self.cache.delete(key)
        assert result is True
        assert not self.cache.is_cached(key)
        
        # Try to delete non-existent entry
        result = self.cache.delete("nonexistent:A:8.8.8.8")
        assert result is False
    
    def test_clear_cache(self):
        """Test clearing all cache entries."""
        # Add multiple entries
        for i in range(5):
            key = f"example{i}.com:A:8.8.8.8"
            self.cache.set(key, self.sample_response, 300)
        
        # Verify entries exist
        stats = self.cache.get_stats()
        assert stats['total_entries'] == 5
        
        # Clear cache
        self.cache.clear_cache()
        
        # Verify cache is empty
        stats = self.cache.get_stats()
        assert stats['total_entries'] == 0
        assert stats['hits'] == 0
        assert stats['misses'] == 0
    
    def test_cache_statistics(self):
        """Test cache statistics tracking."""
        key1 = "example1.com:A:8.8.8.8"
        key2 = "example2.com:A:8.8.8.8"
        
        # Initial stats
        stats = self.cache.get_stats()
        assert stats['hits'] == 0
        assert stats['misses'] == 0
        assert stats['hit_ratio'] == 0
        
        # Cache miss
        result = self.cache.get(key1)
        assert result is None
        
        stats = self.cache.get_stats()
        assert stats['misses'] == 1
        assert stats['hit_ratio'] == 0
        
        # Set and hit
        self.cache.set(key1, self.sample_response, 300)
        result = self.cache.get(key1)
        assert result is not None
        
        stats = self.cache.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_ratio'] == 0.5
        
        # Another hit
        result = self.cache.get(key1)
        stats = self.cache.get_stats()
        assert stats['hits'] == 2
        assert stats['hit_ratio'] == 2/3
    
    def test_max_size_eviction(self):
        """Test cache eviction when max size is reached."""
        cache = CacheManager(max_size=3)
        
        # Fill cache to max size
        for i in range(3):
            key = f"example{i}.com:A:8.8.8.8"
            cache.set(key, self.sample_response, 300)
        
        stats = cache.get_stats()
        assert stats['total_entries'] == 3
        assert stats['evictions'] == 0
        
        # Add one more entry (should trigger eviction)
        cache.set("example3.com:A:8.8.8.8", self.sample_response, 300)
        
        stats = cache.get_stats()
        assert stats['total_entries'] == 3  # Still max size
        assert stats['evictions'] == 1     # One eviction occurred
        
        # The oldest entry should be evicted
        assert not cache.is_cached("example0.com:A:8.8.8.8")
        assert cache.is_cached("example3.com:A:8.8.8.8")
    
    def test_cache_contents(self):
        """Test getting cache contents."""
        key = "example.com:A:8.8.8.8"
        ttl = 300
        
        # Set cache entry
        self.cache.set(key, self.sample_response, ttl)
        
        # Get cache contents
        contents = self.cache.get_cache_contents()
        
        assert key in contents
        assert contents[key]['ttl_remaining'] <= ttl
        assert contents[key]['ttl_remaining'] > 0
        assert 'created' in contents[key]
        assert 'expires' in contents[key]
        assert 'data_size' in contents[key]
    
    def test_export_import_cache(self):
        """Test exporting and importing cache data."""
        # Add some entries
        for i in range(3):
            key = f"example{i}.com:A:8.8.8.8"
            self.cache.set(key, self.sample_response, 300)
        
        # Export to temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            export_file = f.name
        
        try:
            self.cache.export_cache(export_file)
            
            # Verify export file exists and has content
            assert os.path.exists(export_file)
            
            with open(export_file, 'r') as f:
                export_data = json.load(f)
            
            assert 'timestamp' in export_data
            assert 'stats' in export_data
            assert 'entries' in export_data
            assert len(export_data['entries']) == 3
            
            # Clear cache and import
            self.cache.clear_cache()
            assert self.cache.get_stats()['total_entries'] == 0
            
            self.cache.import_cache(export_file)
            
            # Verify entries were imported
            stats = self.cache.get_stats()
            assert stats['total_entries'] == 3
            
            # Verify specific entry
            result = self.cache.get("example0.com:A:8.8.8.8")
            assert result is not None
            assert result['query_name'] == 'example.com'
            
        finally:
            # Clean up temporary file
            if os.path.exists(export_file):
                os.unlink(export_file)
    
    def test_import_nonexistent_file(self):
        """Test importing from non-existent file."""
        with pytest.raises(Exception, match="Failed to import cache"):
            self.cache.import_cache("nonexistent_file.json")
    
    def test_thread_safety(self):
        """Test thread safety of cache operations."""
        num_threads = 10
        operations_per_thread = 50
        
        def worker(thread_id):
            for i in range(operations_per_thread):
                key = f"thread{thread_id}_item{i}:A:8.8.8.8"
                
                # Set entry
                self.cache.set(key, self.sample_response, 300)
                
                # Get entry
                result = self.cache.get(key)
                assert result is not None
                
                # Check if cached
                assert self.cache.is_cached(key)
        
        # Create and start threads
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify final state
        stats = self.cache.get_stats()
        # Due to max_size limit, not all entries may be present
        assert stats['total_entries'] <= self.cache.max_size
        assert stats['hits'] > 0
    
    def test_cleanup_expired_entries(self):
        """Test automatic cleanup of expired entries."""
        # Create cache with short cleanup interval
        cache = CacheManager(max_size=10, cleanup_interval=0.5)
        
        # Add entries with short TTL
        for i in range(3):
            key = f"short_ttl{i}.com:A:8.8.8.8"
            cache.set(key, self.sample_response, 1)  # 1 second TTL
        
        # Add entries with long TTL
        for i in range(2):
            key = f"long_ttl{i}.com:A:8.8.8.8"
            cache.set(key, self.sample_response, 300)  # 5 minutes TTL
        
        # Verify all entries are present
        stats = cache.get_stats()
        assert stats['total_entries'] == 5
        
        # Wait for short TTL entries to expire and cleanup to run
        time.sleep(2)
        
        # Verify expired entries were cleaned up
        stats = cache.get_stats()
        assert stats['total_entries'] == 2  # Only long TTL entries remain
        assert stats['cleanups'] > 0
        
        # Verify specific entries
        assert not cache.is_cached("short_ttl0.com:A:8.8.8.8")
        assert cache.is_cached("long_ttl0.com:A:8.8.8.8")
        
        cache.clear_cache()


if __name__ == '__main__':
    pytest.main([__file__])