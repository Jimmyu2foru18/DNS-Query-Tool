"""DNS Client - Core DNS query functionality using raw UDP packets."""

import socket
import time
import random
from .packet_builder import DNSPacketBuilder
from .packet_parser import DNSPacketParser
from .cache_manager import CacheManager


class DNSClient:
    """DNS client that sends raw UDP packets to resolve domain names."""
    
    def __init__(self, cache_manager=None):
        """Initialize DNS client.
        
        Args:
            cache_manager: Optional CacheManager instance for caching responses
        """
        self.packet_builder = DNSPacketBuilder()
        self.packet_parser = DNSPacketParser()
        self.cache_manager = cache_manager
    
    def query(self, domain, record_type='A', dns_server='8.8.8.8', dns_port=53, 
              timeout=5, verbose=False):
        """Perform DNS query for a domain.
        
        Args:
            domain: Domain name to query
            record_type: DNS record type (A, AAAA, MX, NS, TXT, CNAME)
            dns_server: DNS server IP address
            dns_port: DNS server port
            timeout: Query timeout in seconds
            verbose: Enable verbose output
            
        Returns:
            dict: Parsed DNS response
            
        Raises:
            Exception: If query fails or times out
        """
        # Check cache first
        cache_key = f"{domain}:{record_type}:{dns_server}"
        if self.cache_manager:
            cached_response = self.cache_manager.get(cache_key)
            if cached_response:
                if verbose:
                    print(f"Cache HIT for {cache_key}")
                return cached_response
            elif verbose:
                print(f"Cache MISS for {cache_key}")
        
        # Generate random transaction ID
        transaction_id = random.randint(1, 65535)
        
        # Build DNS query packet
        query_packet = self.packet_builder.build_query(
            domain=domain,
            record_type=record_type,
            transaction_id=transaction_id
        )
        
        if verbose:
            print(f"Built DNS query packet ({len(query_packet)} bytes)")
            print(f"Transaction ID: {transaction_id}")
        
        # Send UDP packet and receive response
        response_packet = self._send_udp_query(
            query_packet, dns_server, dns_port, timeout, verbose
        )
        
        # Parse DNS response
        response = self.packet_parser.parse_response(
            response_packet, transaction_id, verbose
        )
        
        # Add query information to response
        response['query_name'] = domain
        response['query_type'] = record_type
        response['dns_server'] = dns_server
        
        # Cache the response if cache manager is available
        if self.cache_manager and response['status'] == 'NOERROR':
            # Use minimum TTL from all records for cache expiration
            min_ttl = self._get_minimum_ttl(response)
            if min_ttl > 0:
                self.cache_manager.set(cache_key, response, min_ttl)
                if verbose:
                    print(f"Cached response for {min_ttl} seconds")
        
        return response
    
    def _send_udp_query(self, query_packet, dns_server, dns_port, timeout, verbose):
        """Send UDP query packet and receive response.
        
        Args:
            query_packet: Raw DNS query packet bytes
            dns_server: DNS server IP address
            dns_port: DNS server port
            timeout: Query timeout in seconds
            verbose: Enable verbose output
            
        Returns:
            bytes: Raw DNS response packet
            
        Raises:
            Exception: If query fails or times out
        """
        sock = None
        try:
            # Create UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            
            if verbose:
                print(f"Sending query to {dns_server}:{dns_port}")
            
            # Send query packet
            start_time = time.time()
            sock.sendto(query_packet, (dns_server, dns_port))
            
            # Receive response
            response_packet, addr = sock.recvfrom(4096)
            end_time = time.time()
            
            if verbose:
                response_time = (end_time - start_time) * 1000
                print(f"Received response from {addr} ({len(response_packet)} bytes, {response_time:.1f}ms)")
            
            return response_packet
            
        except socket.timeout:
            raise Exception(f"DNS query timeout after {timeout} seconds")
        except socket.gaierror as e:
            raise Exception(f"DNS server address error: {e}")
        except Exception as e:
            raise Exception(f"DNS query failed: {e}")
        finally:
            if sock:
                sock.close()
    
    def _get_minimum_ttl(self, response):
        """Get minimum TTL from all records in response.
        
        Args:
            response: Parsed DNS response
            
        Returns:
            int: Minimum TTL value
        """
        ttls = []
        
        # Collect TTLs from all sections
        for section in ['answers', 'authority', 'additional']:
            if section in response and response[section]:
                for record in response[section]:
                    if 'ttl' in record:
                        ttls.append(record['ttl'])
        
        return min(ttls) if ttls else 300  # Default 5 minutes if no TTL found
    
    def bulk_query(self, domains, record_type='A', dns_server='8.8.8.8', 
                   dns_port=53, timeout=5, verbose=False):
        """Perform bulk DNS queries for multiple domains.
        
        Args:
            domains: List of domain names to query
            record_type: DNS record type
            dns_server: DNS server IP address
            dns_port: DNS server port
            timeout: Query timeout in seconds
            verbose: Enable verbose output
            
        Returns:
            dict: Dictionary mapping domains to their DNS responses
        """
        results = {}
        
        for domain in domains:
            try:
                if verbose:
                    print(f"Querying {domain}...")
                
                response = self.query(
                    domain=domain,
                    record_type=record_type,
                    dns_server=dns_server,
                    dns_port=dns_port,
                    timeout=timeout,
                    verbose=verbose
                )
                results[domain] = response
                
            except Exception as e:
                if verbose:
                    print(f"Failed to query {domain}: {e}")
                results[domain] = {'error': str(e)}
        
        return results