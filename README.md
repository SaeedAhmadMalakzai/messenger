# SaeedsChat Messenger

A real-time chat application built with Flask, Socket.IO, and SQLAlchemy. Features include lobby chat, private messaging, voice rooms, and WebRTC support.

## Features

- **User Authentication**: Registration and login system
- **Lobby Chat**: Public chat room for all users
- **Private Messaging**: Direct messages between users (with coin-based unlock system)
- **Voice Rooms**: Create and join voice chat rooms
- **WebRTC Support**: Video and voice calls between users
- **Real-time Updates**: Live status updates and message delivery

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env and set your SECRET_KEY and other configuration
   ```

5. Initialize the database:
   ```bash
   python app.py
   # This will create the database on first run
   ```

## Running the Application

### Development
```bash
export FLASK_DEBUG=True
python app.py
```

### Production
```bash
export FLASK_DEBUG=False
export SECRET_KEY=your-secure-secret-key-here
export PORT=8000
python app.py
```

Or use a production WSGI server like Gunicorn:
```bash
pip install gunicorn eventlet
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:8000 app:app
```

## Environment Variables

- `SECRET_KEY`: Flask secret key (required in production)
- `DATABASE_URL`: Database connection string (defaults to SQLite)
- `PORT`: Server port (default: 8000)
- `FLASK_DEBUG`: Enable debug mode (False in production)
- `CORS_ORIGINS`: Comma-separated list of allowed CORS origins

## Database

The application uses SQLite by default. For production, consider using PostgreSQL:

```bash
export DATABASE_URL=postgresql://user:password@localhost/dbname
```

## Security Notes

1. **Always set SECRET_KEY** in production via environment variable
2. **Set CORS_ORIGINS** to your actual domain(s) in production
3. **Disable debug mode** in production (set FLASK_DEBUG=False)
4. **Use HTTPS** in production
5. **Use a production database** (PostgreSQL recommended)

## Project Structure

```
final_chatapp/
├── app.py              # Main application file
├── models.py           # Database models
├── config.py           # Configuration
├── requirements.txt     # Python dependencies
├── templates/          # HTML templates
├── static/             # Static files (CSS, JS, images)
└── instance/           # Database and instance files
```

## API Endpoints

- `GET /` - Home page
- `GET /login` - Login page
- `POST /login` - Login endpoint
- `GET /register` - Registration page
- `POST /register` - Registration endpoint
- `GET /messenger` - Main chat interface (requires login)
- `GET /api/messages` - Get message history (requires login)
  - Query params: `room` (for lobby) or `recipient_id` (for private chat)

## Socket.IO Events

### Client → Server
- `connect` - Connect to server
- `join_room` - Join a room
- `send_message` - Send a message
- `send_coins` - Send coins to another user
- `voice_join` - Join a voice room
- `voice_leave` - Leave a voice room
- `webrtc-offer` - WebRTC offer
- `webrtc-answer` - WebRTC answer
- `webrtc-ice-candidate` - WebRTC ICE candidate

### Server → Client
- `new_message` - New message received
- `status` - User status update
- `coins_update` - Coin balance update
- `blocked_message` - Message blocked notification

## License

This project is for educational purposes.

