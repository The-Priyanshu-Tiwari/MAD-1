from extensions import db
from flask_login import UserMixin
from datetime import datetime


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'admin' or 'user'
   

class ParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(150))
    max_spots = db.Column(db.Integer, nullable=False)
    # backrefs:
    # spots: relationship from ParkingSpot (defined there)
    # bookings: if needed, can be derived via spots → bookings


class ParkingSpot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    status = db.Column(db.String(1), default="A")  # A=Available, O=Occupied

    # Relationship to ParkingLot with backref 'spots'
    parking_lot = db.relationship('ParkingLot', backref='spots')


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    cost = db.Column(db.Float)

    # Relationships:
    spot = db.relationship('ParkingSpot', backref='bookings')
    user = db.relationship('User', backref='bookings')

    # Removed lot_id and parking_lot relationship from Booking, to avoid conflicts
    # Access lot by booking.spot.parking_lot

