# DNS Query Tool

A powerful command-line DNS query tool similar to `dig` that resolves domain names by sending raw DNS packets over UDP protocol. Features include response caching, visualization, and support for multiple DNS record types.

## Features

- **Raw DNS Queries**: Send UDP packets directly to DNS servers
- **Multiple Record Types**: Support for A, AAAA, MX, NS, TXT, CNAME records
- **Response Caching**: TTL-based caching for improved performance
- **Visualization**: Query response time graphs and cache statistics
- **Custom DNS Servers**: Query any DNS server of your choice
- **Detailed Output**: DNS response information

## Installation

1. Clone or download this repository
2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Basic Usage
```bash
python main.py example.com
```

### Advanced Usage
```bash
python main.py example.com -t MX

python main.py example.com -s 1.1.1.1

python main.py example.com --visualize

python main.py --cache-stats

python main.py --clear-cache
```

### Command Line Options

- `-t, --type`: DNS record type (A, AAAA, MX, NS, TXT, CNAME) [default: A]
- `-s, --server`: DNS server to query [default: 8.8.8.8]
- `-p, --port`: DNS server port [default: 53]
- `--timeout`: Query timeout in seconds [default: 5]
- `--visualize`: Show response time visualization
- `--cache-stats`: Display cache statistics
- `--clear-cache`: Clear the DNS cache
- `--no-cache`: Disable caching for this query
- `-v, --verbose`: Enable verbose output

## Project Structure

```
DNS Query Tool/
├── src/
│   ├── __init__.py
│   ├── dns_client.py    
│   ├── packet_builder.py 
│   ├── packet_parser.py  
│   ├── cache_manager.py  
│   └── visualizer.py   
├── tests/
│   ├── __init__.py
│   ├── test_dns_client.py
│   ├── test_packet_builder.py
│   ├── test_packet_parser.py
│   └── test_cache_manager.py
├── examples/
│   └── sample_queries.py
├── requirements.txt
├── main.py 
├── README.md
└── project_proposal.md
```

## Examples

### Query A Record
```bash
$ python main.py google.com
Querying google.com (A record) using DNS server 8.8.8.8:53

DNS Response:
  Query: google.com (A)
  Status: NOERROR
  Response Time: 23ms
  
  Answer Section:
    google.com.    300    IN    A    142.250.191.14
    google.com.    300    IN    A    142.250.191.46
  
  Cache: MISS (cached for 300 seconds)
```

### Query MX Record
```bash
$ python main.py google.com -t MX
Querying google.com (MX record) using DNS server 8.8.8.8:53

DNS Response:
  Query: google.com (MX)
  Status: NOERROR
  Response Time: 31ms
  
  Answer Section:
    google.com.    3600   IN    MX    10 smtp.google.com.
    google.com.    3600   IN    MX    20 smtp2.google.com.
  
  Cache: MISS (cached for 3600 seconds)
```

## Technical Details

### DNS Packet Structure
The tool constructs raw DNS packets following RFC 1035 specifications:
- Header (12 bytes): ID, flags, question count, answer count, etc.
- Question Section: Domain name, query type, query class
- Answer Section: Resource records in response

### Caching System
- **Storage**: In-memory dictionary with TTL tracking
- **Key Format**: `{domain}:{record_type}:{dns_server}`
- **Expiration**: Automatic cleanup based on DNS record TTL
- **Statistics**: Hit/miss ratios and cache size monitoring

### Visualization Features
- Response time trends over multiple queries
- Cache hit/miss ratio charts
- DNS server performance comparison

## Testing

Run the test suite:
```bash
pytest tests/ -v
```

Run with coverage:
```bash
pytest tests/ --cov=src --cov-report=html
```

## Dependencies

- Python
- matplotlib
- pytest
- No external DNS libraries

## Troubleshooting

### Common Issues

1. **Permission Denied**: On some systems, raw socket access may require elevated privileges
2. **Timeout Errors**: Increase timeout value or try different DNS servers
3. **Invalid Responses**: Some DNS servers may have non-standard implementations

### Debug Mode
Enable verbose output for debugging:
```bash
python main.py example.com -v
```

## Roadmap

- [ ] Support for DNS over HTTPS (DoH)
- [ ] IPv6 support
- [ ] DNSSEC validation
- [ ] Configuration file support
- [ ] Export results to JSON/CSV
- [ ] Web interface

---
