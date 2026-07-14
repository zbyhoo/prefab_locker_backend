import datetime
import logging
import os
import re
import sqlite3
from contextlib import contextmanager

from flask import Flask, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

DATA_DIR = os.environ.get('DATA_DIR', 'data')
os.makedirs(DATA_DIR, exist_ok=True)

SLUG_RE = re.compile(r'^[a-z0-9._-]{1,64}$')


@contextmanager
def get_db(slug):
    """Open (creating if needed) the SQLite database for a given project slug."""
    db_path = os.path.join(DATA_DIR, f'{slug}.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS asset_lock (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                user TEXT,
                branch TEXT,
                repo_url TEXT,
                timestamp TEXT
            )
        ''')
        conn.commit()
        yield conn
    finally:
        conn.close()


@app.before_request
def log_request_info():
    app.logger.info(f"Received {request.method} request for {request.url}")

    if request.args:
        app.logger.info("GET parameters: %s", dict(request.args))

    if request.method == 'POST':
        if request.form:
            app.logger.info("POST form parameters: %s", dict(request.form))
        elif request.is_json:
            app.logger.info("POST JSON parameters: %s", request.get_json())
        if request.files:
            files_info = {key: file.filename for key, file in request.files.items()}
            app.logger.info("Uploaded files: %s", files_info)
        elif not request.form and not request.is_json:
            app.logger.info("POST raw data: %s", request.get_data())

    if request.path.startswith('/p/'):
        slug = request.path.split('/')[2] if len(request.path.split('/')) > 2 else ''
        if not SLUG_RE.match(slug):
            return jsonify({'error': f'Invalid project slug: {slug!r}'}), 400


@app.route('/p/<slug>/lock', methods=['POST'])
def lock_asset(slug):
    data = request.form
    branch = data.get('branch')
    repo_url = data.get('origin')
    file_path = data.get('filePath')
    user = data.get('userName')

    if not file_path or not user:
        return jsonify({'error': 'Missing required parameters (filePath, userName)'}), 400

    with get_db(slug) as conn:
        existing_lock = conn.execute(
            'SELECT * FROM asset_lock WHERE file_path = ?', (file_path,)
        ).fetchone()

        if existing_lock:
            if existing_lock['user'] == user:
                return jsonify({'message': 'Asset already locked by you'}), 200
            else:
                return jsonify({
                    'error': 'Asset is already locked by another user',
                    'user': existing_lock['user'],
                    'branch': existing_lock['branch'],
                }), 403

        timestamp = datetime.datetime.utcnow().isoformat()
        conn.execute(
            'INSERT INTO asset_lock (file_path, user, branch, repo_url, timestamp) '
            'VALUES (?, ?, ?, ?, ?)',
            (file_path, user, branch, repo_url, timestamp),
        )
        conn.commit()
    return jsonify({'message': 'Asset locked successfully'}), 200


@app.route('/p/<slug>/unlock', methods=['POST'])
def unlock_asset(slug):
    data = request.form
    file_path = data.get('filePath')
    user = data.get('userName')

    if not file_path or not user:
        return jsonify({'error': 'Missing required parameters (filePath, userName)'}), 400

    with get_db(slug) as conn:
        existing_lock = conn.execute(
            'SELECT * FROM asset_lock WHERE file_path = ?', (file_path,)
        ).fetchone()

        if not existing_lock:
            return jsonify({'error': 'Asset is not locked'}), 404

        if existing_lock['user'] != user:
            return jsonify({'error': 'Cannot unlock asset locked by another user'}), 403

        conn.execute('DELETE FROM asset_lock WHERE file_path = ?', (file_path,))
        conn.commit()
    return jsonify({'message': 'Asset unlocked successfully'}), 200


@app.route('/p/<slug>/status', methods=['GET'])
def lock_status(slug):
    file_path = request.args.get('filePath')

    with get_db(slug) as conn:
        existing_lock = conn.execute(
            'SELECT * FROM asset_lock WHERE file_path = ?', (file_path,)
        ).fetchone()

    if existing_lock:
        return jsonify({
            'locked': True,
            'user': existing_lock['user'],
            'branch': existing_lock['branch'],
            'timestamp': existing_lock['timestamp'],
        }), 200
    else:
        return jsonify({'locked': False}), 200


@app.route('/p/<slug>/lockedAssets', methods=['GET'])
def locked_assets(slug):
    with get_db(slug) as conn:
        locks = conn.execute('SELECT * FROM asset_lock').fetchall()

    lock_dict = {
        lock['file_path']: {
            "user": lock['user'],
            "branch": lock['branch'],
        }
        for lock in locks
    }
    return jsonify({"locks": lock_dict}), 200


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'}), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5055))
    app.run(debug=False, host='0.0.0.0', port=port)
