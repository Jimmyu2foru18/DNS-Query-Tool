#!/usr/bin/env python3
"""
DNS Query Tool - Main CLI Entry Point

A command-line DNS query tool that sends raw UDP packets to resolve domain names.
Similar to 'dig' but with caching and visualization features.
"""

import argparse
import sys
import time
from src.dns_client import DNSClient
from src.cache_manager import CacheManager
from src.visualizer import Visualizer


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='DNS Query Tool - Resolve domain names using raw UDP packets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py example.com
  python main.py example.com -t MX
  python main.py example.com -s 1.1.1.1 --visualize
  python main.py --cache-stats
        """
    )
    
    parser.add_argument('domain', nargs='?', help='Domain name to query')
    parser.add_argument('-t', '--type', default='A', 
                       choices=['A', 'AAAA', 'MX', 'NS', 'TXT', 'CNAME'],
                       help='DNS record type (default: A)')
    parser.add_argument('-s', '--server', default='8.8.8.8',
                       help='DNS server to query (default: 8.8.8.8)')
    parser.add_argument('-p', '--port', type=int, default=53,
                       help='DNS server port (default: 53)')
    parser.add_argument('--timeout', type=int, default=5,
                       help='Query timeout in seconds (default: 5)')
    parser.add_argument('--visualize', action='store_true',
                       help='Show response time visualization')
    parser.add_argument('--cache-stats', action='store_true',
                       help='Display cache statistics')
    parser.add_argument('--clear-cache', action='store_true',
                       help='Clear the DNS cache')
    parser.add_argument('--no-cache', action='store_true',
                       help='Disable caching for this query')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose output')
    
    return parser.parse_args()


def format_response(response, query_time):
    """Format DNS response for display."""
    output = []
    output.append(f"DNS Response:")
    output.append(f"  Query: {response['query_name']} ({response['query_type']})")
    output.append(f"  Status: {response['status']}")
    output.append(f"  Response Time: {query_time:.0f}ms")
    output.append("")
    
    if response['answers']:
        output.append("  Answer Section:")
        for answer in response['answers']:
            output.append(f"    {answer['name']:<20} {answer['ttl']:<6} IN {answer['type']:<6} {answer['data']}")
    
    if response['authority']:
        output.append("")
        output.append("  Authority Section:")
        for auth in response['authority']:
            output.append(f"    {auth['name']:<20} {auth['ttl']:<6} IN {auth['type']:<6} {auth['data']}")
    
    if response['additional']:
        output.append("")
        output.append("  Additional Section:")
        for add in response['additional']:
            output.append(f"    {add['name']:<20} {add['ttl']:<6} IN {add['type']:<6} {add['data']}")
    
    return "\n".join(output)


def main():
    """Main function."""
    args = parse_arguments()
    
    # Initialize components
    cache_manager = CacheManager()
    dns_client = DNSClient(cache_manager=cache_manager if not args.no_cache else None)
    visualizer = Visualizer() if args.visualize else None
    
    try:
        # Handle cache operations
        if args.clear_cache:
            cache_manager.clear_cache()
            print("Cache cleared successfully.")
            return
        
        if args.cache_stats:
            stats = cache_manager.get_stats()
            print("Cache Statistics:")
            print(f"  Total Entries: {stats['total_entries']}")
            print(f"  Cache Hits: {stats['hits']}")
            print(f"  Cache Misses: {stats['misses']}")
            print(f"  Hit Ratio: {stats['hit_ratio']:.2%}")
            print(f"  Memory Usage: {stats['memory_usage']:.2f} KB")
            return
        
        # Validate domain argument
        if not args.domain:
            print("Error: Domain name is required")
            sys.exit(1)
        
        # Perform DNS query
        print(f"Querying {args.domain} ({args.type} record) using DNS server {args.server}:{args.port}")
        print()
        
        start_time = time.time()
        response = dns_client.query(
            domain=args.domain,
            record_type=args.type,
            dns_server=args.server,
            dns_port=args.port,
            timeout=args.timeout,
            verbose=args.verbose
        )
        query_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Display results
        print(format_response(response, query_time))
        
        # Show cache status
        if not args.no_cache:
            cache_key = f"{args.domain}:{args.type}:{args.server}"
            if cache_manager.is_cached(cache_key):
                ttl_remaining = cache_manager.get_ttl(cache_key)
                print(f"\n  Cache: HIT (expires in {ttl_remaining} seconds)")
            else:
                print(f"\n  Cache: MISS (cached for {response.get('ttl', 0)} seconds)")
        
        # Show visualization if requested
        if visualizer:
            visualizer.add_query_time(args.domain, query_time)
            visualizer.show_response_time_chart()
    
    except KeyboardInterrupt:
        print("\nQuery interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()