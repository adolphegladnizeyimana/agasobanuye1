import os
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Config - works on Render and local
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///agasobanuye.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-12345')

db = SQLAlchemy(app)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

def init_admin():
    # YOUR EMAIL AND PASSWORD HERE
    admin_email = os.environ.get('ADMIN_EMAIL', 'adolphegladnizeyimana@gmail.com')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'adolphegladnizeyimana@')
    
    try:
        db.create_all()
        admin = User.query.filter_by(email=admin_email).first()
        if admin:
            admin.set_password(admin_password)
            admin.is_admin = True
            print(f"=== ADMIN UPDATED to {admin_email} ===")
        else:
            admin = User(email=admin_email, is_admin=True)
            admin.set_password(admin_password)
            db.session.add(admin)
            print(f"=== ADMIN CREATED {admin_email} ===")
        db.session.commit()
        print(f"Password set successfully")
    except Exception as e:
        print(f"Admin init error: {e}")
        db.session.rollback()

with app.app_context():
    init_admin()

@app.route('/')
def home():
    return jsonify({"message": "Agasobanuye1 API is running", "status": "ok"})

@app.route('/api/health')
def health():
    return jsonify({"status": "Live"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
