from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import random
import os
from datetime import datetime, timedelta

class EventHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse URL and query parameters
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        
        # Get page and limit from query parameters (with defaults)
        page = int(query_params.get('page', [1])[0])
        limit = int(query_params.get('limit', [10])[0])
        
        # Limit the maximum number of items per page
        limit = min(limit, 100)
        
        # Generate random events
        events = self.generate_random_events(page, limit)
        
        # Set response headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        # SECURITY FIX: Restrict CORS to specific origins (not wildcard)
        # For production, set ALLOWED_ORIGINS environment variable
        allowed_origins = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:8080').split(',')
        origin = self.headers.get('Origin', '')
        if origin in allowed_origins:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Credentials', 'true')
        # SECURITY: Do not send CORS headers if origin not allowed (prevents wildcard abuse)
        self.end_headers()
        
        # Send response
        response = {
            'events': events
        }
        
        self.wfile.write(json.dumps(response, indent=2).encode())
    
    def generate_random_events(self, page, limit):
        event_types = ['Conference', 'Workshop', 'Meetup', 'Webinar', 'Seminar', 'Training']
        locations = ['New York', 'San Francisco', 'London', 'Tokyo', 'Berlin', 'Sydney']
        
        events = []
        for i in range(limit):
            event_id = (page - 1) * limit + i + 1
            random_date = datetime.now() + timedelta(days=random.randint(1, 365))
            
            event = {
                'id': event_id,
                'title': f'{random.choice(event_types)} Event {event_id}',
                'description': f'This is a description for event {event_id}',
                'date': random_date.strftime('%Y-%m-%d'),
                'time': f'{random.randint(9, 17):02d}:{random.randint(0, 5)*10:02d}',
                'location': random.choice(locations),
                'capacity': random.randint(20, 500),
                'price': round(random.uniform(0, 299.99), 2),
                'host': '193.234.433.323',
            }
            events.append(event)
        
        return events

def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, EventHandler)
    print(f'Server running on http://localhost:{port}')
    print(f'Try: http://localhost:{port}?page=1&limit=5')
    httpd.serve_forever()

if __name__ == '__main__':
    run_server()