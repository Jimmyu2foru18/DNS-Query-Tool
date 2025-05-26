"""Tests for DNS Packet Builder functionality."""

import pytest
import struct
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from packet_builder import DNSPacketBuilder


class TestDNSPacketBuilder:
    """Test cases for DNSPacketBuilder class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.builder = DNSPacketBuilder()
    
    def test_init(self):
        """Test packet builder initialization."""
        builder = DNSPacketBuilder()
        assert builder.RECORD_TYPES['A'] == 1
        assert builder.RECORD_TYPES['AAAA'] == 28
        assert builder.CLASS_IN == 1
    
    def test_build_header(self):
        """Test DNS header construction."""
        transaction_id = 0x1234
        header = self.builder._build_header(transaction_id)
        
        # Header should be exactly 12 bytes
        assert len(header) == 12
        
        # Unpack and verify header fields
        id_field, flags, qdcount, ancount, nscount, arcount = struct.unpack('!HHHHHH', header)
        
        assert id_field == transaction_id
        assert flags == 0x0100  # RD=1, others=0
        assert qdcount == 1      # One question
        assert ancount == 0      # No answers in query
        assert nscount == 0      # No authority records in query
        assert arcount == 0      # No additional records in query
    
    def test_encode_domain_name_simple(self):
        """Test encoding of simple domain name."""
        domain = "example.com"
        encoded = self.builder._encode_domain_name(domain)
        
        # Should be: \x07example\x03com\x00
        expected = b'\x07example\x03com\x00'
        assert encoded == expected
    
    def test_encode_domain_name_subdomain(self):
        """Test encoding of subdomain."""
        domain = "www.example.com"
        encoded = self.builder._encode_domain_name(domain)
        
        # Should be: \x03www\x07example\x03com\x00
        expected = b'\x03www\x07example\x03com\x00'
        assert encoded == expected
    
    def test_encode_domain_name_root(self):
        """Test encoding of root domain."""
        domain = "."
        encoded = self.builder._encode_domain_name(domain)
        
        # Should be just the terminating zero
        expected = b'\x00'
        assert encoded == expected
    
    def test_encode_domain_name_empty(self):
        """Test encoding of empty domain name."""
        with pytest.raises(ValueError, match="Invalid domain name length"):
            self.builder._encode_domain_name("")
    
    def test_encode_domain_name_too_long(self):
        """Test encoding of domain name that's too long."""
        # Create a domain name longer than 253 characters
        long_domain = "a" * 250 + ".com"
        with pytest.raises(ValueError, match="Invalid domain name length"):
            self.builder._encode_domain_name(long_domain)
    
    def test_encode_domain_name_label_too_long(self):
        """Test encoding of domain with label longer than 63 characters."""
        # Create a label longer than 63 characters
        long_label = "a" * 64
        domain = f"{long_label}.com"
        with pytest.raises(ValueError, match="Label too long"):
            self.builder._encode_domain_name(domain)
    
    def test_build_question_a_record(self):
        """Test building question section for A record."""
        domain = "example.com"
        record_type = "A"
        
        question = self.builder._build_question(domain, record_type)
        
        # Should contain encoded domain name + QTYPE + QCLASS
        expected_name = b'\x07example\x03com\x00'
        expected_type_class = struct.pack('!HH', 1, 1)  # A record, IN class
        expected = expected_name + expected_type_class
        
        assert question == expected
    
    def test_build_question_aaaa_record(self):
        """Test building question section for AAAA record."""
        domain = "example.com"
        record_type = "AAAA"
        
        question = self.builder._build_question(domain, record_type)
        
        # Should contain encoded domain name + QTYPE + QCLASS
        expected_name = b'\x07example\x03com\x00'
        expected_type_class = struct.pack('!HH', 28, 1)  # AAAA record, IN class
        expected = expected_name + expected_type_class
        
        assert question == expected
    
    def test_build_question_mx_record(self):
        """Test building question section for MX record."""
        domain = "example.com"
        record_type = "MX"
        
        question = self.builder._build_question(domain, record_type)
        
        # Should contain encoded domain name + QTYPE + QCLASS
        expected_name = b'\x07example\x03com\x00'
        expected_type_class = struct.pack('!HH', 15, 1)  # MX record, IN class
        expected = expected_name + expected_type_class
        
        assert question == expected
    
    def test_build_query_complete(self):
        """Test building complete DNS query packet."""
        domain = "example.com"
        record_type = "A"
        transaction_id = 0x1234
        
        packet = self.builder.build_query(domain, record_type, transaction_id)
        
        # Packet should contain header + question
        assert len(packet) > 12  # At least header size
        
        # Verify header portion
        header = packet[:12]
        id_field, flags, qdcount, ancount, nscount, arcount = struct.unpack('!HHHHHH', header)
        
        assert id_field == transaction_id
        assert flags == 0x0100
        assert qdcount == 1
        assert ancount == 0
        assert nscount == 0
        assert arcount == 0
        
        # Verify question portion contains encoded domain
        question = packet[12:]
        assert question.startswith(b'\x07example\x03com\x00')
    
    def test_build_query_unsupported_type(self):
        """Test building query with unsupported record type."""
        with pytest.raises(ValueError, match="Unsupported record type: INVALID"):
            self.builder.build_query("example.com", "INVALID", 1)
    
    def test_build_reverse_query_valid_ip(self):
        """Test building reverse DNS query for valid IP."""
        ip_address = "192.168.1.1"
        transaction_id = 0x5678
        
        packet = self.builder.build_reverse_query(ip_address, transaction_id)
        
        # Should build query for 1.1.168.192.in-addr.arpa
        assert len(packet) > 12
        
        # Verify header
        header = packet[:12]
        id_field, flags, qdcount, ancount, nscount, arcount = struct.unpack('!HHHHHH', header)
        
        assert id_field == transaction_id
        assert qdcount == 1
        
        # Question should contain reversed IP domain
        question = packet[12:]
        # Should contain encoded "1.1.168.192.in-addr.arpa"
        assert b'\x01\x31\x01\x31\x03\x31\x36\x38\x03\x31\x39\x32\x07in-addr\x04arpa\x00' in question
    
    def test_build_reverse_query_invalid_ip(self):
        """Test building reverse DNS query for invalid IP."""
        with pytest.raises(ValueError, match="Invalid IP address"):
            self.builder.build_reverse_query("invalid.ip", 1)
        
        with pytest.raises(ValueError, match="Invalid IP address"):
            self.builder.build_reverse_query("192.168.1", 1)
        
        with pytest.raises(ValueError, match="Invalid IP address"):
            self.builder.build_reverse_query("192.168.1.1.1", 1)
    
    def test_get_supported_types(self):
        """Test getting list of supported record types."""
        supported_types = self.builder.get_supported_types()
        
        expected_types = ['A', 'NS', 'CNAME', 'MX', 'TXT', 'AAAA']
        
        assert isinstance(supported_types, list)
        for record_type in expected_types:
            assert record_type in supported_types
    
    def test_record_type_constants(self):
        """Test that record type constants are correct."""
        assert self.builder.RECORD_TYPES['A'] == 1
        assert self.builder.RECORD_TYPES['NS'] == 2
        assert self.builder.RECORD_TYPES['CNAME'] == 5
        assert self.builder.RECORD_TYPES['MX'] == 15
        assert self.builder.RECORD_TYPES['TXT'] == 16
        assert self.builder.RECORD_TYPES['AAAA'] == 28
    
    def test_class_constant(self):
        """Test that class constant is correct."""
        assert self.builder.CLASS_IN == 1
    
    def test_build_query_different_transaction_ids(self):
        """Test that different transaction IDs produce different packets."""
        domain = "example.com"
        record_type = "A"
        
        packet1 = self.builder.build_query(domain, record_type, 0x1111)
        packet2 = self.builder.build_query(domain, record_type, 0x2222)
        
        # Packets should be different (different transaction IDs)
        assert packet1 != packet2
        
        # But only the first 2 bytes (transaction ID) should differ
        assert packet1[2:] == packet2[2:]
    
    def test_build_query_different_domains(self):
        """Test building queries for different domains."""
        transaction_id = 0x1234
        record_type = "A"
        
        packet1 = self.builder.build_query("example.com", record_type, transaction_id)
        packet2 = self.builder.build_query("google.com", record_type, transaction_id)
        
        # Packets should be different (different domains)
        assert packet1 != packet2
        
        # Headers should be the same
        assert packet1[:12] == packet2[:12]
    
    def test_build_query_different_record_types(self):
        """Test building queries for different record types."""
        domain = "example.com"
        transaction_id = 0x1234
        
        packet_a = self.builder.build_query(domain, "A", transaction_id)
        packet_mx = self.builder.build_query(domain, "MX", transaction_id)
        
        # Packets should be different (different record types)
        assert packet_a != packet_mx
        
        # Headers should be the same
        assert packet_a[:12] == packet_mx[:12]
        
        # Domain encoding should be the same, but QTYPE should differ
        domain_len = len(b'\x07example\x03com\x00')
        assert packet_a[12:12+domain_len] == packet_mx[12:12+domain_len]
        
        # Extract QTYPE from both packets
        qtype_offset = 12 + domain_len
        qtype_a = struct.unpack('!H', packet_a[qtype_offset:qtype_offset+2])[0]
        qtype_mx = struct.unpack('!H', packet_mx[qtype_offset:qtype_offset+2])[0]
        
        assert qtype_a == 1   # A record
        assert qtype_mx == 15  # MX record


if __name__ == '__main__':
    pytest.main([__file__])