"""Integration tests for DNS Query Tool."""

import pytest
import sys
import os
import tempfile
import json
from unittest.mock import patch, MagicMock

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dns_client import DNSClient
from cache_manager import CacheManager
from visualizer import Visualizer
from packet_builder import DNSPacketBuilder
from packet_parser import DNSPacketParser


class TestIntegration:
    """Integration tests for the complete DNS Query Tool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cache_manager = CacheManager(max_size=100)
        self.dns_client = DNSClient(cache_manager=self.cache_manager)
        self.visualizer = Visualizer()
        
        # Sample DNS response for mocking
        self.sample_response = {
            'transaction_id': 12345,
            'flags': {
                'qr': 1, 'opcode': 0, 'aa': 0, 'tc': 0, 'rd': 1,
                'ra': 1, 'z': 0, 'rcode': 0
            },
            'query_name': 'example.com',
            'query_type': 'A',
            'query_class': 'IN',
            'status': 'NOERROR',
            'answers': [{
                'name': 'example.com',
                'type': 'A',
                'class': 'IN',
                'ttl': 300,
                'data': '93.184.216.34'
            }],
            'authorities': [],
            'additional': []
        }
    
    def teardown_method(self):
        """Clean up after tests."""
        self.cache_manager.clear_cache()
    
    def test_packet_builder_parser_integration(self):
        """Test that packet builder and parser work together correctly."""
        builder = DNSPacketBuilder()
        parser = DNSPacketParser()
        
        # Build a query packet
        query_packet = builder.build_query('example.com', 'A')
        assert len(query_packet) > 0
        
        # Parse the query packet (simulate what a DNS server would do)
        # Note: This is mainly to test the structure, not full parsing
        # since we're building queries, not responses
        assert query_packet[:2] != b'\x00\x00'  # Should have transaction ID
    
    def test_dns_client_cache_integration(self):
        """Test DNS client integration with cache manager."""
        domain = 'example.com'
        record_type = 'A'
        server = '8.8.8.8'
        
        # Mock the UDP query to return our sample response
        with patch.object(self.dns_client, '_send_udp_query') as mock_udp:
            mock_udp.return_value = self.sample_response
            
            # First query - should hit the network and cache the result
            result1 = self.dns_client.query(domain, record_type, server)
            
            assert result1 is not None
            assert result1['query_name'] == domain
            assert result1['status'] == 'NOERROR'
            assert len(result1['answers']) == 1
            
            # Verify it was cached
            cache_key = f"{domain}:{record_type}:{server}"
            assert self.cache_manager.is_cached(cache_key)
            
            # Second query - should hit the cache
            result2 = self.dns_client.query(domain, record_type, server)
            
            assert result2 is not None
            assert result2['query_name'] == domain
            
            # UDP should only be called once (first query)
            assert mock_udp.call_count == 1
            
            # Verify cache statistics
            stats = self.cache_manager.get_stats()
            assert stats['hits'] == 1
            assert stats['misses'] == 1
    
    def test_dns_client_without_cache(self):
        """Test DNS client without cache manager."""
        dns_client_no_cache = DNSClient()
        
        domain = 'example.com'
        record_type = 'A'
        server = '8.8.8.8'
        
        # Mock the UDP query
        with patch.object(dns_client_no_cache, '_send_udp_query') as mock_udp:
            mock_udp.return_value = self.sample_response
            
            # Multiple queries should all hit the network
            result1 = dns_client_no_cache.query(domain, record_type, server)
            result2 = dns_client_no_cache.query(domain, record_type, server)
            
            assert result1 is not None
            assert result2 is not None
            
            # UDP should be called twice (no caching)
            assert mock_udp.call_count == 2
    
    def test_bulk_query_with_cache(self):
        """Test bulk queries with caching."""
        domains = ['example.com', 'google.com', 'github.com']
        record_type = 'A'
        server = '8.8.8.8'
        
        # Mock responses for each domain
        responses = {}
        for domain in domains:
            response = self.sample_response.copy()
            response['query_name'] = domain
            response['answers'] = [{
                'name': domain,
                'type': 'A',
                'class': 'IN',
                'ttl': 300,
                'data': f'192.168.1.{domains.index(domain) + 1}'
            }]
            responses[domain] = response
        
        def mock_udp_side_effect(domain, record_type, server, timeout):
            return responses.get(domain, self.sample_response)
        
        with patch.object(self.dns_client, '_send_udp_query') as mock_udp:
            mock_udp.side_effect = mock_udp_side_effect
            
            # Perform bulk query
            results = self.dns_client.bulk_query(domains, record_type, server)
            
            assert len(results) == len(domains)
            
            # Verify each result
            for i, (domain, result) in enumerate(results):
                assert domain in domains
                assert result is not None
                assert result['query_name'] == domain
                assert result['answers'][0]['data'] == f'192.168.1.{domains.index(domain) + 1}'
            
            # Verify all domains are cached
            for domain in domains:
                cache_key = f"{domain}:{record_type}:{server}"
                assert self.cache_manager.is_cached(cache_key)
            
            # Second bulk query should hit cache
            results2 = self.dns_client.bulk_query(domains, record_type, server)
            
            # UDP should only be called once per domain (first query)
            assert mock_udp.call_count == len(domains)
            
            # Verify cache statistics
            stats = self.cache_manager.get_stats()
            assert stats['hits'] == len(domains)  # Second bulk query hits
            assert stats['misses'] == len(domains)  # First bulk query misses
    
    def test_visualizer_integration(self):
        """Test integration with visualizer."""
        domain = 'example.com'
        record_type = 'A'
        server = '8.8.8.8'
        
        # Mock the UDP query with timing
        def mock_udp_with_timing(*args, **kwargs):
            import time
            time.sleep(0.1)  # Simulate 100ms response time
            return self.sample_response
        
        with patch.object(self.dns_client, '_send_udp_query') as mock_udp:
            mock_udp.side_effect = mock_udp_with_timing
            
            # Perform query and measure time
            import time
            start_time = time.time()
            result = self.dns_client.query(domain, record_type, server)
            end_time = time.time()
            
            response_time = (end_time - start_time) * 1000  # Convert to ms
            
            # Add to visualizer
            self.visualizer.add_query_time(domain, record_type, response_time)
            
            # Add cache stats
            cache_stats = self.cache_manager.get_stats()
            self.visualizer.add_cache_stats(cache_stats)
            
            # Verify data was added
            assert len(self.visualizer.query_times) == 1
            assert len(self.visualizer.cache_stats) == 1
            
            query_data = self.visualizer.query_times[0]
            assert query_data['domain'] == domain
            assert query_data['record_type'] == record_type
            assert query_data['response_time'] > 0
    
    def test_cache_export_import_integration(self):
        """Test cache export/import functionality."""
        domains = ['example.com', 'google.com']
        record_type = 'A'
        server = '8.8.8.8'
        
        # Add some entries to cache
        with patch.object(self.dns_client, '_send_udp_query') as mock_udp:
            mock_udp.return_value = self.sample_response
            
            for domain in domains:
                self.dns_client.query(domain, record_type, server)
        
        # Export cache
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            export_file = f.name
        
        try:
            self.cache_manager.export_cache(export_file)
            
            # Verify export file
            assert os.path.exists(export_file)
            
            with open(export_file, 'r') as f:
                export_data = json.load(f)
            
            assert 'entries' in export_data
            assert len(export_data['entries']) == len(domains)
            
            # Clear cache and import
            self.cache_manager.clear_cache()
            assert self.cache_manager.get_stats()['total_entries'] == 0
            
            self.cache_manager.import_cache(export_file)
            
            # Verify import
            stats = self.cache_manager.get_stats()
            assert stats['total_entries'] == len(domains)
            
            # Verify entries are accessible
            for domain in domains:
                cache_key = f"{domain}:{record_type}:{server}"
                assert self.cache_manager.is_cached(cache_key)
        
        finally:
            if os.path.exists(export_file):
                os.unlink(export_file)
    
    def test_error_handling_integration(self):
        """Test error handling across components."""
        domain = 'nonexistent.invalid'
        record_type = 'A'
        server = '8.8.8.8'
        
        # Mock a timeout error
        with patch.object(self.dns_client, '_send_udp_query') as mock_udp:
            mock_udp.side_effect = Exception("Timeout")
            
            # Query should handle the error gracefully
            result = self.dns_client.query(domain, record_type, server)
            
            # Should return None or error response
            assert result is None or result.get('status') == 'ERROR'
            
            # Cache should not contain the failed query
            cache_key = f"{domain}:{record_type}:{server}"
            assert not self.cache_manager.is_cached(cache_key)
    
    def test_different_record_types_integration(self):
        """Test integration with different DNS record types."""
        domain = 'example.com'
        server = '8.8.8.8'
        record_types = ['A', 'AAAA', 'MX', 'NS', 'TXT']
        
        # Mock responses for different record types
        def mock_udp_for_record_type(domain, record_type, server, timeout):
            response = self.sample_response.copy()
            response['query_type'] = record_type
            
            if record_type == 'A':
                response['answers'] = [{
                    'name': domain, 'type': 'A', 'class': 'IN',
                    'ttl': 300, 'data': '93.184.216.34'
                }]
            elif record_type == 'AAAA':
                response['answers'] = [{
                    'name': domain, 'type': 'AAAA', 'class': 'IN',
                    'ttl': 300, 'data': '2606:2800:220:1:248:1893:25c8:1946'
                }]
            elif record_type == 'MX':
                response['answers'] = [{
                    'name': domain, 'type': 'MX', 'class': 'IN',
                    'ttl': 300, 'data': {'priority': 10, 'exchange': 'mail.example.com'}
                }]
            elif record_type == 'NS':
                response['answers'] = [{
                    'name': domain, 'type': 'NS', 'class': 'IN',
                    'ttl': 300, 'data': 'ns1.example.com'
                }]
            elif record_type == 'TXT':
                response['answers'] = [{
                    'name': domain, 'type': 'TXT', 'class': 'IN',
                    'ttl': 300, 'data': 'v=spf1 include:_spf.example.com ~all'
                }]
            
            return response
        
        with patch.object(self.dns_client, '_send_udp_query') as mock_udp:
            mock_udp.side_effect = mock_udp_for_record_type
            
            # Query each record type
            for record_type in record_types:
                result = self.dns_client.query(domain, record_type, server)
                
                assert result is not None
                assert result['query_type'] == record_type
                assert len(result['answers']) == 1
                
                # Verify caching
                cache_key = f"{domain}:{record_type}:{server}"
                assert self.cache_manager.is_cached(cache_key)
            
            # Verify all record types are cached separately
            stats = self.cache_manager.get_stats()
            assert stats['total_entries'] == len(record_types)
    
    def test_concurrent_queries_integration(self):
        """Test concurrent queries with caching."""
        import threading
        import time
        
        domain = 'example.com'
        record_type = 'A'
        server = '8.8.8.8'
        num_threads = 5
        
        results = []
        errors = []
        
        def worker():
            try:
                with patch.object(self.dns_client, '_send_udp_query') as mock_udp:
                    mock_udp.return_value = self.sample_response
                    
                    result = self.dns_client.query(domain, record_type, server)
                    results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create and start threads
        threads = []
        for _ in range(num_threads):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == num_threads
        
        # All results should be valid
        for result in results:
            assert result is not None
            assert result['query_name'] == domain
    
    def test_memory_usage_integration(self):
        """Test memory usage with large number of queries."""
        import gc
        
        # Perform many queries to test memory management
        num_queries = 100
        
        with patch.object(self.dns_client, '_send_udp_query') as mock_udp:
            mock_udp.return_value = self.sample_response
            
            for i in range(num_queries):
                domain = f"example{i}.com"
                result = self.dns_client.query(domain, 'A', '8.8.8.8')
                assert result is not None
                
                # Add to visualizer
                self.visualizer.add_query_time(domain, 'A', 100.0 + i)
        
        # Force garbage collection
        gc.collect()
        
        # Verify cache size is managed (should not exceed max_size)
        stats = self.cache_manager.get_stats()
        assert stats['total_entries'] <= self.cache_manager.max_size
        
        # Verify visualizer data
        assert len(self.visualizer.query_times) == num_queries


if __name__ == '__main__':
    pytest.main([__file__])