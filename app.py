from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from datetime import datetime
import os
from models import User
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Import models from models.py and forms from forms.py (see below)

# --- USER LOADER ---
@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# --- INITIALIZE DB AND CREATE ADMIN ---


@app.before_first_request
def create_tables_and_admin():
    from models import db
    db.create_all()
    # Create admin if not exists
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', password=generate_password_hash('admin', method='sha256'), role='admin')
        db.session.add(admin)
        db.session.commit()

@app.before_first_request
def create_tables_and_admin():
    db.create_all()
    from models import User
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', password=generate_password_hash('admin', method='sha256'), role='admin')
        db.session.add(admin)
        db.session.commit()

# --- ROUTES ---
@app.route('/')
def home():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Registration logic (see forms.py)
    pass

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Login logic (can distinguish admin vs user)
    pass

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('user_dashboard'))
    # Dashboard logic for admin
    return render_template('admin_dashboard.html')

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    if current_user.role != 'user':
        return redirect(url_for('admin_dashboard'))
    # Dashboard logic for user
    return render_template('user_dashboard.html')

# More routes for CRUD parking lots, spots, bookings, etc.

if __name__ == '__main__':
    app.run(debug=True)
