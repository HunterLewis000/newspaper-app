import eventlet
eventlet.monkey_patch()


import boto3
import requests
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
from io import BytesIO
import os
import google.oauth2.id_token
import google.auth.transport.requests
from sqlalchemy import desc
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


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
    scope=["https://www.googleapis.com/auth/calendar"],
    redirect_to="google_login"
)
app.register_blueprint(google_bp, url_prefix="/login")

# Flask-Login Config
login_manager = LoginManager()
login_manager.login_view = "home"  
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, id, email=None, name=None, token=None):
        self.id = id
        self.email = email
        self.name = name
        self.token = token


users = {} 

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
# Login + Logout
# -----------------------------------------------------------------------------
@app.route("/google_login")
def google_login():
    # Get the credential token sent by the button
    token = request.args.get("credential")
    if not token:
        flash("No credential received.", "error")
        return redirect(url_for("home"))

    # Verify
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

    # Extract
    email = id_info.get("email", "")

    allowed_domains = ["@ccp-stl.org", "@chaminade-stl.org"]

    if not any(email.lower().endswith(domain) for domain in allowed_domains):
        flash("Access denied: only @ccp-stl.org or @chaminade-stl.org accounts allowed.", "error")
        return redirect(url_for("home"))

    user_id = id_info["sub"]
    full_name = id_info.get("name", "")

    # Store
    if user_id not in users:
        users[user_id] = User(user_id, email=email, name=full_name)
    login_user(users[user_id])

    if not users.get(user_id):
        users[user_id] = User(user_id, email=email, name=full_name, token=google.token)
    else:
        users[user_id].token = google.token


    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("home"))


# -----------------------------------------------------------------------------
# Routes (protected)
# -----------------------------------------------------------------------------
@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("login.html", google_client_id=os.environ.get("GOOGLE_CLIENT_ID"))

@app.route('/dashboard')
@login_required
def index():
    articles = Article.query.filter_by(archived=False).order_by(Article.position).all()
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
    files = []
    for f in article.files:
        files.append({
            "id": f.id,
            "filename": f.filename,
            "file_url": url_for('download_file', file_id=f.id)
        })
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
    new_article = Article(title=title, author=author, deadline=deadline)
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

@app.route('/calendar')
@login_required
def calendar():

    return render_template('calendar.html')

@app.route('/activate/<int:article_id>', methods=['POST'])
@login_required
def activate_article(article_id):
    article = Article.query.get(article_id)
    if article:
        article.archived = False
        db.session.commit()
        socketio.emit('article_activated', {'id': article.id})
        return jsonify(success=True) 
    return jsonify(success=False), 404

@app.route('/update_order', methods=['POST'])
@login_required
def update_order():
    data = request.json
    order = data.get("order", [])
    try:
        for idx, article_id in enumerate(order):
            article = Article.query.get(int(article_id))
            if article:
                article.position = idx
        db.session.commit()

        socketio.emit("update_article_order", {"order": order})
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

# -----------------------------------------------------------------------------
# Calendar Routes
# -----------------------------------------------------------------------------
GOOGLE_CALENDAR_ID = '887571597d40c57fb2ca6c658ae6063475908c62860c563ad6aba974e1d90d7f@group.calendar.google.com'

@app.route('/api/calendar_events')
@login_required
def calendar_events():
    api_key = os.environ.get('GOOGLE_CALENDAR_API_KEY')
    url = f'https://www.googleapis.com/calendar/v3/calendars/{GOOGLE_CALENDAR_ID}/events?key={api_key}'
    resp = requests.get(url)
    if resp.status_code != 200:
        return jsonify([]), 500

    data = resp.json()
    events = [{
        'id': e['id'],
        'title': e.get('summary', 'No Title'),
        'start': e.get('start', {}).get('dateTime') or e.get('start', {}).get('date'),
        'end': e.get('end', {}).get('dateTime') or e.get('end', {}).get('date'),
        'description': e.get('description', ''),
        'location': e.get('location', '')
    } for e in data.get('items', [])]

    return jsonify(events)

@app.route('/api/update_calendar_event/<event_id>', methods=['POST'])
@login_required
def update_calendar_event(event_id):
    data = request.json
    if not data:
        return jsonify(success=False, message="No data provided"), 400

    if not getattr(current_user, 'token', None):
        return jsonify(success=False, message="No Google token found"), 401

    try:
        creds = Credentials(
            token=current_user.token['access_token'],
            refresh_token=current_user.token.get('refresh_token'),
            token_uri='https://oauth2.googleapis.com/token',
            client_id=os.environ['GOOGLE_CLIENT_ID'],
            client_secret=os.environ['GOOGLE_CLIENT_SECRET']
        )

        service = build('calendar', 'v3', credentials=creds)

        start_dt = data.get('start')
        end_dt = data.get('end')

        if not start_dt or not end_dt:
            return jsonify(success=False, message="Start and end datetime required"), 400

        event_body = {
            'summary': data.get('title'),
            'description': data.get('description', ''),
            'location': data.get('location', ''),
            'start': {'dateTime': start_dt, 'timeZone': 'America/Chicago'},
            'end': {'dateTime': end_dt, 'timeZone': 'America/Chicago'}
        }

        updated_event = service.events().update(
            calendarId=GOOGLE_CALENDAR_ID,
            eventId=event_id,
            body=event_body
        ).execute()

        return jsonify(success=True, event=updated_event)

    except Exception as e:
        print("Error updating event:", e)
        return jsonify(success=False, message=str(e)), 500

# -----------------------------------------------------------------------------
# Broadcast Socket.io
# -----------------------------------------------------------------------------
@socketio.on('article_archived')
def handle_article_archived(data):
    emit('article_archived', data, broadcast=True)

@socketio.on('article_activated')
def handle_article_activated(data):
    emit('article_activated', data, broadcast=True)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
# if __name__ == '__main__':
#    with app.app_context():
#        db.create_all()
#    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
