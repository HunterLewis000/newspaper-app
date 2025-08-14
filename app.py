import boto3
from flask import Flask, render_template, request, redirect, jsonify, send_file, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
import os
from io import BytesIO


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://newspaper_db_47wk_user:2WQbescUw19AeDpYVPPGZzFeVnyePdiV@dpg-d2e1sv3e5dus73feem00-a.ohio-postgres.render.com/newspaper_db_47wk'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")  # Enable cross-origin for Render

# S3 setup
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    region_name=os.environ['AWS_REGION']
)
BUCKET_NAME = os.environ['S3_BUCKET_NAME']


class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="Not Started")
    deadline = db.Column(db.String(20))
    file_key = db.Column(db.String(200))  # S3 object key

@app.route('/')
def index():
    articles = Article.query.all()
    return render_template('index.html', articles=articles)

# Upload file route
@app.route('/upload/<int:article_id>', methods=['POST'])
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
    article.file_key = s3_key
    db.session.commit()

    # Emit to clients if needed
    socketio.emit('file_uploaded', {'id': article_id, 'file_key': s3_key, 'filename': file.filename})
    return jsonify(success=True, file_key=s3_key, filename=file.filename)

# Preview file route
@app.route('/preview/<int:article_id>')
def preview_file(article_id):
    article = Article.query.get(article_id)
    if not article or not article.file_key:
        return "File not found", 404

    file_obj = BytesIO()
    s3_client.download_fileobj(BUCKET_NAME, article.file_key, file_obj)
    file_obj.seek(0)

    # Simple preview for images / PDFs
    if article.file_key.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        return send_file(file_obj, mimetype='image/jpeg')
    elif article.file_key.lower().endswith('.pdf'):
        return send_file(file_obj, mimetype='application/pdf')
    else:
        # For text files
        content = file_obj.read().decode('utf-8')
        return f"<pre>{content}</pre>"

# Add Article
@app.route('/add', methods=['POST'])
def add_article():
    title = request.form['title']
    author = request.form['author']
    deadline = request.form['deadline']
    new_article = Article(title=title, author=author, deadline=deadline)
    db.session.add(new_article)
    db.session.commit()
    # Emit the new article to all connected clients
    socketio.emit('article_added', {
        'id': new_article.id,
        'title': title,
        'author': author,
        'status': new_article.status,
        'deadline': deadline
    })
    return redirect('/')

# Delete Article
@app.route('/delete/<int:article_id>', methods=['POST'])
def delete_article(article_id):
    article = Article.query.get(article_id)
    if article:
        db.session.delete(article)
        db.session.commit()
        socketio.emit('article_deleted', {'id': article_id})
        return jsonify(success=True)
    return jsonify(success=False), 404

# Update Article
@app.route('/update/<int:article_id>', methods=['POST'])
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

# Update Status
@app.route('/update_status/<int:article_id>', methods=['POST'])
def update_status(article_id):
    article = Article.query.get(article_id)
    if article:
        new_status = request.json.get('status')
        article.status = new_status
        db.session.commit()
        socketio.emit('status_updated', {'id': article_id, 'status': new_status})
        return jsonify(success=True)
    return jsonify(success=False), 404

if __name__ == '__main__':
    if not os.path.exists('newspaper.db'):
        with app.app_context():
            db.create_all()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
