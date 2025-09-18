import eventlet
eventlet.monkey_patch()

import boto3
import requests
from flask import Flask, render_template, request, redirect, jsonify, send_file, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from flask_migrate import Migrate
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.middleware.proxy_fix import ProxyFix
from io import BytesIO
import os
import google.oauth2.id_token
import google.auth.transport.requests
from sqlalchemy import desc, and_
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from werkzeug.utils import secure_filename
import uuid
import mimetypes
from botocore.exceptions import ClientError



# App + DB setup
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://newspaper_db_47wk_user:2WQbescUw19AeDpYVPPGZzFeVnyePdiV@dpg-d2e1sv3e5dus73feem00-a.ohio-postgres.render.com/newspaper_db_47wk'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app, cors_allowed_origins="*")


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

ALLOWED_EMAILS = {
    "hlewis26@ccp-stl.org",
    "jcopley26@ccp-stl.org",
    "tschilly@chaminade-stl.org",
    "hbryant@chaminade-stl.org"
}

@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

@app.context_processor
def inject_allowed_emails():
    return dict(ALLOWED_EMAILS=ALLOWED_EMAILS)



# AWS S3 setup
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    region_name=os.environ['AWS_REGION']
)
BUCKET_NAME = os.environ['S3_BUCKET_NAME']

# Models
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
    cat = db.Column(db.String(50), nullable=True)

class ArticleFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    s3_key = db.Column(db.String(200), nullable=False)

class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    active = db.Column(db.Boolean, default=True)

class AttendanceDate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    date_id = db.Column(db.Integer, db.ForeignKey('attendance_date.id'), nullable=False)
    present = db.Column(db.Boolean, default=False)

    person = db.relationship("Person")
    date = db.relationship("AttendanceDate")

# Login + Logout

@app.route("/google_login")
def google_login():
   
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

    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("home"))


# Routes (protected)

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
    article = Article.query.get_or_404(article_id)

    if 'file' not in request.files:
        return jsonify(success=False, message="No file uploaded"), 400

    file = request.files['file']
    if not file or file.filename.strip() == '':
        return jsonify(success=False, message="Empty filename"), 400

    
    filename = secure_filename(file.filename)
    s3_key = f"articles/{article_id}/{uuid.uuid4().hex}_{filename}"

    mimetype = file.mimetype or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    try:
        s3_client.upload_fileobj(
            file,
            BUCKET_NAME,
            s3_key,
            ExtraArgs={"ContentType": mimetype}
        )
    except ClientError as e:
        app.logger.error(f"S3 upload failed: {e}")
        return jsonify(success=False, message="Upload failed"), 500

 
    new_file = ArticleFile(
        article_id=article.id,
        filename=filename,
        s3_key=s3_key
    )
    db.session.add(new_file)
    db.session.commit()

    file_url = url_for('download_file', file_id=new_file.id)

    socketio.emit('file_uploaded', {
        'articleId': article.id,
        'file_id': new_file.id,
        'filename': new_file.filename,
        'file_url': file_url
    })

    return jsonify(success=True, file_id=new_file.id, filename=filename, file_url=file_url)

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
    file = ArticleFile.query.get_or_404(file_id)

    file_obj = BytesIO()
    try:
        s3_client.download_fileobj(BUCKET_NAME, file.s3_key, file_obj)
    except ClientError as e:
        app.logger.error(f"S3 download failed: {e}")
        return "File not found in storage", 404

    file_obj.seek(0)

   
    mtype, _ = mimetypes.guess_type(file.filename)
    mimetype = mtype or "application/octet-stream"

    return send_file(
        file_obj,
        mimetype=mimetype,
        as_attachment=True,
        download_name=file.filename
    )

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
    cat = request.form['cat']

    for a in Article.query.all():
        a.position += 1

    new_article = Article(title=title, author=author, deadline=deadline, cat=cat, position=0)
    db.session.add(new_article)
    db.session.commit()

    socketio.emit('article_added', {
        'id': new_article.id,
        'title': title,
        'cat': cat,
        'author': author,
        'status': new_article.status,
        'deadline': deadline,
        'editor': new_article.editor
    })

    order = [a.id for a in Article.query.order_by(Article.position).all()]
    socketio.emit('update_article_order', {'order': order})

    return redirect('/')



@app.route('/delete/<int:article_id>', methods=['POST'])
@login_required
def delete_article(article_id):
    article = Article.query.get(article_id)
    if not article:
        return jsonify(success=False), 404

    deleted_position = article.position
    db.session.delete(article)
    db.session.commit()

    for a in Article.query.filter(Article.position > deleted_position).all():
        a.position -= 1
    db.session.commit()

    socketio.emit('article_deleted', {'id': article_id})

    order = [a.id for a in Article.query.order_by(Article.position).all()]
    socketio.emit('update_article_order', {'order': order})

    return jsonify(success=True)


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

@app.route('/update_cat/<int:article_id>', methods=['POST'])
@login_required
def update_cat(article_id):
    article = Article.query.get(article_id)
    if article:
        data = request.json
        article.cat = data.get('cat', None)
        db.session.commit()
        socketio.emit('cat_updated', {'id': article.id, 'cat': article.cat})
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

@app.route("/manage")
@login_required
def manage():
    if current_user.email not in ALLOWED_EMAILS:
        return "Forbidden", 403
    return render_template("manage.html")

@app.route("/manage/attendance")
@login_required
def manage_attendance():
    if current_user.email not in ALLOWED_EMAILS:
        return "Forbidden", 403
    # render the UI (template provided below)
    return render_template("manage_attendance.html")


@app.route("/api/attendance/data")
@login_required
def attendance_data():
    if current_user.email not in ALLOWED_EMAILS:
        return jsonify({"error": "forbidden"}), 403

    people = Person.query.order_by(Person.name).all()
    dates = AttendanceDate.query.order_by(AttendanceDate.date).all()
    attendances = Attendance.query.all()

    # Convert tuple keys to string keys
    att_map = {f"{a.person_id}_{a.date_id}": a.present for a in attendances}

    people_serial = [{"id": p.id, "name": p.name, "active": p.active} for p in people]
    dates_serial = [{"id": d.id, "date": d.date.isoformat()} for d in dates]

    return jsonify({
        "people": people_serial,
        "dates": dates_serial,
        "attendance": att_map
    })


@app.route("/api/attendance/toggle", methods=["POST"])
@login_required
def attendance_toggle():
    """Toggle a single cell: person_id + date_id + optional present boolean."""
    if current_user.email not in ALLOWED_EMAILS:
        return jsonify({"error": "forbidden"}), 403

    data = request.json or {}
    person_id = data.get("person_id")
    date_id = data.get("date_id")
    # allow explicit set of present or toggle if omitted
    explicit_present = data.get("present", None)

    if not person_id or not date_id:
        return jsonify({"error": "missing params"}), 400

    person = Person.query.get(person_id)
    date = AttendanceDate.query.get(date_id)
    if not person or not date:
        return jsonify({"error": "not found"}), 404

    att = Attendance.query.filter_by(person_id=person_id, date_id=date_id).first()
    if not att:
        att = Attendance(person_id=person_id, date_id=date_id, present=False)
        db.session.add(att)

    if explicit_present is None:
        att.present = not att.present
    else:
        att.present = bool(explicit_present)

    db.session.commit()

    # emit to other clients
    socketio.emit("attendance_updated", {
        "person_id": person_id,
        "date_id": date_id,
        "present": att.present
    })

    return jsonify({"person_id": person_id, "date_id": date_id, "present": att.present})


@app.route("/api/attendance/add_person", methods=["POST"])
@login_required
def attendance_add_person():
    if current_user.email not in ALLOWED_EMAILS:
        return jsonify({"error": "forbidden"}), 403

    name = (request.json or {}).get("name", "").strip()
    if not name:
        return jsonify({"error": "empty name"}), 400

    # uniqueness enforced by model -- handle gracefully
    try:
        new_p = Person(name=name, active=True)
        db.session.add(new_p)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "person exists"}), 400

    # Optionally pre-create Attendance rows for existing dates (not required)
    dates = AttendanceDate.query.all()
    for d in dates:
        # only create existence if you want a row for each date automatically
        existing = Attendance.query.filter_by(person_id=new_p.id, date_id=d.id).first()
        if not existing:
            db.session.add(Attendance(person_id=new_p.id, date_id=d.id, present=False))
    db.session.commit()

    socketio.emit("person_added", {"id": new_p.id, "name": new_p.name})
    return jsonify({"id": new_p.id, "name": new_p.name})


@app.route("/api/attendance/delete_person", methods=["POST"])
@login_required
def attendance_delete_person():
    if current_user.email not in ALLOWED_EMAILS:
        return jsonify({"error": "forbidden"}), 403

    person_id = (request.json or {}).get("person_id")
    person = Person.query.get(person_id)
    if not person:
        return jsonify({"error": "not found"}), 404

    # delete related attendances (relationship cascade not defined on Person -> Attendance,
    # so we'll remove explicitly)
    Attendance.query.filter_by(person_id=person.id).delete()
    db.session.delete(person)
    db.session.commit()

    socketio.emit("person_deleted", {"person_id": person_id})
    return jsonify({"ok": True})


@app.route("/api/attendance/add_date", methods=["POST"])
@login_required
def attendance_add_date():
    if current_user.email not in ALLOWED_EMAILS:
        return jsonify({"error": "forbidden"}), 403

    date_str = (request.json or {}).get("date")  # expect YYYY-MM-DD
    if not date_str:
        return jsonify({"error": "empty date"}), 400

    try:
        parsed = datetime.fromisoformat(date_str).date()
    except Exception:
        return jsonify({"error": "invalid date format, use YYYY-MM-DD"}), 400

    try:
        new_d = AttendanceDate(date=parsed)
        db.session.add(new_d)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "date exists"}), 400

    # optional: create Attendances for each person for this date
    people = Person.query.all()
    for p in people:
        existing = Attendance.query.filter_by(person_id=p.id, date_id=new_d.id).first()
        if not existing:
            db.session.add(Attendance(person_id=p.id, date_id=new_d.id, present=False))
    db.session.commit()

    socketio.emit("date_added", {"id": new_d.id, "date": new_d.date.isoformat()})
    return jsonify({"id": new_d.id, "date": new_d.date.isoformat()})


@app.route("/api/attendance/delete_date", methods=["POST"])
@login_required
def attendance_delete_date():
    if current_user.email not in ALLOWED_EMAILS:
        return jsonify({"error": "forbidden"}), 403

    date_id = (request.json or {}).get("date_id")
    d = AttendanceDate.query.get(date_id)
    if not d:
        return jsonify({"error": "not found"}), 404

    # delete attendances for that date
    Attendance.query.filter_by(date_id=d.id).delete()
    db.session.delete(d)
    db.session.commit()

    socketio.emit("date_deleted", {"date_id": date_id})
    return jsonify({"ok": True})


@app.route("/manage/permissions")
@login_required
def manage_permissions():
    if current_user.email not in ALLOWED_EMAILS:
        return "Forbidden", 403
    return render_template("manage_permissions.html")

@app.route("/manage/about")
@login_required
def manage_about():
    if current_user.email not in ALLOWED_EMAILS:
        return "Forbidden", 403
    return render_template("manage_about.html")


# Calendar Routes
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


# Broadcast Socket.io

@socketio.on('article_archived')
def handle_article_archived(data):
    emit('article_archived', data, broadcast=True)

@socketio.on('article_activated')
def handle_article_activated(data):
    emit('article_activated', data, broadcast=True)



# Main
# -----------------------------------------------------------------------------
# if __name__ == '__main__':
#    with app.app_context():
#        db.create_all()
#    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
