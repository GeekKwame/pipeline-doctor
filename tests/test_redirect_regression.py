"""Regression tests for SafeRedirectHandler with real HTTP servers.

These tests use two actual HTTP servers (on different ports) to verify
that redirects work correctly and Authorization headers are stripped
on cross-host redirects.
"""

import base64
import http.server
import json
import socketserver
import threading
import time
import zipfile
from io import BytesIO
from urllib.request import Request, build_opener

import pytest

from pipeline_doctor.github_client import SafeRedirectHandler


# Track requests received by each server
server_a_requests = []
server_b_requests = []


class ServerAHandler(http.server.BaseHTTPRequestHandler):
    """Handler for server A - issues redirects to server B."""
    
    def log_message(self, format, *args):
        """Suppress server logging."""
        pass
    
    def do_GET(self):
        """Handle GET requests with redirects."""
        # Record the request
        server_a_requests.append({
            'path': self.path,
            'headers': dict(self.headers)
        })
        
        # Extract redirect code from path (e.g., /redirect/302)
        path_without_query = self.path.split('?')[0]
        parts = path_without_query.split('/')
        if len(parts) >= 3 and parts[1] == 'redirect':
            code = int(parts[2])
            
            # Determine body type from query parameter
            body_type = 'plain'
            if '?' in self.path:
                query = self.path.split('?')[1]
                if 'body=zip' in query:
                    body_type = 'zip'
            
            # Redirect to server B
            redirect_url = f'http://localhost:{self.server.server_b_port}/logs?body={body_type}'
            self.send_response(code)
            self.send_header('Location', redirect_url)
            self.end_headers()
        else:
            self.send_error(404)


class ServerBHandler(http.server.BaseHTTPRequestHandler):
    """Handler for server B - serves log content."""
    
    def log_message(self, format, *args):
        """Suppress server logging."""
        pass
    
    def do_GET(self):
        """Handle GET requests and serve log content."""
        # Record the request
        server_b_requests.append({
            'path': self.path,
            'headers': dict(self.headers)
        })
        
        # Determine body type from query parameter
        body_type = 'plain'
        if '?' in self.path:
            query = self.path.split('?')[1]
            if 'body=zip' in query:
                body_type = 'zip'
        
        self.send_response(200)
        
        if body_type == 'zip':
            # Create a zip file with log content
            log_content = b"Test log content from zip file"
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('log.txt', log_content)
            
            zip_data = zip_buffer.getvalue()
            self.send_header('Content-Type', 'application/zip')
            self.send_header('Content-Length', str(len(zip_data)))
            self.end_headers()
            self.wfile.write(zip_data)
        else:
            # Plain text log
            log_content = b"Test log content from plain text"
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(log_content)))
            self.end_headers()
            self.wfile.write(log_content)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """HTTP server that handles requests in separate threads."""
    allow_reuse_address = True
    daemon_threads = True


@pytest.fixture(scope='module')
def http_servers():
    """Start two HTTP servers for testing redirects."""
    global server_a_requests, server_b_requests
    
    # Find available ports
    server_a_port = 9876
    server_b_port = 9877
    
    # Create servers
    server_a = ThreadedHTTPServer(('localhost', server_a_port), ServerAHandler)
    server_b = ThreadedHTTPServer(('localhost', server_b_port), ServerBHandler)
    
    # Store server B port in server A for redirect URLs
    server_a.server_b_port = server_b_port
    
    # Start servers in background threads
    thread_a = threading.Thread(target=server_a.serve_forever, daemon=True)
    thread_b = threading.Thread(target=server_b.serve_forever, daemon=True)
    thread_a.start()
    thread_b.start()
    
    # Wait for servers to start
    time.sleep(0.1)
    
    yield {
        'server_a_port': server_a_port,
        'server_b_port': server_b_port
    }
    
    # Cleanup
    server_a.shutdown()
    server_b.shutdown()


@pytest.fixture(autouse=True)
def clear_request_logs():
    """Clear request logs before each test."""
    global server_a_requests, server_b_requests
    server_a_requests = []
    server_b_requests = []


@pytest.mark.parametrize('redirect_code', [301, 302, 303, 307, 308])
def test_redirect_plain_text_strips_auth_header(http_servers, redirect_code):
    """Test that redirects strip Authorization header with plain text response."""
    server_a_port = http_servers['server_a_port']
    
    # Create request with Authorization header
    url = f'http://localhost:{server_a_port}/redirect/{redirect_code}?body=plain'
    request = Request(url)
    request.add_header('Authorization', 'Bearer ghp_test_token_12345')
    
    # Create opener with SafeRedirectHandler
    original_host = f'localhost:{server_a_port}'
    handler = SafeRedirectHandler(original_host, 'ghp_test_token_12345')
    opener = build_opener(handler)
    
    # Make request
    with opener.open(request) as response:
        content = response.read()
    
    # Verify we got the log content
    assert content == b"Test log content from plain text"
    
    # Verify server A received the Authorization header
    assert len(server_a_requests) == 1
    assert 'Authorization' in server_a_requests[0]['headers']
    assert server_a_requests[0]['headers']['Authorization'] == 'Bearer ghp_test_token_12345'
    
    # Verify server B did NOT receive the Authorization header (cross-host redirect)
    assert len(server_b_requests) == 1
    assert 'Authorization' not in server_b_requests[0]['headers']
    
    # Verify request counting is correct (2 requests: initial + redirect)
    # This is implicitly tested by checking both server logs


@pytest.mark.parametrize('redirect_code', [301, 302, 303, 307, 308])
def test_redirect_zip_strips_auth_header(http_servers, redirect_code):
    """Test that redirects strip Authorization header with zip response."""
    server_a_port = http_servers['server_a_port']
    
    # Create request with Authorization header
    url = f'http://localhost:{server_a_port}/redirect/{redirect_code}?body=zip'
    request = Request(url)
    request.add_header('Authorization', 'Bearer ghp_test_token_99999')
    
    # Create opener with SafeRedirectHandler
    original_host = f'localhost:{server_a_port}'
    handler = SafeRedirectHandler(original_host, 'ghp_test_token_99999')
    opener = build_opener(handler)
    
    # Make request
    with opener.open(request) as response:
        zip_data = response.read()
    
    # Verify we got a zip file and can extract content
    with zipfile.ZipFile(BytesIO(zip_data)) as zf:
        names = zf.namelist()
        assert len(names) == 1
        with zf.open(names[0]) as f:
            content = f.read()
            assert content == b"Test log content from zip file"
    
    # Verify server A received the Authorization header
    assert len(server_a_requests) == 1
    assert 'Authorization' in server_a_requests[0]['headers']
    assert server_a_requests[0]['headers']['Authorization'] == 'Bearer ghp_test_token_99999'
    
    # Verify server B did NOT receive the Authorization header (cross-host redirect)
    assert len(server_b_requests) == 1
    assert 'Authorization' not in server_b_requests[0]['headers']


def test_redirect_same_host_keeps_auth_header(http_servers):
    """Test that same-host redirects preserve Authorization header."""
    # Start a temporary server on a different port
    temp_port = 9878
    
    # Create a custom handler that redirects to the same host
    class SameHostServerHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass
        
        def do_GET(self):
            if self.path == '/first':
                # Record first request
                server_a_requests.append({
                    'path': self.path,
                    'headers': dict(self.headers)
                })
                # Redirect to same host
                self.send_response(302)
                self.send_header('Location', f'http://localhost:{temp_port}/second')
                self.end_headers()
            elif self.path == '/second':
                # Record second request
                server_a_requests.append({
                    'path': self.path,
                    'headers': dict(self.headers)
                })
                # Serve content
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Final content")
            else:
                self.send_error(404)
    
    temp_server = ThreadedHTTPServer(('localhost', temp_port), SameHostServerHandler)
    temp_thread = threading.Thread(target=temp_server.serve_forever, daemon=True)
    temp_thread.start()
    time.sleep(0.1)
    
    try:
        # Create request with Authorization header
        url = f'http://localhost:{temp_port}/first'
        request = Request(url)
        request.add_header('Authorization', 'Bearer ghp_same_host_token')
        
        # Create opener with SafeRedirectHandler
        original_host = f'localhost:{temp_port}'
        handler = SafeRedirectHandler(original_host, 'ghp_same_host_token')
        opener = build_opener(handler)
        
        # Make request
        with opener.open(request) as response:
            content = response.read()
        
        # Verify we got the final content
        assert content == b"Final content"
        
        # Verify both requests received the Authorization header (same host)
        assert len(server_a_requests) == 2
        assert 'Authorization' in server_a_requests[0]['headers']
        assert 'Authorization' in server_a_requests[1]['headers']
    finally:
        temp_server.shutdown()
