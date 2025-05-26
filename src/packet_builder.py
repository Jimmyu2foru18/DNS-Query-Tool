"""DNS Packet Builder - Constructs raw DNS query packets according to RFC 1035."""

import struct


class DNSPacketBuilder:
    """Builds DNS query packets in binary format."""
    
    # DNS record type constants
    RECORD_TYPES = {
        'A': 1,
        'NS': 2,
        'CNAME': 5,
        'PTR': 12,
        'MX': 15,
        'TXT': 16,
        'AAAA': 28
    }
    
    # DNS class constants
    CLASS_IN = 1  # Internet class
    
    def __init__(self):
        """Initialize DNS packet builder."""
        pass
    
    def build_query(self, domain, record_type='A', transaction_id=1):
        """Build a DNS query packet.
        
        Args:
            domain: Domain name to query
            record_type: DNS record type (A, AAAA, MX, NS, TXT, CNAME)
            transaction_id: Transaction ID for the query
            
        Returns:
            bytes: Raw DNS query packet
            
        Raises:
            ValueError: If record type is not supported
        """
        if record_type not in self.RECORD_TYPES:
            raise ValueError(f"Unsupported record type: {record_type}")
        
        # Build DNS header
        header = self._build_header(transaction_id)
        
        # Build question section
        question = self._build_question(domain, record_type)
        
        # Combine header and question
        packet = header + question
        
        return packet
    
    def _build_header(self, transaction_id):
        """Build DNS header (12 bytes).
        
        DNS Header Format (RFC 1035):
        0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                      ID                       |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |QR|   Opcode  |AA|TC|RD|RA|   Z    |   RCODE   |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                    QDCOUNT                    |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                    ANCOUNT                    |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                    NSCOUNT                    |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                    ARCOUNT                    |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        
        Args:
            transaction_id: Transaction ID for the query
            
        Returns:
            bytes: DNS header (12 bytes)
        """
        # Header fields
        id_field = transaction_id & 0xFFFF
        
        # Flags: QR=0 (query), Opcode=0 (standard query), AA=0, TC=0, RD=1 (recursion desired)
        # RA=0, Z=0 (reserved), RCODE=0
        flags = 0x0100  # Binary: 0000000100000000 (RD=1)
        
        qdcount = 1  # Number of questions
        ancount = 0  # Number of answers
        nscount = 0  # Number of authority records
        arcount = 0  # Number of additional records
        
        # Pack header using big-endian format
        header = struct.pack('!HHHHHH', 
                           id_field, flags, qdcount, ancount, nscount, arcount)
        
        return header
    
    def _build_question(self, domain, record_type):
        """Build DNS question section.
        
        Question Format:
        0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                                               |
        /                     QNAME                     /
        /                                               /
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                     QTYPE                     |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                     QCLASS                    |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        
        Args:
            domain: Domain name to query
            record_type: DNS record type
            
        Returns:
            bytes: DNS question section
        """
        # Encode domain name
        qname = self._encode_domain_name(domain)
        
        # Get record type code
        qtype = self.RECORD_TYPES[record_type]
        
        # Class (always IN for Internet)
        qclass = self.CLASS_IN
        
        # Pack question section
        question = qname + struct.pack('!HH', qtype, qclass)
        
        return question
    
    def _encode_domain_name(self, domain):
        """Encode domain name in DNS format.
        
        DNS domain names are encoded as a sequence of labels, where each label
        is prefixed by its length. The sequence ends with a zero-length label.
        
        Example: "example.com" -> \x07example\x03com\x00
        
        Args:
            domain: Domain name to encode
            
        Returns:
            bytes: Encoded domain name
            
        Raises:
            ValueError: If domain name is invalid
        """
        if not domain or len(domain) > 253:
            raise ValueError("Invalid domain name length")
        
        encoded = b''
        
        # Split domain into labels
        labels = domain.split('.')
        
        for label in labels:
            if not label:
                continue
                
            if len(label) > 63:
                raise ValueError(f"Label too long: {label}")
            
            # Encode label length and label
            encoded += struct.pack('!B', len(label))
            encoded += label.encode('ascii')
        
        # Add terminating zero-length label
        encoded += b'\x00'
        
        return encoded
    
    def build_reverse_query(self, ip_address, transaction_id=1):
        """Build a reverse DNS query (PTR record) for an IP address.
        
        Args:
            ip_address: IP address to reverse lookup
            transaction_id: Transaction ID for the query
            
        Returns:
            bytes: Raw DNS query packet for PTR record
            
        Raises:
            ValueError: If IP address is invalid
        """
        # Convert IP to reverse domain format
        try:
            octets = ip_address.split('.')
            if len(octets) != 4:
                raise ValueError("Invalid IPv4 address")
            
            # Reverse octets and add .in-addr.arpa
            reverse_domain = '.'.join(reversed(octets)) + '.in-addr.arpa'
            
        except Exception:
            raise ValueError(f"Invalid IP address: {ip_address}")
        
        # Build PTR query
        return self.build_query(reverse_domain, 'PTR', transaction_id)
    
    def get_supported_types(self):
        """Get list of supported DNS record types.
        
        Returns:
            list: List of supported record type strings
        """
        return list(self.RECORD_TYPES.keys())