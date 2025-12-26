import os
from app import create_app
import eventlet

# Create app instance
app, socketio = create_app()

# Initialize database tables
with app.app_context():
    from models import db
    try:
        db.create_all()
        print("✅ Database initialized")
    except Exception as e:
        print(f"⚠️ Database initialization warning: {e}")

# Export for gunicorn
application = app

