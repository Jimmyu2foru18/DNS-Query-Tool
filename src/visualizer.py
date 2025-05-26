"""Visualizer - Provides visualization features for DNS queries and cache statistics."""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from collections import defaultdict, deque
import numpy as np


class Visualizer:
    """Handles visualization of DNS query data and cache statistics."""
    
    def __init__(self, max_history=100):
        """Initialize visualizer.
        
        Args:
            max_history: Maximum number of query records to keep in history
        """
        self.max_history = max_history
        
        # Query history: list of (timestamp, domain, response_time, cache_hit)
        self.query_history = deque(maxlen=max_history)
        
        # Response time history by domain
        self.domain_response_times = defaultdict(lambda: deque(maxlen=50))
        
        # Cache statistics history
        self.cache_stats_history = deque(maxlen=max_history)
        
        # Configure matplotlib for better appearance
        plt.style.use('default')
        plt.rcParams['figure.figsize'] = (12, 8)
        plt.rcParams['font.size'] = 10
    
    def add_query_time(self, domain, response_time, cache_hit=False):
        """Add a query response time to the history.
        
        Args:
            domain: Domain name that was queried
            response_time: Response time in milliseconds
            cache_hit: Whether this was a cache hit
        """
        timestamp = datetime.now()
        
        # Add to general history
        self.query_history.append({
            'timestamp': timestamp,
            'domain': domain,
            'response_time': response_time,
            'cache_hit': cache_hit
        })
        
        # Add to domain-specific history
        self.domain_response_times[domain].append({
            'timestamp': timestamp,
            'response_time': response_time,
            'cache_hit': cache_hit
        })
    
    def add_cache_stats(self, stats):
        """Add cache statistics to history.
        
        Args:
            stats: Cache statistics dictionary
        """
        timestamp = datetime.now()
        stats_with_time = stats.copy()
        stats_with_time['timestamp'] = timestamp
        
        self.cache_stats_history.append(stats_with_time)
    
    def show_response_time_chart(self, domain=None, show_cache_hits=True):
        """Show response time chart.
        
        Args:
            domain: Specific domain to show (None for all domains)
            show_cache_hits: Whether to highlight cache hits
        """
        if not self.query_history:
            print("No query data available for visualization")
            return
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        # Filter data by domain if specified
        if domain:
            data = [q for q in self.query_history if q['domain'] == domain]
            title_suffix = f" for {domain}"
        else:
            data = list(self.query_history)
            title_suffix = " (All Domains)"
        
        if not data:
            print(f"No data available for domain: {domain}")
            return
        
        # Extract data for plotting
        timestamps = [q['timestamp'] for q in data]
        response_times = [q['response_time'] for q in data]
        cache_hits = [q['cache_hit'] for q in data]
        
        # Plot 1: Response time over time
        ax1.set_title(f"DNS Query Response Times{title_suffix}")
        
        if show_cache_hits:
            # Separate cache hits and misses
            hit_times = [timestamps[i] for i, hit in enumerate(cache_hits) if hit]
            hit_response_times = [response_times[i] for i, hit in enumerate(cache_hits) if hit]
            miss_times = [timestamps[i] for i, hit in enumerate(cache_hits) if not hit]
            miss_response_times = [response_times[i] for i, hit in enumerate(cache_hits) if not hit]
            
            if hit_times:
                ax1.scatter(hit_times, hit_response_times, color='green', alpha=0.7, 
                           label='Cache Hits', s=50)
            if miss_times:
                ax1.scatter(miss_times, miss_response_times, color='red', alpha=0.7, 
                           label='Cache Misses', s=50)
        else:
            ax1.plot(timestamps, response_times, 'bo-', alpha=0.7, markersize=4)
        
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Response Time (ms)')
        ax1.grid(True, alpha=0.3)
        if show_cache_hits:
            ax1.legend()
        
        # Format x-axis
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
        
        # Plot 2: Response time distribution
        ax2.set_title(f"Response Time Distribution{title_suffix}")
        ax2.hist(response_times, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
        ax2.set_xlabel('Response Time (ms)')
        ax2.set_ylabel('Frequency')
        ax2.grid(True, alpha=0.3)
        
        # Add statistics text
        avg_time = np.mean(response_times)
        median_time = np.median(response_times)
        min_time = np.min(response_times)
        max_time = np.max(response_times)
        
        stats_text = f"Avg: {avg_time:.1f}ms\nMedian: {median_time:.1f}ms\nMin: {min_time:.1f}ms\nMax: {max_time:.1f}ms"
        ax2.text(0.02, 0.98, stats_text, transform=ax2.transAxes, 
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        plt.tight_layout()
        plt.show()
    
    def show_cache_performance_chart(self):
        """Show cache performance over time."""
        if not self.cache_stats_history:
            print("No cache statistics available for visualization")
            return
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        
        # Extract data
        timestamps = [stats['timestamp'] for stats in self.cache_stats_history]
        hit_ratios = [stats['hit_ratio'] for stats in self.cache_stats_history]
        total_entries = [stats['total_entries'] for stats in self.cache_stats_history]
        memory_usage = [stats['memory_usage'] for stats in self.cache_stats_history]
        hits = [stats['hits'] for stats in self.cache_stats_history]
        misses = [stats['misses'] for stats in self.cache_stats_history]
        
        # Plot 1: Hit ratio over time
        ax1.set_title('Cache Hit Ratio Over Time')
        ax1.plot(timestamps, [ratio * 100 for ratio in hit_ratios], 'g-', linewidth=2)
        ax1.set_ylabel('Hit Ratio (%)')
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim(0, 100)
        
        # Plot 2: Cache size over time
        ax2.set_title('Cache Size Over Time')
        ax2.plot(timestamps, total_entries, 'b-', linewidth=2)
        ax2.set_ylabel('Number of Entries')
        ax2.grid(True, alpha=0.3)
        
        # Plot 3: Memory usage over time
        ax3.set_title('Cache Memory Usage Over Time')
        ax3.plot(timestamps, memory_usage, 'r-', linewidth=2)
        ax3.set_xlabel('Time')
        ax3.set_ylabel('Memory Usage (KB)')
        ax3.grid(True, alpha=0.3)
        
        # Plot 4: Hits vs Misses
        ax4.set_title('Cache Hits vs Misses')
        if hits and misses:
            latest_hits = hits[-1] if hits else 0
            latest_misses = misses[-1] if misses else 0
            
            if latest_hits + latest_misses > 0:
                labels = ['Hits', 'Misses']
                sizes = [latest_hits, latest_misses]
                colors = ['green', 'red']
                ax4.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        
        # Format x-axis for time plots
        for ax in [ax1, ax2, ax3]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        plt.show()
    
    def show_domain_comparison_chart(self, top_n=10):
        """Show comparison of response times across domains.
        
        Args:
            top_n: Number of top domains to show
        """
        if not self.domain_response_times:
            print("No domain-specific data available for visualization")
            return
        
        # Calculate average response times per domain
        domain_stats = {}
        for domain, queries in self.domain_response_times.items():
            response_times = [q['response_time'] for q in queries if not q['cache_hit']]
            if response_times:
                domain_stats[domain] = {
                    'avg_time': np.mean(response_times),
                    'query_count': len(queries),
                    'cache_hit_rate': sum(1 for q in queries if q['cache_hit']) / len(queries)
                }
        
        if not domain_stats:
            print("No non-cached query data available for comparison")
            return
        
        # Sort by average response time and take top N
        sorted_domains = sorted(domain_stats.items(), 
                              key=lambda x: x[1]['avg_time'], reverse=True)[:top_n]
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        domains = [item[0] for item in sorted_domains]
        avg_times = [item[1]['avg_time'] for item in sorted_domains]
        cache_hit_rates = [item[1]['cache_hit_rate'] * 100 for item in sorted_domains]
        
        # Plot 1: Average response times
        ax1.set_title(f'Average Response Times (Top {len(domains)} Domains)')
        bars1 = ax1.barh(domains, avg_times, color='skyblue')
        ax1.set_xlabel('Average Response Time (ms)')
        ax1.grid(True, alpha=0.3, axis='x')
        
        # Add value labels on bars
        for i, bar in enumerate(bars1):
            width = bar.get_width()
            ax1.text(width + max(avg_times) * 0.01, bar.get_y() + bar.get_height()/2, 
                    f'{width:.1f}ms', ha='left', va='center')
        
        # Plot 2: Cache hit rates
        ax2.set_title(f'Cache Hit Rates (Top {len(domains)} Domains)')
        bars2 = ax2.barh(domains, cache_hit_rates, color='lightgreen')
        ax2.set_xlabel('Cache Hit Rate (%)')
        ax2.grid(True, alpha=0.3, axis='x')
        ax2.set_xlim(0, 100)
        
        # Add value labels on bars
        for i, bar in enumerate(bars2):
            width = bar.get_width()
            ax2.text(width + 1, bar.get_y() + bar.get_height()/2, 
                    f'{width:.1f}%', ha='left', va='center')
        
        plt.tight_layout()
        plt.show()
    
    def export_data(self, filename):
        """Export visualization data to CSV file.
        
        Args:
            filename: Output CSV filename
        """
        import csv
        
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['timestamp', 'domain', 'response_time', 'cache_hit']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for query in self.query_history:
                writer.writerow({
                    'timestamp': query['timestamp'].isoformat(),
                    'domain': query['domain'],
                    'response_time': query['response_time'],
                    'cache_hit': query['cache_hit']
                })
        
        print(f"Query data exported to {filename}")
    
    def get_summary_stats(self):
        """Get summary statistics for all queries.
        
        Returns:
            dict: Summary statistics
        """
        if not self.query_history:
            return {}
        
        response_times = [q['response_time'] for q in self.query_history]
        cache_hits = sum(1 for q in self.query_history if q['cache_hit'])
        total_queries = len(self.query_history)
        unique_domains = len(set(q['domain'] for q in self.query_history))
        
        return {
            'total_queries': total_queries,
            'unique_domains': unique_domains,
            'cache_hit_rate': cache_hits / total_queries if total_queries > 0 else 0,
            'avg_response_time': np.mean(response_times),
            'median_response_time': np.median(response_times),
            'min_response_time': np.min(response_times),
            'max_response_time': np.max(response_times),
            'std_response_time': np.std(response_times)
        }