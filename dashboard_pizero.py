#!/usr/bin/env python3
"""
Lightweight DNS Analytics Dashboard for Pi Zero 2W
Optimized for minimal memory and CPU usage
"""

from flask import Flask, render_template, jsonify
import sqlite3
import yaml
from datetime import datetime, timedelta
from functools import lru_cache
import time

app = Flask(__name__)

# Pi Zero 2W Optimizations
DB_PATH = 'data/dns_logs.db'
CACHE_TIMEOUT = 10  # Cache results for 10 seconds
MAX_RECENT_QUERIES = 50  # Show only 50 recent queries (vs 100)
STATS_INTERVAL = 3600  # Update stats hourly

# Simple in-memory cache
cache = {}
cache_times = {}

def get_db():
    """Get database connection with optimizations"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Read-only optimizations
    conn.execute("PRAGMA query_only = ON")
    conn.execute("PRAGMA cache_size = -1000")  # 1MB cache
    return conn

def cached_query(key, ttl=CACHE_TIMEOUT):
    """Simple cache decorator"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            now = time.time()
            if key in cache and (now - cache_times.get(key, 0)) < ttl:
                return cache[key]
            
            result = func(*args, **kwargs)
            cache[key] = result
            cache_times[key] = now
            return result
        return wrapper
    return decorator

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index_pizero.html')

@app.route('/api/stats')
@cached_query('stats', ttl=30)  # Cache for 30 seconds
def get_stats():
    """Get summary statistics - cached"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Last 24 hours stats
    yesterday = int(time.time()) - 86400
    
    # Total queries
    total = cursor.execute(
        "SELECT COUNT(*) FROM dns_queries WHERE timestamp > ?",
        (yesterday,)
    ).fetchone()[0]
    
    # Blocked queries
    blocked = cursor.execute(
        "SELECT COUNT(*) FROM dns_queries WHERE blocked = 1 AND timestamp > ?",
        (yesterday,)
    ).fetchone()[0]
    
    # Unique domains
    unique_domains = cursor.execute(
        "SELECT COUNT(DISTINCT domain) FROM dns_queries WHERE timestamp > ?",
        (yesterday,)
    ).fetchone()[0]
    
    # Unique clients
    unique_clients = cursor.execute(
        "SELECT COUNT(DISTINCT client_ip) FROM dns_queries "
        "WHERE client_ip IS NOT NULL AND timestamp > ?",
        (yesterday,)
    ).fetchone()[0]
    
    conn.close()
    
    blocked_pct = (blocked / total * 100) if total > 0 else 0
    
    return jsonify({
        'total_queries': total,
        'blocked_queries': blocked,
        'blocked_percentage': round(blocked_pct, 1),
        'unique_domains': unique_domains,
        'unique_clients': unique_clients
    })

@app.route('/api/top-domains')
@cached_query('top_domains', ttl=60)  # Cache for 1 minute
def get_top_domains():
    """Top 10 queried domains - cached"""
    conn = get_db()
    cursor = conn.cursor()
    
    yesterday = int(time.time()) - 86400
    
    rows = cursor.execute("""
        SELECT domain, COUNT(*) as count
        FROM dns_queries
        WHERE timestamp > ? AND blocked = 0
        GROUP BY domain
        ORDER BY count DESC
        LIMIT 10
    """, (yesterday,)).fetchall()
    
    conn.close()
    
    return jsonify([{
        'domain': row['domain'],
        'count': row['count']
    } for row in rows])

@app.route('/api/top-blocked')
@cached_query('top_blocked', ttl=60)
def get_top_blocked():
    """Top 10 blocked domains - cached"""
    conn = get_db()
    cursor = conn.cursor()
    
    yesterday = int(time.time()) - 86400
    
    rows = cursor.execute("""
        SELECT domain, COUNT(*) as count
        FROM dns_queries
        WHERE timestamp > ? AND blocked = 1
        GROUP BY domain
        ORDER BY count DESC
        LIMIT 10
    """, (yesterday,)).fetchall()
    
    conn.close()
    
    return jsonify([{
        'domain': row['domain'],
        'count': row['count']
    } for row in rows])

@app.route('/api/timeline')
@cached_query('timeline', ttl=60)
def get_timeline():
    """Hourly query timeline - cached"""
    conn = get_db()
    cursor = conn.cursor()
    
    yesterday = int(time.time()) - 86400
    
    # Get hourly buckets
    rows = cursor.execute("""
        SELECT 
            (timestamp / 3600) * 3600 as hour,
            COUNT(*) as total,
            SUM(blocked) as blocked
        FROM dns_queries
        WHERE timestamp > ?
        GROUP BY hour
        ORDER BY hour
    """, (yesterday,)).fetchall()
    
    conn.close()
    
    return jsonify([{
        'timestamp': row['hour'],
        'total': row['total'],
        'blocked': row['blocked']
    } for row in rows])

@app.route('/api/clients')
@cached_query('clients', ttl=60)
def get_clients():
    """Top clients by query count - cached"""
    conn = get_db()
    cursor = conn.cursor()
    
    yesterday = int(time.time()) - 86400
    
    rows = cursor.execute("""
        SELECT client_ip, COUNT(*) as count
        FROM dns_queries
        WHERE client_ip IS NOT NULL AND timestamp > ?
        GROUP BY client_ip
        ORDER BY count DESC
        LIMIT 10
    """, (yesterday,)).fetchall()
    
    conn.close()
    
    return jsonify([{
        'client': row['client_ip'],
        'queries': row['count']
    } for row in rows])

@app.route('/api/recent')
def get_recent_queries():
    """Recent queries - limited to 50 for performance"""
    conn = get_db()
    cursor = conn.cursor()
    
    rows = cursor.execute("""
        SELECT timestamp, client_ip, domain, query_type, status, blocked
        FROM dns_queries
        ORDER BY timestamp DESC
        LIMIT ?
    """, (MAX_RECENT_QUERIES,)).fetchall()
    
    conn.close()
    
    return jsonify([{
        'timestamp': row['timestamp'],
        'client': row['client_ip'],
        'domain': row['domain'],
        'type': row['query_type'],
        'status': row['status'],
        'blocked': bool(row['blocked'])
    } for row in rows])

@app.route('/api/query-types')
@cached_query('query_types', ttl=120)
def get_query_types():
    """Query type distribution - cached"""
    conn = get_db()
    cursor = conn.cursor()
    
    yesterday = int(time.time()) - 86400
    
    rows = cursor.execute("""
        SELECT query_type, COUNT(*) as count
        FROM dns_queries
        WHERE query_type IS NOT NULL AND timestamp > ?
        GROUP BY query_type
        ORDER BY count DESC
    """, (yesterday,)).fetchall()
    
    conn.close()
    
    return jsonify([{
        'type': row['query_type'],
        'count': row['count']
    } for row in rows])

@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db()
        conn.execute("SELECT 1")
        conn.close()
        return jsonify({'status': 'healthy', 'timestamp': int(time.time())})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Pi-hole Dashboard - Pi Zero 2W Edition")
    print("=" * 60)
    print(f"💾 Database: {DB_PATH}")
    print(f"⚡ Cache: {CACHE_TIMEOUT}s TTL")
    print(f"📊 Recent queries: {MAX_RECENT_QUERIES}")
    print("🌐 Starting server on http://0.0.0.0:5000")
    print("=" * 60)
    
    # Run with minimal threads for Pi Zero 2W
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True,
        processes=1  # Single process for low memory
    )
