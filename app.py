from flask import Flask, request, jsonify
import sqlite3
import os

# Init app
app = Flask(__name__)

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

# Original home route
@app.route('/', methods=['GET'])
def home():
    return "<h1>Distant Reading Archive</h1><p>This is a prototype API</p>"

# Test-compatible routes
@app.route('/books', methods=['GET'])
def get_all_books():
    db_path = os.path.join('db', 'books.db')    
    conn = sqlite3.connect(db_path)
    conn.row_factory = dict_factory
    cur = conn.cursor()
    all_books = cur.execute('SELECT * FROM books;').fetchall()
    return jsonify(all_books)

@app.route('/books/<int:book_id>', methods=['GET'])
def get_book_by_id(book_id):
    db_path = os.path.join('db', 'books.db')
    print(f"Looking for book with ID {book_id}, DB path: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = dict_factory
        cur = conn.cursor()
        
        # First check if the database has any records
        all_count = cur.execute('SELECT COUNT(*) as count FROM books;').fetchone()
        print(f"Total books in database: {all_count['count']}")
        
        # Now try to get the specific book
        book = cur.execute('SELECT * FROM books WHERE id=?;', [book_id]).fetchone()
        print(f"Query result: {book}")
        
        if book:
            return jsonify(book)
        else:
            return jsonify({"error": f"Book with ID {book_id} not found"}), 404
    except Exception as e:
        print(f"Database error: {str(e)}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500

@app.route('/books', methods=['POST'])
def create_book():
    if not request.is_json:
        return "<p>The content isn't of type JSON</p>", 400

    content = request.get_json()
    title = content.get('title')
    author = content.get('author')
    published = content.get('published', '')
    first_sentence = content.get('first_sentence', '')

    db_path = os.path.join('db', 'books.db')    
    conn = sqlite3.connect(db_path)
    query = 'INSERT INTO books (title, author, published, first_sentence) VALUES (?, ?, ?, ?);'

    cur = conn.cursor()
    cur.execute(query, (title, author, published, first_sentence))
    conn.commit()
    
    return jsonify(content), 201

# Original API routes can be kept for backward compatibility
@app.route('/api/v2/resources/books/all', methods=['GET'])
def api_all():
    db_path = os.path.join('db', 'books.db')    
    conn = sqlite3.connect(db_path)
    conn.row_factory = dict_factory
    cur = conn.cursor()
    all_books = cur.execute('SELECT * FROM books;').fetchall()
    return jsonify(all_books)

@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404</h1><p>The resource could not be found</p>", 404

@app.route('/api/v2/resources/books', methods=['GET'])
def api_filter():
    query_parameters = request.args

    id = query_parameters.get('id')
    published = query_parameters.get('published')
    author = query_parameters.get('author')

    query = 'SELECT * FROM books WHERE'
    to_filter = []

    if id:
        query += ' id=? AND'
        to_filter.append(id)
    
    if published:
        query += ' published=? AND'
        to_filter.append(published)

    if author:
        query += ' author=? AND'
        to_filter.append(author)

    if not(id or published or author):
        return page_not_found(404)

    query = query[:-4] + ';'

    db_path = os.path.join('db', 'books.db')    
    conn = sqlite3.connect(db_path)
    conn.row_factory = dict_factory
    cur = conn.cursor()

    results = cur.execute(query, to_filter).fetchall()

    return jsonify(results)

@app.route('/api/v2/resources/books', methods=['POST'])
def add_book():
    if not request.is_json:
        return "<p>The content isn't of type JSON</p>", 400

    content = request.get_json()
    title = content.get('title')
    author = content.get('author')
    published = content.get('published', '')
    first_sentence = content.get('first_sentence', '')

    db_path = os.path.join('db', 'books.db')    
    conn = sqlite3.connect(db_path)
    query = 'INSERT INTO books (title, author, published, first_sentence) VALUES (?, ?, ?, ?);'

    cur = conn.cursor()
    cur.execute(query, (title, author, published, first_sentence))
    conn.commit()
    
    return jsonify(content)

# A method that runs the application server.
if __name__ == "__main__":
    # Threaded option to enable multiple instances for multiple user access support
    app.run(host='0.0.0.0', port=5000)
