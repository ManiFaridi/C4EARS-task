import os
import pickle
import datetime
from queue import Queue
import logging
import sqlite3
from functools import wraps
import ssl
import jwt
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

SECRET_KEY = os.environ['secret_key']
LOG_PATH = './logs.txt'
RQ_PERSISTENCE_PATH = './request_queue_backup.pkl'

logging.basicConfig(filename=LOG_PATH,
                    level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

request_queue = Queue()
with open(RQ_PERSISTENCE_PATH, 'wb') as file:
    pickle.dump(request_queue, file)

DB_POOL_SIZE = 5
db_conn_pool = Queue(maxsize=DB_POOL_SIZE)


def create_connection():
    return sqlite3.connect('requests.db')


def init_connection_pool():
    for _ in range(DB_POOL_SIZE):
        db_conn_pool.put(create_connection())


def get_connection():
    return db_conn_pool.get()


def return_connection(conn):
    db_conn_pool.put(conn)


def generate_token(username):
    token = jwt.encode({
        'sub': username,
        'iat':  datetime.datetime.now(datetime.timezone.utc),
        'exp':  datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    }, SECRET_KEY, algorithm='HS256')
    return token


def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            logging.warning('Missing token')
            return jsonify({"error": "Unauthorized, token missing"}), 403

        try:
            token = token.split(" ")[1]
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            logging.warning('Token expired')
            return jsonify({"error": "Token expired"}), 403
        except jwt.InvalidTokenError:
            logging.warning('Invalid token')
            return jsonify({"error": "Invalid token"}), 403

        return f(*args, **kwargs)
    return decorated_function


def init_db():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_text TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            result TEXT
        )
    ''')
    conn.commit()
    conn.close()


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    # this whole section is to be changed (using database and hashed passwords for authentication)
    if username == 'admin' and password == 'password':  # to be changed
        token = generate_token(username)
        logging.info(f'User {username} logged in successfully')
        return jsonify({'token': token}), 200

    logging.warning('Login failed')
    return jsonify({"error": "Invalid credentials"}), 401


@app.route('/submit-request', methods=['POST'])
@token_required
def submit_request():
    user_query = request.json.get('query')
    if not user_query:
        logging.error('Invalid request: no query provided')
        return jsonify({"error": "Invalid request, no query provided"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO requests (request_text) VALUES (?)', (user_query,))
    request_id = cursor.lastrowid
    conn.commit()
    return_connection(conn)

    request_queue.put(request_id)
    with open(RQ_PERSISTENCE_PATH, 'wb') as file:
        pickle.dump(request_queue, file)
    logging.info(f'Request submitted: {request_id}')
    return jsonify({"message": "Request submitted", "request_id": request_id}), 200


@app.route('/fetch-requests', methods=['GET'])
@token_required
def fetch_requests():
    if request_queue.empty():
        logging.info('No pending requests in queue')
        return jsonify({"message": "No pending requests"}), 200

    request_id = request_queue.get()
    with open(RQ_PERSISTENCE_PATH, 'wb') as file:
        pickle.dump(request_queue, file)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, request_text FROM requests WHERE id = ?', (request_id,))
    req = cursor.fetchone()
    return_connection(conn)

    logging.info(f'Fetched request: {request_id}')
    return jsonify({"request_id": req[0], "query": req[1]}), 200


@app.route('/submit-result', methods=['POST'])
@token_required
def submit_result():
    data = request.json
    request_id = data.get('request_id')
    result = data.get('result')

    if not request_id or not result:
        logging.error('Invalid result submission: missing request_id or result')
        return jsonify({"error": "Invalid request, missing request_id or result"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE requests SET status = ?, result = ? WHERE id = ?', ('completed', result, request_id))
    conn.commit()
    return_connection(conn)

    logging.info(f'Result submitted for request ID: {request_id}')
    return jsonify({"message": "Result submitted"}), 200


@app.route('/get-result/<int:request_id>', methods=['GET'])
@token_required
def get_result(request_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT status, result FROM requests WHERE id = ?', (request_id,))
    result = cursor.fetchone()
    return_connection(conn)

    if not result:
        logging.error(f'Request not found: {request_id}')
        return jsonify({"error": "Request not found"}), 404

    logging.info(f'Retrieved result for request ID: {request_id}')
    return jsonify({"status": result[0], "result": result[1]}), 200


@app.route('/get-logs', methods=['GET'])
@token_required
def get_logs():
    logging.info('Log file exported!')
    return send_file(LOG_PATH, as_attachment=True, mimetype='text/plain')


if __name__ == '__main__':
    init_db()
    init_connection_pool()
    
    if os.stat(RQ_PERSISTENCE_PATH).st_size != 0:
        with open(RQ_PERSISTENCE_PATH, 'rb') as file:
            request_queue = pickle.load(file)
        
    context = ssl.SSLContext(ssl.PROTOCOL_TLS)
    context.load_cert_chain('cert.pem', 'key.pem')

    logging.info('Starting Flask app with SSL...')
    app.run(ssl_context=context, debug=True)
    # thank you for the oppurtunity you have given, I hope I did a good job making you satisfied
