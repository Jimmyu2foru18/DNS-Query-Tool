"""Tests for DNS Client functionality."""

import pytest
import socket
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dns_client import DNSClient
from cache_manager import CacheManager


class TestDNSClient:
    """Test cases for DNSClient class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cache_manager = CacheManager()
        self.dns_client = DNSClient(cache_manager=self.cache_manager)
    
    def test_init_with_cache(self):
        """Test DNS client initialization with cache manager."""
        client = DNSClient(cache_manager=self.cache_manager)
        assert client.cache_manager is self.cache_manager
        assert client.packet_builder is not None
        assert client.packet_parser is not None
    
    def test_init_without_cache(self):
        """Test DNS client initialization without cache manager."""
        client = DNSClient()
        assert client.cache_manager is None
        assert client.packet_builder is not None
        assert client.packet_parser is not None
    
    @patch('dns_client.socket.socket')
    def test_send_udp_query_success(self, mock_socket):
        """Test successful UDP query."""
        # Mock socket behavior
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b'\x00\x01' + b'\x00' * 10, ('8.8.8.8', 53))
        
        query_packet = b'\x00\x01' + b'\x00' * 10
        
        result = self.dns_client._send_udp_query(
            query_packet, '8.8.8.8', 53, 5, False
        )
        
        assert result == b'\x00\x01' + b'\x00' * 10
        mock_sock.sendto.assert_called_once_with(query_packet, ('8.8.8.8', 53))
        mock_sock.recvfrom.assert_called_once_with(4096)
        mock_sock.close.assert_called_once()
    
    @patch('dns_client.socket.socket')
    def test_send_udp_query_timeout(self, mock_socket):
        """Test UDP query timeout."""
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        mock_sock.recvfrom.side_effect = socket.timeout()
        
        query_packet = b'\x00\x01' + b'\x00' * 10
        
        with pytest.raises(Exception, match="DNS query timeout"):
            self.dns_client._send_udp_query(
                query_packet, '8.8.8.8', 53, 5, False
            )
    
    @patch('dns_client.socket.socket')
    def test_send_udp_query_socket_error(self, mock_socket):
        """Test UDP query socket error."""
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        mock_sock.sendto.side_effect = socket.error("Network error")
        
        query_packet = b'\x00\x01' + b'\x00' * 10
        
        with pytest.raises(Exception, match="DNS query failed"):
            self.dns_client._send_udp_query(
                query_packet, '8.8.8.8', 53, 5, False
            )
    
    def test_get_minimum_ttl_with_records(self):
        """Test getting minimum TTL from response with records."""
        response = {
            'answers': [
                {'ttl': 300},
                {'ttl': 600}
            ],
            'authority': [
                {'ttl': 3600}
            ],
            'additional': [
                {'ttl': 1800}
            ]
        }
        
        min_ttl = self.dns_client._get_minimum_ttl(response)
        assert min_ttl == 300
    
    def test_get_minimum_ttl_empty_response(self):
        """Test getting minimum TTL from empty response."""
        response = {
            'answers': [],
            'authority': [],
            'additional': []
        }
        
        min_ttl = self.dns_client._get_minimum_ttl(response)
        assert min_ttl == 300  # Default TTL
    
    def test_get_minimum_ttl_no_ttl_fields(self):
        """Test getting minimum TTL when records have no TTL field."""
        response = {
            'answers': [
                {'name': 'example.com', 'type': 'A'},
                {'name': 'example.com', 'type': 'A'}
            ],
            'authority': [],
            'additional': []
        }
        
        min_ttl = self.dns_client._get_minimum_ttl(response)
        assert min_ttl == 300  # Default TTL
    
    @patch.object(DNSClient, '_send_udp_query')
    @patch.object(DNSClient, 'packet_builder')
    @patch.object(DNSClient, 'packet_parser')
    def test_query_cache_hit(self, mock_parser, mock_builder, mock_send):
        """Test DNS query with cache hit."""
        # Set up cache with existing entry
        cache_key = "example.com:A:8.8.8.8"
        cached_response = {
            'query_name': 'example.com',
            'query_type': 'A',
            'status': 'NOERROR',
            'answers': [{'name': 'example.com', 'type': 'A', 'data': '1.2.3.4', 'ttl': 300}]
        }
        self.cache_manager.set(cache_key, cached_response, 300)
        
        result = self.dns_client.query('example.com', 'A', '8.8.8.8')
        
        # Should return cached response without calling network functions
        assert result['query_name'] == 'example.com'
        assert result['status'] == 'NOERROR'
        mock_send.assert_not_called()
        mock_builder.build_query.assert_not_called()
    
    @patch.object(DNSClient, '_send_udp_query')
    def test_query_cache_miss(self, mock_send):
        """Test DNS query with cache miss."""
        # Mock the network response
        mock_response_packet = b'\x12\x34' + b'\x81\x80' + b'\x00\x01' * 4 + b'\x00' * 20
        mock_send.return_value = mock_response_packet
        
        # Mock packet builder and parser
        with patch.object(self.dns_client.packet_builder, 'build_query') as mock_build, \
             patch.object(self.dns_client.packet_parser, 'parse_response') as mock_parse:
            
            mock_build.return_value = b'query_packet'
            mock_parse.return_value = {
                'status': 'NOERROR',
                'answers': [{'name': 'example.com', 'type': 'A', 'data': '1.2.3.4', 'ttl': 300}]
            }
            
            result = self.dns_client.query('example.com', 'A', '8.8.8.8')
            
            # Should call network functions
            mock_build.assert_called_once()
            mock_send.assert_called_once()
            mock_parse.assert_called_once()
            
            # Should add query info to response
            assert result['query_name'] == 'example.com'
            assert result['query_type'] == 'A'
            assert result['dns_server'] == '8.8.8.8'
    
    @patch.object(DNSClient, 'query')
    def test_bulk_query_success(self, mock_query):
        """Test bulk query with successful responses."""
        mock_query.side_effect = [
            {'query_name': 'example.com', 'status': 'NOERROR'},
            {'query_name': 'google.com', 'status': 'NOERROR'}
        ]
        
        domains = ['example.com', 'google.com']
        results = self.dns_client.bulk_query(domains)
        
        assert len(results) == 2
        assert 'example.com' in results
        assert 'google.com' in results
        assert results['example.com']['status'] == 'NOERROR'
        assert results['google.com']['status'] == 'NOERROR'
    
    @patch.object(DNSClient, 'query')
    def test_bulk_query_with_errors(self, mock_query):
        """Test bulk query with some errors."""
        mock_query.side_effect = [
            {'query_name': 'example.com', 'status': 'NOERROR'},
            Exception('Network error')
        ]
        
        domains = ['example.com', 'invalid.domain']
        results = self.dns_client.bulk_query(domains)
        
        assert len(results) == 2
        assert 'example.com' in results
        assert 'invalid.domain' in results
        assert results['example.com']['status'] == 'NOERROR'
        assert 'error' in results['invalid.domain']
        assert 'Network error' in results['invalid.domain']['error']
    
    def test_query_without_cache_manager(self):
        """Test query behavior when no cache manager is provided."""
        client = DNSClient()  # No cache manager
        
        with patch.object(client, '_send_udp_query') as mock_send, \
             patch.object(client.packet_builder, 'build_query') as mock_build, \
             patch.object(client.packet_parser, 'parse_response') as mock_parse:
            
            mock_send.return_value = b'response_packet'
            mock_build.return_value = b'query_packet'
            mock_parse.return_value = {
                'status': 'NOERROR',
                'answers': [{'name': 'example.com', 'type': 'A', 'data': '1.2.3.4', 'ttl': 300}]
            }
            
            result = client.query('example.com')
            
            # Should work without caching
            assert result['query_name'] == 'example.com'
            mock_send.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__])