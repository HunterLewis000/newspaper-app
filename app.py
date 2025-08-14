from flask import Flask, render_template, request, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://username:password@host:port/dbname'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")  # Enable cross-origin for Render

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="Not Started")
    deadline = db.Column(db.String(20))

@app.route('/')
def index():
    articles = Article.query.all()
    return render_template('index.html', articles=articles)

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
