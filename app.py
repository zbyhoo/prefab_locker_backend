from flask import Flask, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
import datetime
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////app/data/locks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class AssetLock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    branch = db.Column(db.String(100), nullable=False)
    repo_url = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    user = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('file_path', name='_branch_repo_file_uc'),
    )

    def __init__(self, branch, repo_url, file_path, user):
        self.branch = branch
        self.repo_url = repo_url
        self.file_path = file_path
        self.user = user


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


@app.route('/lock', methods=['POST'])
def lock_asset():
    data = request.form
    branch = data.get('branch')
    repo_url = data.get('origin')
    file_path = data.get('filePath')
    user = data.get('userName') or session.get("user_email")
    
    if not branch or not repo_url or not file_path or not user:
        return jsonify({'error': 'Missing required parameters (branch, origin, filePath, userName)'}), 400

    existing_lock = AssetLock.query.filter_by(file_path=file_path).first()
    if existing_lock:
        if existing_lock.user == user:
            return jsonify({'message': 'Asset already locked by you'}), 200
        else:
            return jsonify({'error': 'Asset is already locked by another user'}), 403

    new_lock = AssetLock(branch=branch, repo_url=repo_url, file_path=file_path, user=user)
    db.session.add(new_lock)
    db.session.commit()
    return jsonify({'message': 'Asset locked successfully'}), 200


@app.route('/unlock', methods=['POST'])
def unlock_asset():
    data = request.form
    file_path = data.get('filePath')
    user = data.get('userName') or session.get("user_email")
    
    if not file_path or not user:
        return jsonify({'error': 'Missing required parameters (branch, origin, filePath, userName)'}), 400

    existing_lock = AssetLock.query.filter_by(file_path=file_path).first()
    if not existing_lock:
        return jsonify({'error': 'Asset is not locked'}), 404

    if existing_lock.user != user:
        return jsonify({'error': 'Cannot unlock asset locked by another user'}), 403

    db.session.delete(existing_lock)
    db.session.commit()
    return jsonify({'message': 'Asset unlocked successfully'}), 200


@app.route('/status', methods=['GET'])
def lock_status():
    file_path = request.args.get('filePath')
    
    existing_lock = AssetLock.query.filter_by(file_path=file_path).first()
    if existing_lock:
        return jsonify({
            'locked': True,
            'user': existing_lock.user,
            'branch': existing_lock.branch,
            'timestamp': existing_lock.timestamp.isoformat()
        }), 200
    else:
        return jsonify({'locked': False}), 200


@app.route('/lockedAssets', methods=['GET'])
def locked_assets():
    locks = AssetLock.query.all()
    lock_dict = {
        lock.file_path: {
            "user": lock.user,
            "branch": lock.branch
        }
        for lock in locks
    }
    return jsonify({"locks": lock_dict}), 200


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'}), 200


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5005)
