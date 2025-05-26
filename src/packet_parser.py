"""DNS Packet Parser - Parses raw DNS response packets according to RFC 1035."""

import struct
import socket


class DNSPacketParser:
    """Parses DNS response packets from binary format."""
    
    # DNS record type constants (reverse mapping)
    RECORD_TYPES = {
        1: 'A',
        2: 'NS',
        5: 'CNAME',
        12: 'PTR',
        15: 'MX',
        16: 'TXT',
        28: 'AAAA'
    }
    
    # DNS response codes
    RESPONSE_CODES = {
        0: 'NOERROR',
        1: 'FORMERR',
        2: 'SERVFAIL',
        3: 'NXDOMAIN',
        4: 'NOTIMP',
        5: 'REFUSED'
    }
    
    def __init__(self):
        """Initialize DNS packet parser."""
        pass
    
    def parse_response(self, packet, expected_id=None, verbose=False):
        """Parse a DNS response packet.
        
        Args:
            packet: Raw DNS response packet bytes
            expected_id: Expected transaction ID (for validation)
            verbose: Enable verbose output
            
        Returns:
            dict: Parsed DNS response with sections
            
        Raises:
            Exception: If packet is malformed or validation fails
        """
        if len(packet) < 12:
            raise Exception("DNS packet too short (minimum 12 bytes required)")
        
        offset = 0
        
        # Parse header
        header, offset = self._parse_header(packet, offset, verbose)
        
        # Validate transaction ID if provided
        if expected_id is not None and header['id'] != expected_id:
            raise Exception(f"Transaction ID mismatch: expected {expected_id}, got {header['id']}")
        
        # Initialize response structure
        response = {
            'id': header['id'],
            'status': self.RESPONSE_CODES.get(header['rcode'], f'UNKNOWN({header["rcode"]}'),
            'flags': header['flags'],
            'questions': [],
            'answers': [],
            'authority': [],
            'additional': []
        }
        
        try:
            # Parse question section
            for _ in range(header['qdcount']):
                question, offset = self._parse_question(packet, offset, verbose)
                response['questions'].append(question)
            
            # Parse answer section
            for _ in range(header['ancount']):
                answer, offset = self._parse_resource_record(packet, offset, verbose)
                response['answers'].append(answer)
            
            # Parse authority section
            for _ in range(header['nscount']):
                authority, offset = self._parse_resource_record(packet, offset, verbose)
                response['authority'].append(authority)
            
            # Parse additional section
            for _ in range(header['arcount']):
                additional, offset = self._parse_resource_record(packet, offset, verbose)
                response['additional'].append(additional)
                
        except Exception as e:
            if verbose:
                print(f"Warning: Error parsing DNS sections: {e}")
            # Return partial response if sections can't be fully parsed
        
        return response
    
    def _parse_header(self, packet, offset, verbose):
        """Parse DNS header (12 bytes).
        
        Args:
            packet: Raw packet bytes
            offset: Current offset in packet
            verbose: Enable verbose output
            
        Returns:
            tuple: (header_dict, new_offset)
        """
        header_data = struct.unpack('!HHHHHH', packet[offset:offset+12])
        
        header = {
            'id': header_data[0],
            'flags': header_data[1],
            'qdcount': header_data[2],  # Questions
            'ancount': header_data[3],  # Answers
            'nscount': header_data[4],  # Authority
            'arcount': header_data[5]   # Additional
        }
        
        # Parse flags
        flags = header['flags']
        header['qr'] = (flags >> 15) & 1  # Query/Response
        header['opcode'] = (flags >> 11) & 15  # Operation code
        header['aa'] = (flags >> 10) & 1  # Authoritative answer
        header['tc'] = (flags >> 9) & 1   # Truncated
        header['rd'] = (flags >> 8) & 1   # Recursion desired
        header['ra'] = (flags >> 7) & 1   # Recursion available
        header['rcode'] = flags & 15      # Response code
        
        if verbose:
            print(f"DNS Header: ID={header['id']}, QR={header['qr']}, "
                  f"RCODE={header['rcode']}, Questions={header['qdcount']}, "
                  f"Answers={header['ancount']}")
        
        return header, offset + 12
    
    def _parse_question(self, packet, offset, verbose):
        """Parse DNS question section.
        
        Args:
            packet: Raw packet bytes
            offset: Current offset in packet
            verbose: Enable verbose output
            
        Returns:
            tuple: (question_dict, new_offset)
        """
        # Parse domain name
        name, offset = self._parse_domain_name(packet, offset)
        
        # Parse QTYPE and QCLASS
        qtype, qclass = struct.unpack('!HH', packet[offset:offset+4])
        offset += 4
        
        question = {
            'name': name,
            'type': self.RECORD_TYPES.get(qtype, f'TYPE{qtype}'),
            'class': qclass
        }
        
        if verbose:
            print(f"Question: {name} {question['type']}")
        
        return question, offset
    
    def _parse_resource_record(self, packet, offset, verbose):
        """Parse DNS resource record.
        
        Args:
            packet: Raw packet bytes
            offset: Current offset in packet
            verbose: Enable verbose output
            
        Returns:
            tuple: (record_dict, new_offset)
        """
        # Parse name
        name, offset = self._parse_domain_name(packet, offset)
        
        # Parse TYPE, CLASS, TTL, RDLENGTH
        rtype, rclass, ttl, rdlength = struct.unpack('!HHIH', packet[offset:offset+10])
        offset += 10
        
        # Parse RDATA
        rdata = packet[offset:offset+rdlength]
        offset += rdlength
        
        # Parse record data based on type
        record_type = self.RECORD_TYPES.get(rtype, f'TYPE{rtype}')
        parsed_data = self._parse_record_data(record_type, rdata, packet)
        
        record = {
            'name': name,
            'type': record_type,
            'class': rclass,
            'ttl': ttl,
            'data': parsed_data
        }
        
        if verbose:
            print(f"Record: {name} {ttl} {record_type} {parsed_data}")
        
        return record, offset
    
    def _parse_domain_name(self, packet, offset):
        """Parse domain name with compression support.
        
        Args:
            packet: Raw packet bytes
            offset: Current offset in packet
            
        Returns:
            tuple: (domain_name, new_offset)
        """
        labels = []
        original_offset = offset
        jumped = False
        
        while True:
            if offset >= len(packet):
                break
                
            length = packet[offset]
            
            # Check for compression (pointer)
            if (length & 0xC0) == 0xC0:
                if not jumped:
                    original_offset = offset + 2
                    jumped = True
                
                # Extract pointer offset
                pointer = struct.unpack('!H', packet[offset:offset+2])[0] & 0x3FFF
                offset = pointer
                continue
            
            # End of name
            if length == 0:
                offset += 1
                break
            
            # Regular label
            offset += 1
            if offset + length > len(packet):
                break
                
            label = packet[offset:offset+length].decode('ascii', errors='ignore')
            labels.append(label)
            offset += length
        
        domain_name = '.'.join(labels) if labels else '.'
        final_offset = original_offset if jumped else offset
        
        return domain_name, final_offset
    
    def _parse_record_data(self, record_type, rdata, packet):
        """Parse record data based on record type.
        
        Args:
            record_type: DNS record type string
            rdata: Raw record data bytes
            packet: Full packet (for name compression)
            
        Returns:
            str: Parsed record data
        """
        try:
            if record_type == 'A':
                # IPv4 address
                if len(rdata) == 4:
                    return socket.inet_ntoa(rdata)
            
            elif record_type == 'AAAA':
                # IPv6 address
                if len(rdata) == 16:
                    return socket.inet_ntop(socket.AF_INET6, rdata)
            
            elif record_type in ['NS', 'CNAME', 'PTR']:
                # Domain name
                name, _ = self._parse_domain_name(packet, packet.find(rdata))
                return name
            
            elif record_type == 'MX':
                # Mail exchange: priority + domain name
                if len(rdata) >= 3:
                    priority = struct.unpack('!H', rdata[:2])[0]
                    # Find the domain name in the packet
                    # This is a simplified approach
                    domain_start = packet.find(rdata[2:])
                    if domain_start != -1:
                        name, _ = self._parse_domain_name(packet, domain_start)
                        return f"{priority} {name}"
                    return f"{priority} <unknown>"
            
            elif record_type == 'TXT':
                # Text record
                text_parts = []
                offset = 0
                while offset < len(rdata):
                    if offset >= len(rdata):
                        break
                    length = rdata[offset]
                    offset += 1
                    if offset + length <= len(rdata):
                        text_parts.append(rdata[offset:offset+length].decode('ascii', errors='ignore'))
                        offset += length
                    else:
                        break
                return '"' + ''.join(text_parts) + '"'
            
            # Default: return hex representation
            return rdata.hex()
            
        except Exception:
            # Fallback to hex representation
            return rdata.hex()