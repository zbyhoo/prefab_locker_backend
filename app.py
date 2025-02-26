from flask import Flask, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Required for session management.

# SQLite is used for simplicity.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////app/data/locks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database model updated with repo_url (origin repository URL).
class AssetLock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    branch = db.Column(db.String(100), nullable=False)
    repo_url = db.Column(db.String(255), nullable=False)  # New field: repository origin URL.
    file_path = db.Column(db.String(255), nullable=False)
    user = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('branch', 'repo_url', 'file_path', name='_branch_repo_file_uc'),
    )


@app.route('/lock', methods=['POST'])
def lock_asset():
    data = request.form
    branch = data.get('branch')
    repo_url = data.get('origin')  # Repository origin URL
    file_path = data.get('filePath')
    user = data.get('userName') or session.get("user_email")  # Use provided username or logged-in Google email.
    
    if not branch or not repo_url or not file_path or not user:
        return jsonify({'error': 'Missing required parameters (branch, origin, filePath, userName)'}), 400

    # Query lock by branch, repo_url and file_path.
    existing_lock = AssetLock.query.filter_by(branch=branch, repo_url=repo_url, file_path=file_path).first()
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
    branch = data.get('branch')
    repo_url = data.get('origin')
    file_path = data.get('filePath')
    user = data.get('userName') or session.get("user_email")
    
    if not branch or not repo_url or not file_path or not user:
        return jsonify({'error': 'Missing required parameters (branch, origin, filePath, userName)'}), 400

    existing_lock = AssetLock.query.filter_by(branch=branch, repo_url=repo_url, file_path=file_path).first()
    if not existing_lock:
        return jsonify({'error': 'Asset is not locked'}), 404

    if existing_lock.user != user:
        return jsonify({'error': 'Cannot unlock asset locked by another user'}), 403

    db.session.delete(existing_lock)
    db.session.commit()
    return jsonify({'message': 'Asset unlocked successfully'}), 200


@app.route('/status', methods=['GET'])
def lock_status():
    branch = request.args.get('branch')
    repo_url = request.args.get('origin')
    file_path = request.args.get('filePath')
    
    if not branch or not repo_url or not file_path:
        return jsonify({'error': 'Missing required parameters (branch, origin, filePath)'}), 400

    existing_lock = AssetLock.query.filter_by(branch=branch, repo_url=repo_url, file_path=file_path).first()
    if existing_lock:
        return jsonify({
            'locked': True,
            'user': existing_lock.user,
            'timestamp': existing_lock.timestamp.isoformat()
        }), 200
    else:
        return jsonify({'locked': False}), 200


@app.route('/lockedAssets', methods=['GET'])
def locked_assets():
    branch = request.args.get('branch')
    repo_url = request.args.get('origin')
    
    if not branch or not repo_url:
        return jsonify({'error': 'Missing required parameters (branch, origin)'}), 400

    locks = AssetLock.query.filter_by(branch=branch, repo_url=repo_url).all()
    lock_dict = {lock.file_path: lock.user for lock in locks}
    return jsonify({"locks": lock_dict}), 200


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5005)
