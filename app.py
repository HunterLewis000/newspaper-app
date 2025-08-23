import eventlet
eventlet.monkey_patch()

import os
from io import BytesIO
from datetime import datetime

import boto3
import google.oauth2.id_token
import google.auth.transport.requests
from flask import Flask, render_template, request, redirect, jsonify, send_file, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from flask_migrate import Migrate
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from flask_dance.contrib.google import make_google_blueprint, google
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import func

# -----------------------------------------------------------------------------
# App + DB setup
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://newspaper_db_47wk_user:2WQbescUw19AeDpYVPPGZzFeVnyePdiV@dpg-d2e1sv3e5dus73feem00-a.ohio-postgres.render.com/newspaper_db_47wk'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app, cors_allowed_origins="*")

# -----------------------------------------------------------------------------
# Auth setup (LoginManager + Google OAuth)
# -----------------------------------------------------------------------------
google_bp = make_google_blueprint(
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    redirect_to="google_login"
)
app.register_blueprint(google_bp, url_prefix="/login")

login_manager = LoginManager()
login_manager.login_view = "home"
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, id, email=None, name=None):
        self.id = id
        self.email = email
        self.name = name

users = {}  # in-memory for demo

@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

# -----------------------------------------------------------------------------
# AWS S3 setup
# -----------------------------------------------------------------------------
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    region_name=os.environ['AWS_REGION']
)
BUCKET_NAME = os.environ['S3_BUCKET_NAME']

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="Not Started")
    editor = db.Column(db.String(50), nullable=True)
    deadline = db.Column(db.String(20))
    files = db.relationship('ArticleFile', backref='article', lazy=True, cascade="all, delete-orphan")
    archived = db.Column(db.Boolean, default=False)
    position = db.Column(db.Integer, nullable=False, default=0)

class ArticleFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    s3_key = db.Column(db.String(200), nullable=False)

# -----------------------------------------------------------------------------
# Helpers for ordering
# -----------------------------------------------------------------------------
def resequence_positions(include_archived=False):
    """
    Compress positions to 0..N-1 in the current (filtered) list to avoid gaps.
    """
    q = Article.query
    if not include_archived:
        q = q.filter_by(archived=False)
    articles = q.order_by(Article.position.asc(), Article.id.asc()).all()
    for idx, a in enumerate(articles):
        a.position = idx
        db.session.add(a)
    db.session.commit()

def ensure_positions_seeded():
    """
    If all (active) positions are 0 or NULL-ish, seed them by id.
    Call on first run or after column add.
    """
    # Detect if there are duplicates/all zero among active items
    active = Article.query.filter_by(archived=False).all()
    if not active:
        return
    unique_positions = {a.position for a in active}
    if len(unique_positions) == 1 and (0 in unique_positions or None in unique_positions):
        # Seed by id order
        by_id = sorted(active, key=lambda a: a.id)
        for idx, a in enumerate(by_id):
            a.position = idx
            db.session.add(a)
        db.session.commit()

# -----------------------------------------------------------------------------
# Login + Logout
# -----------------------------------------------------------------------------
@app.route("/google_login")
def google_login():
    token = request.args.get("credential")
    if not token:
        flash("No credential received.", "error")
        return redirect(url_for("home"))

    request_adapter = google.auth.transport.requests.Request()
    try:
        id_info = google.oauth2.id_token.verify_oauth2_token(
            token,
            request_adapter,
            os.environ.get("GOOGLE_CLIENT_ID")
        )
    except ValueError:
        flash("Invalid Google token.", "error")
        return redirect(url_for("home"))

    email = id_info.get("email", "")
    allowed_domains = ["@ccp-stl.org", "@chaminade-stl.org"]
    if not any(email.lower().endswith(domain) for domain in allowed_domains):
        flash("Access denied: only @ccp-stl.org or @chaminade-stl.org accounts allowed.", "error")
        return redirect(url_for("home"))

    user_id = id_info["sub"]
    full_name = id_info.get("name", "")
    if user_id not in users:
        users[user_id] = User(user_id, email=email, name=full_name)
    login_user(users[user_id])

    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("home"))

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("login.html", google_client_id=os.environ.get("GOOGLE_CLIENT_ID"))

@app.route('/dashboard')
@login_required
def index():
    ensure_positions_seeded()
    articles = Article.query.filter_by(archived=False).order_by(Article.position.asc(), Article.id.asc()).all()
    return render_template('index.html', articles=articles)

@app.route('/upload/<int:article_id>', methods=['POST'])
@login_required
def upload_file(article_id):
    article = Article.query.get(article_id)
    if not article:
        return jsonify(success=False), 404

    if 'file' not in request.files:
        return jsonify(success=False, message="No file uploaded"), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify(success=False, message="Empty filename"), 400

    s3_key = f"articles/{article_id}/{file.filename}"
    s3_client.upload_fileobj(file, BUCKET_NAME, s3_key)

    new_file = ArticleFile(article_id=article.id, filename=file.filename, s3_key=s3_key)
    db.session.add(new_file)
    db.session.commit()

    file_url = url_for('download_file', file_id=new_file.id)
    socketio.emit('file_uploaded', {
        'articleId': article.id,
        'file_id': new_file.id,
        'filename': new_file.filename,
        'file_url': file_url
    })
    return jsonify(success=True, file_id=new_file.id, filename=new_file.filename, file_url=file_url)

@app.route('/files/<int:article_id>')
@login_required
def list_files(article_id):
    article = Article.query.get_or_404(article_id)
    files = [{
        "id": f.id,
        "filename": f.filename,
        "file_url": url_for('download_file', file_id=f.id)
    } for f in article.files]
    return jsonify(files=files)

@app.route('/download_file/<int:file_id>')
@login_required
def download_file(file_id):
    file = ArticleFile.query.get(file_id)
    if not file:
        return "File not found", 404

    file_obj = BytesIO()
    s3_client.download_fileobj(BUCKET_NAME, file.s3_key, file_obj)
    file_obj.seek(0)

    if file.s3_key.lower().endswith('.docx'):
        mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    elif file.s3_key.lower().endswith('.pdf'):
        mimetype = 'application/pdf'
    elif file.s3_key.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        mimetype = 'image/jpeg'
    else:
        mimetype = 'application/octet-stream'

    return send_file(file_obj, mimetype=mimetype, as_attachment=True, download_name=file.filename)

@app.route('/delete_file/<int:file_id>', methods=['POST'])
@login_required
def delete_file(file_id):
    file = ArticleFile.query.get(file_id)
    if not file:
        return jsonify(success=False), 404

    s3_client.delete_object(Bucket=BUCKET_NAME, Key=file.s3_key)
    db.session.delete(file)
    db.session.commit()

    socketio.emit('file_deleted', {'file_id': file.id, 'article_id': file.article_id})
    return jsonify(success=True)

@app.route('/add', methods=['POST'])
@login_required
def add_article():
    title = request.form['title']
    author = request.form['author']
    deadline = request.form['deadline']

    # Put new article at the end of the current active list
    max_position = db.session.query(func.max(Article.position)).filter(Article.archived == False).scalar()
    next_pos = (max_position + 1) if max_position is not None else 0

    new_article = Article(title=title, author=author, deadline=deadline, position=next_pos)
    db.session.add(new_article)
    db.session.commit()

    socketio.emit('article_added', {
        'id': new_article.id,
        'title': title,
        'author': author,
        'status': new_article.status,
        'deadline': deadline,
        'editor': new_article.editor
    })
    return redirect('/')

@app.route('/delete/<int:article_id>', methods=['POST'])
@login_required
def delete_article(article_id):
    article = Article.query.get(article_id)
    if article:
        db.session.delete(article)
        db.session.commit()
        resequence_positions(include_archived=False)
        socketio.emit('article_deleted', {'id': article_id})
        return jsonify(success=True)
    return jsonify(success=False), 404

@app.route('/update/<int:article_id>', methods=['POST'])
@login_required
def update_article(article_id):
    article = Article.query.get(article_id)
    if article:
        data = request.json
        article.title = data.get('title', article.title)
        article.author = data.get('author', article.author)
        article.deadline = data.get('deadline', article.deadline)
        db.session.commit()

        socketio.emit('article_updated', {
            'id': article.id,
            'title': article.title,
            'author': article.author,
            'deadline': article.deadline
        })
        return jsonify(success=True)
    return jsonify(success=False), 404

@app.route('/update_status/<int:article_id>', methods=['POST'])
@login_required
def update_status(article_id):
    article = Article.query.get(article_id)
    if article:
        new_status = request.json.get('status')
        article.status = new_status
        db.session.commit()
        socketio.emit('status_updated', {'id': article_id, 'status': new_status})
        return jsonify(success=True)
    return jsonify(success=False), 404

@app.route('/update_editor/<int:article_id>', methods=['POST'])
@login_required
def update_editor(article_id):
    article = Article.query.get(article_id)
    if article:
        data = request.json
        article.editor = data.get('editor', None)
        db.session.commit()
        socketio.emit('editor_updated', {'id': article.id, 'editor': article.editor})
        return jsonify(success=True)
    return jsonify(success=False), 404

@app.route('/article/<int:article_id>')
@login_required
def get_article(article_id):
    article = Article.query.get_or_404(article_id)
    return jsonify({
        'id': article.id,
        'title': article.title,
        'author': article.author,
        'status': article.status,
        'editor': article.editor,
        'deadline': article.deadline,
        'archived': article.archived
    })

@app.route('/archive/<int:article_id>', methods=['POST'])
@login_required
def archive_article(article_id):
    article = Article.query.get(article_id)
    if article:
        article.archived = True
        db.session.commit()
        resequence_positions(include_archived=False)
        socketio.emit('article_archived', {'id': article.id})
        return jsonify(success=True)
    return jsonify(success=False), 404

@app.route('/archived')
@login_required
def archived():
    articles = Article.query.filter_by(archived=True).all()

    def parse_deadline(article):
        try:
            return datetime.strptime(article.deadline, "%Y-%m-%d")
        except (TypeError, ValueError):
            return datetime.min

    articles_sorted = sorted(articles, key=parse_deadline, reverse=True)
    return render_template('archived.html', articles=articles_sorted)

@app.route('/activate/<int:article_id>', methods=['POST'])
@login_required
def activate_article(article_id):
    article = Article.query.get(article_id)
    if article:
        # Reactivate and place at end of active list
        article.archived = False
        max_position = db.session.query(func.max(Article.position)).filter(Article.archived == False).scalar()
        article.position = (max_position + 1) if max_position is not None else 0
        db.session.commit()
        socketio.emit('article_activated', {'id': article.id})
        return jsonify(success=True)
    return jsonify(success=False), 404

# -----------------------------------------------------------------------------
# Socket.IO events (Drag-to-reorder)
# -----------------------------------------------------------------------------
@socketio.on('reorder_articles')
def handle_reorder_articles(data):
    """
    Receives: { order: [<article_id>, <article_id>, ...] } in the *new* order
    Updates .position = index for active (non-archived) rows only.
    Broadcasts the final order to all clients (including sender) for consistency.
    """
    order = data.get('order', [])
    if not isinstance(order, list):
        return

    # Ensure IDs are ints and correspond to active articles
    ids_in_order = []
    for raw in order:
        try:
            ids_in_order.append(int(raw))
        except (TypeError, ValueError):
            continue

    # Assign positions sequentially according to the order received
    # Only update non-archived items; ignore archived if sent by mistake
    active_ids = {a.id for a in Article.query.filter_by(archived=False).all()}
    idx = 0
    for article_id in ids_in_order:
        if article_id in active_ids:
            a = Article.query.get(article_id)
            if a:
                a.position = idx
                db.session.add(a)
                idx += 1
    db.session.commit()

    # Optional safety: resequence to compress any gaps
    resequence_positions(include_archived=False)

    # Broadcast new order to everyone (sender included) so UIs stay in sync
    emit('update_article_order', {'order': [str(i) for i in ids_in_order]}, broadcast=True)

# -----------------------------------------------------------------------------
# Flask CLI helper to (re)seed positions on demand
# -----------------------------------------------------------------------------
@app.cli.command("init-positions")
def cli_init_positions():
    """Seed or resequence active article positions starting at 0 by id."""
    with app.app_context():
        ensure_positions_seeded()
        resequence_positions(include_archived=False)
        print("Active article positions initialized.")

# -----------------------------------------------------------------------------
# Main (Render/SocketIO host)
# -----------------------------------------------------------------------------
# if __name__ == '__main__':
#     with app.app_context():
#         db.create_all()
#     socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
