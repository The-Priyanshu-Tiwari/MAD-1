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

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password=generate_password_hash('admin'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json() or {}
            username = data.get('username')
            password = data.get('password')
            role = data.get('role', 'user')
            if not username or not password:
                return jsonify({'error': 'Username and password are required'}), 400
            if User.query.filter_by(username=username).first():
                return jsonify({'error': 'Username already exists'}), 409

            hashed_password = generate_password_hash(password)
            new_user = User(username=username, password=hashed_password, role=role)
            db.session.add(new_user)
            db.session.commit()
            return jsonify({'message': 'Account created successfully!'}), 201
        else:
            username = request.form.get('username')
            password = request.form.get('password')
            role = request.form.get('role', 'user')

            if not username or not password:
                flash('Username and password are required', 'danger')
                return redirect(url_for('register'))

            if User.query.filter_by(username=username).first():
                flash('Username already exists', 'danger')
                return redirect(url_for('register'))

            hashed_password = generate_password_hash(password)
            new_user = User(username=username, password=hashed_password, role=role)
            db.session.add(new_user)
            db.session.commit()
            flash('Account created successfully!', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json() or {}
            username = data.get('username')
            password = data.get('password')
        else:
            username = request.form.get('username')
            password = request.form.get('password')

        print(f'Login attempt for username: {username} with password: {password}')

        user = User.query.filter_by(username=username).first()
        print(f'User found in DB: {user}')

        if user:
            from werkzeug.security import check_password_hash
            pwd_check = check_password_hash(user.password, password)
            print(f'Password hash matches: {pwd_check}')
        else:
            pwd_check = False

        if user and pwd_check:
            login_user(user)
            if request.is_json:
                return jsonify({
                    'message': 'Logged in successfully!',
                    'username': user.username,
                    'role': user.role
                }), 200
            flash('Logged in successfully!', 'success')
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))

        if request.is_json:
            return jsonify({'error': 'Invalid username or password'}), 401
        flash('Invalid username or password', 'danger')

    return render_template('login.html')


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
    duration_minutes = data.get('duration_minutes', 60)  # default to 60 minutes
    start_time_str = data.get('start_time')  # new field, optional

    # Validate spot_id
    spot = ParkingSpot.query.get(spot_id)
    if not spot:
        return jsonify({'error': 'Parking spot not found'}), 404

    # Parse start_time if provided
    if start_time_str:
        try:
            # Expecting ISO 8601 format, e.g. '2025-07-24T18:00:00'
            start_time = datetime.fromisoformat(start_time_str)
        except ValueError:
            return jsonify({'error': 'Invalid start_time format. Use ISO 8601 format.'}), 400
    else:
        start_time = datetime.utcnow()

    # Calculate end_time
    end_time = start_time + timedelta(minutes=duration_minutes)

    # Check if spot is available **for the requested time period**
    # Here you should check if any existing booking overlaps with [start_time, end_time)
    overlapping_booking = Booking.query.filter(
        Booking.spot_id == spot_id,
        Booking.end_time > start_time,
        Booking.start_time < end_time
    ).first()

    if overlapping_booking:
        return jsonify({
            'message': 'Spot occupied',
            'will_be_free_at': overlapping_booking.end_time.isoformat()
        }), 409

    # If available, create booking
    cost = (duration_minutes / 60) * spot.parking_lot.price

    booking = Booking(
        spot_id=spot.id,
        user_id=current_user.id,
        start_time=start_time,
        end_time=end_time,
        cost=cost
    )
    db.session.add(booking)

    # Update spot status to 'O' (Occupied) - but this is simplistic for bookings in future;
    # ideally, a spot's occupancy depends on current datetime, not just bookings.
    # You might want to manage spot status more dynamically in a complete app.
    spot.status = 'O'

    db.session.commit()

    return jsonify({
        'message': 'Booking confirmed',
        'spot_id': spot.id,
        'start_time': booking.start_time.isoformat(),
        'end_time': booking.end_time.isoformat(),
        'cost': booking.cost
    }), 201

if __name__ == '__main__':
    app.run(debug=True)
