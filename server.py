import os
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

database_url = os.environ.get('DATABASE_URL', 'sqlite:///agasobanuye.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'adolphe-secret-2026')

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    def set_password(self, p):
        self.password_hash = generate_password_hash(p)

def init_admin():
    email = os.environ.get('ADMIN_EMAIL', 'adolphegladnizeyimana@gmail.com')
    pwd = os.environ.get('ADMIN_PASSWORD', 'adolphegladnizeyimana@')
    try:
        db.create_all()
        admin = User.query.filter_by(email=email).first()
        if admin:
            admin.set_password(pwd)
            admin.is_admin = True
        else:
            admin = User(email=email, is_admin=True)
            admin.set_password(pwd)
            db.session.add(admin)
        db.session.commit()
        print(f"=== ADMIN OK {email} ===")
    except Exception as e:
        print(f"Admin error {e}")
        db.session.rollback()

def init():
    init_admin()

with app.app_context():
    init_admin()

@app.route('/')
def home():
    return jsonify({"message": "Agasobanuye1 API running", "admin": "adolphegladnizeyimana@gmail.com"})

@app.route('/api/health')
def health():
    return jsonify({"status": "Live"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
