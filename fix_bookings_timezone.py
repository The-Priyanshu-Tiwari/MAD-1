from app import app, db
from models import Booking
from datetime import timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

with app.app_context():
    bookings = Booking.query.all()
    for b in bookings:
        changed = False
        if b.start_time and b.start_time.tzinfo is None:
            b.start_time = b.start_time.replace(tzinfo=IST)
            changed = True
        if b.end_time and b.end_time.tzinfo is None:
            b.end_time = b.end_time.replace(tzinfo=IST)
            changed = True
        if changed:
            print(f"✔️ Updated Booking ID: {b.id}")
    db.session.commit()

print("✅ Timezone fixed for all existing bookings.")

