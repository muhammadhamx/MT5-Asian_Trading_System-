import time
import json
import logging
from django.utils.deprecation import MiddlewareMixin

# Configure logging
logger = logging.getLogger('api_requests')

class APIRequestLoggingMiddleware(MiddlewareMixin):
    """Middleware to log all API requests and responses"""
    
    def process_request(self, request):
        """Process the request"""
        # Store the start time
        request.start_time = time.time()
        
        # Log the request
        if request.path.startswith('/api/'):
            method = request.method
            path = request.path
            query_params = dict(request.GET.items())
            
            # Try to get request body for POST/PUT requests
            body = None
            if method in ['POST', 'PUT', 'PATCH'] and hasattr(request, 'body'):
                try:
                    body = json.loads(request.body.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    body = '<binary data or invalid JSON>'
            
            # Log the request details
            logger.info(f"API Request: {method} {path}")
            logger.info(f"Query Params: {query_params}")
            if body:
                logger.info(f"Request Body: {body}")
        
        return None
    
    def process_response(self, request, response):
        """Process the response"""
        if hasattr(request, 'start_time') and request.path.startswith('/api/'):
            # Calculate request duration
            duration = time.time() - request.start_time
            
            # Get response status and content
            status_code = response.status_code
            
            # Try to get response content based on content type
            content = None
            content_type = response.get('Content-Type', '')

            if hasattr(response, 'content') and 'application/json' in content_type:
                try:
                    content = json.loads(response.content.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    content = '<invalid JSON>'
            elif hasattr(response, 'content') and content_type.startswith('text/'):
                try:
                    content = response.content.decode('utf-8')[:500]  # Limit text content
                except UnicodeDecodeError:
                    content = '<text encoding error>'
            elif hasattr(response, 'content'):
                content = f'<binary data: {content_type}, {len(response.content)} bytes>'

            # Log the response details
            logger.info(f"API Response: {request.method} {request.path} - Status: {status_code} - Duration: {duration:.3f}s")
            if content and content != f'<binary data: {content_type}, {len(response.content)} bytes>':
                logger.info(f"Response Content: {content}")
            
            # Add a separator for better readability
            logger.info("-" * 80)
        
        return response