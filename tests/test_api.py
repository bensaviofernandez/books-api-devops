import pytest
import json
import sys
import os

# Add the parent directory to path so we can import the app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_get_all_books(client):
    response = client.get('/books')
    assert response.status_code == 200
    books = json.loads(response.data)
    assert isinstance(books, list)
    assert len(books) > 0

def test_get_book_by_id(client):
    # First book should exist
    response = client.get('/books/1')
    assert response.status_code == 200
    book = json.loads(response.data)
    assert book['id'] == 1
    
    # Non-existent book should return 404
    response = client.get('/books/999')
    assert response.status_code == 404

def test_create_book(client):
    new_book = {
        'title': 'Test Book',
        'author': 'Test Author',
        'read': False
    }
    response = client.post('/books', 
                           data=json.dumps(new_book),
                           content_type='application/json')
    assert response.status_code == 201
    created_book = json.loads(response.data)
    assert created_book['title'] == 'Test Book'
