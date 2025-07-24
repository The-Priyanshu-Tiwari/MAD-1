from flask import Flask, render_template, request, redirect, url_for, flash
from extensions import db, login_manager
from models import User, ParkingLot, ParkingSpot, Booking
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
import os
from datetime import datetime, timedelta
from flask import  jsonify



app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

# Create database tables within app context
with app.app_context():
    db.create_all()
    # Create admin user if not exists
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password=generate_password_hash('admin'),  # Removed method parameter
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('user_dashboard'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        
        new_user = User(
            username=username,
            password=generate_password_hash(password),  # Removed method parameter
            role='user'
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('user_dashboard'))
    return render_template('admin_dashboard.html')

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    return render_template('user_dashboard.html')

@app.route('/api/parkinglot', methods=['POST'])
@login_required
def create_parking_lot():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.json
    name = data.get('name')
    price = data.get('price')
    address = data.get('address')
    max_spots = data.get('max_spots')

    if not all([name, price, max_spots]):
        return jsonify({'error': 'Missing required fields'}), 400

    parking_lot = ParkingLot(name=name, price=price, address=address, max_spots=max_spots)
    db.session.add(parking_lot)
    db.session.commit()

    # Create parking spots for this lot
    for _ in range(max_spots):
        spot = ParkingSpot(lot_id=parking_lot.id, status='A')
        db.session.add(spot)
    db.session.commit()

    return jsonify({'message': 'Parking lot created', 'parking_lot_id': parking_lot.id}), 201


@app.route('/api/parkinglot/<int:lot_id>/slots', methods=['GET'])
@login_required
def get_parking_slots(lot_id):
    lot = ParkingLot.query.get(lot_id)
    if not lot:
        return jsonify({'error': 'Parking lot not found'}), 404

    spots = ParkingSpot.query.filter_by(lot_id=lot_id).all()
    spot_list = []
    for spot in spots:
        spot_list.append({'id': spot.id, 'status': spot.status})

    return jsonify({'parking_lot': lot.name, 'spots': spot_list}), 200


@app.route('/api/bookings', methods=['POST'])
@login_required
def book_parking_spot():
    data = request.json
    spot_id = data.get('spot_id')
    duration_minutes = data.get('duration_minutes', 60)  # Default 60 minutes booking

    spot = ParkingSpot.query.get(spot_id)
    if not spot:
        return jsonify({'error': 'Parking spot not found'}), 404

    # Check if spot is available
    if spot.status == 'A':
        now = datetime.utcnow()
        end_time = now + timedelta(minutes=duration_minutes)
        cost = duration_minutes / 60 * spot.parking_lot.price  # Calculate cost based on lot price

        booking = Booking(
            spot_id=spot.id,
            user_id=current_user.id,
            start_time=now,
            end_time=end_time,
            cost=cost
        )
        db.session.add(booking)
        spot.status = 'O'
        db.session.commit()
        return jsonify({
            'message': 'Booking confirmed',
            'spot_id': spot.id,
            'start_time': booking.start_time.isoformat(),
            'end_time': booking.end_time.isoformat(),
            'cost': booking.cost
        }), 201
    else:
        # Spot is occupied, find when will be free
        current_booking = Booking.query.filter(
            Booking.spot_id == spot.id,
            Booking.end_time > datetime.utcnow()
        ).order_by(Booking.end_time.desc()).first()

        if current_booking:
            free_time = current_booking.end_time.isoformat()
            return jsonify({'message': 'Spot occupied', 'will_be_free_at': free_time}), 409
        else:
            # If no active booking but status is still occupied (data inconsistency)
            spot.status = 'A'
            db.session.commit()
            return jsonify({'message': 'Spot status reset. Please try booking again.'}), 409
        

if __name__ == '__main__':
    app.run(debug=True)
