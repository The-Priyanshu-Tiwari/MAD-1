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


# Route to serve the Add Parking Lot HTML page (GET)
@app.route('/admin/add_parking_lot', methods=['GET'])
@login_required
def add_parking_lot():
    if current_user.role != 'admin':
        return redirect(url_for('user_dashboard'))
    return render_template('add_parking_lot.html')


# API route to handle parking lot creation (POST)
@app.route('/api/parkinglot', methods=['POST'])
@login_required
def create_parking_lot():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json() or {}
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



from datetime import datetime

@app.route('/api/parkinglot/<int:lot_id>/slots', methods=['GET'])
@login_required
def get_parking_slots(lot_id):
    lot = ParkingLot.query.get(lot_id)
    if not lot:
        return jsonify({'error': 'Parking lot not found'}), 404

    spots = ParkingSpot.query.filter_by(lot_id=lot_id).all()
    spot_list = []
    now = datetime.utcnow()

    for spot in spots:
        active_booking = Booking.query.filter(
            Booking.spot_id == spot.id,
            Booking.start_time <= now,
            Booking.end_time >= now
        ).first()

        cost = active_booking.cost if active_booking else None

        spot_list.append({
            'id': spot.id,
            'status': spot.status,
            'cost': spot.parking_lot.price,
        })

    return jsonify({
        'id': lot.id,
        'parking_lot': lot.name,
        'address': lot.address,
        'price': lot.price,
        'spots': spot_list
    }), 200



@app.route('/api/parkinglots', methods=['GET'])
@login_required
def get_all_parking_lots():
    lots = ParkingLot.query.all()
    lots_data = []
    for lot in lots:
        lots_data.append({
            'id': lot.id,
            'name': lot.name,
            'address': lot.address,
            'max_spots': lot.max_spots,
            'price': lot.price
        })
    return jsonify(lots_data)



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

@app.route('/api/mybookings', methods=['GET'])
@login_required
def my_bookings():
    bookings = Booking.query.filter_by(user_id=current_user.id).all()

    result = []
    for booking in bookings:
        # Access related lot via booking.spot.parking_lot
        lot_name = booking.spot.parking_lot.name if booking.spot and booking.spot.parking_lot else 'N/A'

        result.append({
            'id': booking.id,
            'lot_name': lot_name,
            'spot_id': booking.spot_id,
            'start_time': booking.start_time.isoformat(),
            'end_time': booking.end_time.isoformat() if booking.end_time else None,
            'cost': booking.cost
        })

    return jsonify(result)

@app.route('/api/parkinglot/<int:lot_id>', methods=['PUT'])
@login_required
def update_parking_lot(lot_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    lot = ParkingLot.query.get_or_404(lot_id)
    data = request.get_json() or {}

    lot.name = data.get('name', lot.name)
    lot.address = data.get('address', lot.address)
    lot.price = data.get('price', lot.price)
    max_spots = data.get('max_spots', lot.max_spots)

    # If spot count changed, only update count if more spots are needed
    if max_spots > lot.max_spots:
        for _ in range(max_spots - lot.max_spots):
            spot = ParkingSpot(lot_id=lot.id, status='A')
            db.session.add(spot)
    lot.max_spots = max_spots

    db.session.commit()
    return jsonify({'message': 'Parking lot updated successfully'}), 200

@app.route('/api/parkinglot/<int:lot_id>', methods=['DELETE'])
@login_required
def delete_parking_lot(lot_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    lot = ParkingLot.query.get_or_404(lot_id)

    # First delete associated parking spots and bookings
    bookings = Booking.query.join(ParkingSpot).filter(ParkingSpot.lot_id == lot.id).all()
    for booking in bookings:
        db.session.delete(booking)

    ParkingSpot.query.filter_by(lot_id=lot.id).delete()
    db.session.delete(lot)
    db.session.commit()

    return jsonify({'message': 'Parking lot deleted successfully'}), 200



if __name__ == '__main__':
    app.run(debug=True)
