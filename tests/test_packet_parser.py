"""Tests for DNS Packet Parser functionality."""

import pytest
import struct
import socket
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from packet_parser import DNSPacketParser


class TestDNSPacketParser:
    """Test cases for DNSPacketParser class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = DNSPacketParser()
    
    def test_init(self):
        """Test packet parser initialization."""
        parser = DNSPacketParser()
        assert parser.RECORD_TYPES[1] == 'A'
        assert parser.RECORD_TYPES[28] == 'AAAA'
        assert parser.RESPONSE_CODES[0] == 'NOERROR'
    
    def create_test_header(self, transaction_id=0x1234, flags=0x8180, 
                          qdcount=1, ancount=1, nscount=0, arcount=0):
        """Create a test DNS header."""
        return struct.pack('!HHHHHH', transaction_id, flags, qdcount, ancount, nscount, arcount)
    
    def create_test_domain_name(self, domain):
        """Create encoded domain name for testing."""
        encoded = b''
        for label in domain.split('.'):
            if label:
                encoded += struct.pack('!B', len(label)) + label.encode('ascii')
        encoded += b'\x00'
        return encoded
    
    def test_parse_header_valid(self):
        """Test parsing valid DNS header."""
        transaction_id = 0x1234
        flags = 0x8180  # QR=1, RD=1, RA=1
        header_bytes = self.create_test_header(transaction_id, flags, 1, 2, 1, 0)
        
        header, offset = self.parser._parse_header(header_bytes, 0, False)
        
        assert offset == 12
        assert header['id'] == transaction_id
        assert header['flags'] == flags
        assert header['qdcount'] == 1
        assert header['ancount'] == 2
        assert header['nscount'] == 1
        assert header['arcount'] == 0
        
        # Test flag parsing
        assert header['qr'] == 1
        assert header['opcode'] == 0
        assert header['aa'] == 0
        assert header['tc'] == 0
        assert header['rd'] == 1
        assert header['ra'] == 1
        assert header['rcode'] == 0
    
    def test_parse_domain_name_simple(self):
        """Test parsing simple domain name."""
        # Create packet with "example.com"
        domain_bytes = self.create_test_domain_name("example.com")
        packet = b'\x00' * 12 + domain_bytes  # Add dummy header
        
        domain, offset = self.parser._parse_domain_name(packet, 12)
        
        assert domain == "example.com"
        assert offset == 12 + len(domain_bytes)
    
    def test_parse_domain_name_with_compression(self):
        """Test parsing domain name with compression pointer."""
        # Create packet with compression
        # First occurrence: "example.com" at offset 12
        # Second occurrence: pointer to offset 12
        domain_bytes = self.create_test_domain_name("example.com")
        pointer_bytes = struct.pack('!H', 0xC000 | 12)  # Pointer to offset 12
        
        packet = b'\x00' * 12 + domain_bytes + pointer_bytes
        
        # Parse the pointer
        domain, offset = self.parser._parse_domain_name(packet, 12 + len(domain_bytes))
        
        assert domain == "example.com"
        assert offset == 12 + len(domain_bytes) + 2  # Pointer is 2 bytes
    
    def test_parse_question_a_record(self):
        """Test parsing DNS question for A record."""
        domain_bytes = self.create_test_domain_name("example.com")
        qtype_qclass = struct.pack('!HH', 1, 1)  # A record, IN class
        question_bytes = domain_bytes + qtype_qclass
        
        packet = b'\x00' * 12 + question_bytes
        
        question, offset = self.parser._parse_question(packet, 12, False)
        
        assert question['name'] == "example.com"
        assert question['type'] == "A"
        assert question['class'] == 1
        assert offset == 12 + len(question_bytes)
    
    def test_parse_record_data_a_record(self):
        """Test parsing A record data."""
        ip_bytes = socket.inet_aton("192.168.1.1")
        
        result = self.parser._parse_record_data("A", ip_bytes, b'')
        
        assert result == "192.168.1.1"
    
    def test_parse_record_data_aaaa_record(self):
        """Test parsing AAAA record data."""
        ipv6_bytes = socket.inet_pton(socket.AF_INET6, "2001:db8::1")
        
        result = self.parser._parse_record_data("AAAA", ipv6_bytes, b'')
        
        assert result == "2001:db8::1"
    
    def test_parse_record_data_mx_record(self):
        """Test parsing MX record data."""
        priority = 10
        domain = "mail.example.com"
        domain_bytes = self.create_test_domain_name(domain)
        
        # Create MX record data: priority + domain
        mx_data = struct.pack('!H', priority) + domain_bytes
        
        # Create full packet for domain name parsing
        packet = b'\x00' * 12 + mx_data
        
        result = self.parser._parse_record_data("MX", mx_data, packet)
        
        # Result should contain priority and domain (simplified parsing)
        assert str(priority) in result
    
    def test_parse_record_data_txt_record(self):
        """Test parsing TXT record data."""
        text = "v=spf1 include:_spf.google.com ~all"
        # TXT records are length-prefixed strings
        txt_data = struct.pack('!B', len(text)) + text.encode('ascii')
        
        result = self.parser._parse_record_data("TXT", txt_data, b'')
        
        assert text in result
        assert result.startswith('"')
        assert result.endswith('"')
    
    def test_parse_record_data_unknown_type(self):
        """Test parsing unknown record type."""
        unknown_data = b'\x01\x02\x03\x04'
        
        result = self.parser._parse_record_data("UNKNOWN", unknown_data, b'')
        
        # Should return hex representation
        assert result == "01020304"
    
    def test_parse_resource_record_complete(self):
        """Test parsing complete resource record."""
        # Create A record for example.com -> 192.168.1.1
        domain_bytes = self.create_test_domain_name("example.com")
        rtype = 1  # A record
        rclass = 1  # IN
        ttl = 300
        ip_bytes = socket.inet_aton("192.168.1.1")
        rdlength = len(ip_bytes)
        
        rr_bytes = (domain_bytes + 
                   struct.pack('!HHIH', rtype, rclass, ttl, rdlength) + 
                   ip_bytes)
        
        packet = b'\x00' * 12 + rr_bytes
        
        record, offset = self.parser._parse_resource_record(packet, 12, False)
        
        assert record['name'] == "example.com"
        assert record['type'] == "A"
        assert record['class'] == rclass
        assert record['ttl'] == ttl
        assert record['data'] == "192.168.1.1"
        assert offset == 12 + len(rr_bytes)
    
    def test_parse_response_complete(self):
        """Test parsing complete DNS response."""
        transaction_id = 0x1234
        
        # Create header
        header = self.create_test_header(transaction_id, 0x8180, 1, 1, 0, 0)
        
        # Create question
        domain_bytes = self.create_test_domain_name("example.com")
        question = domain_bytes + struct.pack('!HH', 1, 1)  # A record, IN class
        
        # Create answer
        ip_bytes = socket.inet_aton("192.168.1.1")
        answer = (domain_bytes + 
                 struct.pack('!HHIH', 1, 1, 300, len(ip_bytes)) + 
                 ip_bytes)
        
        packet = header + question + answer
        
        response = self.parser.parse_response(packet, transaction_id, False)
        
        assert response['id'] == transaction_id
        assert response['status'] == 'NOERROR'
        assert len(response['questions']) == 1
        assert len(response['answers']) == 1
        assert len(response['authority']) == 0
        assert len(response['additional']) == 0
        
        # Check question
        assert response['questions'][0]['name'] == "example.com"
        assert response['questions'][0]['type'] == "A"
        
        # Check answer
        assert response['answers'][0]['name'] == "example.com"
        assert response['answers'][0]['type'] == "A"
        assert response['answers'][0]['data'] == "192.168.1.1"
        assert response['answers'][0]['ttl'] == 300
    
    def test_parse_response_transaction_id_mismatch(self):
        """Test parsing response with mismatched transaction ID."""
        header = self.create_test_header(0x1234, 0x8180, 0, 0, 0, 0)
        packet = header
        
        with pytest.raises(Exception, match="Transaction ID mismatch"):
            self.parser.parse_response(packet, 0x5678, False)
    
    def test_parse_response_packet_too_short(self):
        """Test parsing response with packet too short."""
        packet = b'\x00' * 10  # Less than 12 bytes
        
        with pytest.raises(Exception, match="DNS packet too short"):
            self.parser.parse_response(packet, None, False)
    
    def test_parse_response_malformed_sections(self):
        """Test parsing response with malformed sections."""
        # Create header indicating 1 question but no question data
        header = self.create_test_header(0x1234, 0x8180, 1, 0, 0, 0)
        packet = header  # No question data
        
        # Should not raise exception but return partial response
        response = self.parser.parse_response(packet, 0x1234, False)
        
        assert response['id'] == 0x1234
        assert response['status'] == 'NOERROR'
        # Questions list might be empty due to parsing error
    
    def test_response_codes(self):
        """Test response code mapping."""
        assert self.parser.RESPONSE_CODES[0] == 'NOERROR'
        assert self.parser.RESPONSE_CODES[1] == 'FORMERR'
        assert self.parser.RESPONSE_CODES[2] == 'SERVFAIL'
        assert self.parser.RESPONSE_CODES[3] == 'NXDOMAIN'
        assert self.parser.RESPONSE_CODES[4] == 'NOTIMP'
        assert self.parser.RESPONSE_CODES[5] == 'REFUSED'
    
    def test_parse_response_with_error_code(self):
        """Test parsing response with error code."""
        transaction_id = 0x1234
        flags = 0x8183  # QR=1, RD=1, RA=1, RCODE=3 (NXDOMAIN)
        
        header = struct.pack('!HHHHHH', transaction_id, flags, 1, 0, 0, 0)
        
        # Add minimal question
        domain_bytes = self.create_test_domain_name("nonexistent.example.com")
        question = domain_bytes + struct.pack('!HH', 1, 1)
        
        packet = header + question
        
        response = self.parser.parse_response(packet, transaction_id, False)
        
        assert response['status'] == 'NXDOMAIN'
        assert len(response['answers']) == 0
    
    def test_record_type_mapping(self):
        """Test record type number to string mapping."""
        assert self.parser.RECORD_TYPES[1] == 'A'
        assert self.parser.RECORD_TYPES[2] == 'NS'
        assert self.parser.RECORD_TYPES[5] == 'CNAME'
        assert self.parser.RECORD_TYPES[12] == 'PTR'
        assert self.parser.RECORD_TYPES[15] == 'MX'
        assert self.parser.RECORD_TYPES[16] == 'TXT'
        assert self.parser.RECORD_TYPES[28] == 'AAAA'
    
    def test_parse_response_unknown_record_type(self):
        """Test parsing response with unknown record type."""
        transaction_id = 0x1234
        
        # Create header
        header = self.create_test_header(transaction_id, 0x8180, 1, 1, 0, 0)
        
        # Create question
        domain_bytes = self.create_test_domain_name("example.com")
        question = domain_bytes + struct.pack('!HH', 1, 1)
        
        # Create answer with unknown record type (999)
        unknown_data = b'\x01\x02\x03\x04'
        answer = (domain_bytes + 
                 struct.pack('!HHIH', 999, 1, 300, len(unknown_data)) + 
                 unknown_data)
        
        packet = header + question + answer
        
        response = self.parser.parse_response(packet, transaction_id, False)
        
        assert response['answers'][0]['type'] == 'TYPE999'
        assert response['answers'][0]['data'] == '01020304'  # Hex representation


if __name__ == '__main__':
    pytest.main([__file__])