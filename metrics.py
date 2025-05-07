# metrics.py
from prometheus_client import Counter, Histogram, Gauge, Summary, generate_latest, CONTENT_TYPE_LATEST
import time

# Define metrics
REQUESTS = Counter('books_api_requests_total', 'Total number of requests to the Books API', ['method', 'endpoint', 'status'])
IN_PROGRESS = Gauge('books_api_requests_in_progress', 'Number of requests in progress')
REQUEST_TIME = Summary('books_api_request_duration_seconds', 'Time spent processing request')
EXCEPTIONS = Counter('books_api_exceptions_total', 'Exceptions caught during request processing')
DB_OPERATIONS = Counter('books_api_db_operations_total', 'Total database operations', ['operation'])
BOOKS_COUNT = Gauge('books_api_books_count', 'Number of books in the database')

# Function to update metrics on API request
def before_request():
    IN_PROGRESS.inc()
    request.start_time = time.time()

def after_request(response):
    IN_PROGRESS.dec()
    resp_time = time.time() - request.start_time
    REQUEST_TIME.observe(resp_time)
    REQUESTS.labels(request.method, request.endpoint, response.status_code).inc()
    return response

def record_exception():
    EXCEPTIONS.inc()

def update_books_count(count):
    BOOKS_COUNT.set(count)

def record_db_operation(operation):
    DB_OPERATIONS.labels(operation).inc()
