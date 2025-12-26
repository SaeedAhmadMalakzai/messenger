from datetime import datetime, timedelta
import os
from functools import wraps
from dotenv import load_dotenv

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect

# Load environment variables from .env file
load_dotenv()

from config import Config
from models import db, User, Message, VoiceRoom, VoiceParticipant, CoinTransaction, DMUnlock, VoiceComment

MAX_STAGE = 10               # voice-room speakers cap
DM_FREE_MSG_LIMIT = 3        # free msgs without reply

def create_app():
    app = Flask(__name__, instance_relative_config=True,
                static_folder='static', template_folder='templates')
    app.config.from_object(Config)
    os.makedirs(app.instance_path, exist_ok=True)
    
    # Fix database URI to use absolute path (Flask's instance_relative_config can cause issues)
    # This must be done BEFORE db.init_app()
    if not os.environ.get("DATABASE_URL"):
        db_path = os.path.join(app.instance_path, "chat.db")
        db_path = os.path.abspath(db_path).replace("\\", "/")
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"

    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        flash("Please log in to access this page.", "error")
        return redirect(url_for("login"))

    socketio = SocketIO(app,
                        cors_allowed_origins=app.config.get("SOCKETIO_CORS_ALLOWED_ORIGINS"),
                        async_mode="threading",
                        manage_session=True,
                        logger=True,
                        engineio_logger=True)
    
    # Add global exception handler for Socket.IO
    @socketio.on_error_default
    def default_error_handler(e):
        print(f"❌ Socket.IO error: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ---------------- ROUTES ----------------
    # Health check endpoint for Render
    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "healthy"}), 200

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("messenger"))
        return render_template("index.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        # Already logged in?
        if current_user.is_authenticated and request.method == "GET":
            return redirect(url_for("messenger"))

        if request.method == "POST":
            # force logout stale sessions
            if current_user.is_authenticated:
                logout_user()

            try:
                username = (request.form.get("username") or "").strip()
                password = (request.form.get("password") or "").strip()
                
                if not username or not password:
                    flash("Username and password required.", "error")
                    return render_template("login.html"), 400
                
                user = User.query.filter_by(username=username).first()

                if user and check_password_hash(user.password_hash, password):
                    login_user(user, remember=True)
                    user.status = "online"
                    db.session.commit()
                    return redirect(url_for("messenger"))

                flash("Invalid username or password.", "error")
                return render_template("login.html"), 401
            except Exception as e:
                db.session.rollback()
                flash("An error occurred. Please try again.", "error")
                return render_template("login.html"), 500

        return render_template("login.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            try:
                username = (request.form.get("username") or '').strip()
                password = (request.form.get("password") or '').strip()

                if not username or not password:
                    flash("Username and password required.", "error")
                    return render_template("register.html"), 400

                if len(username) < 3:
                    flash("Username must be at least 3 characters long.", "error")
                    return render_template("register.html"), 400

                if len(password) < 6:
                    flash("Password must be at least 6 characters long.", "error")
                    return render_template("register.html"), 400

                if User.query.filter_by(username=username).first():
                    flash("Username already exists.", "error")
                    return render_template("register.html"), 409

                user = User(username=username,
                            password_hash=generate_password_hash(password))
                db.session.add(user)
                db.session.commit()
                flash("User registered, log in.", "success")
                return redirect(url_for("login"))
            except Exception as e:
                db.session.rollback()
                flash("An error occurred during registration. Please try again.", "error")
                return render_template("register.html"), 500

        return render_template("register.html")

    @app.route("/messenger")
    @login_required
    def messenger():
        users = User.query.filter(User.id != current_user.id).all()
        rooms = VoiceRoom.query.filter_by(active=True).all()
        return render_template("messenger.html", users=users, me=current_user, rooms=rooms)

    @app.route("/voice-rooms")
    @login_required
    def voice_rooms():
        rooms = VoiceRoom.query.filter_by(active=True).all()
        return render_template("voice_rooms.html", rooms=rooms, me=current_user)

    @app.route("/api/rooms/create", methods=["POST"])
    @login_required
    def api_create_room():
        data = request.get_json() or {}
        name = (data.get("name") or "Room").strip() or "Room"
        room = VoiceRoom(name=name, created_by=current_user.id)
        db.session.add(room)
        db.session.commit()
        vp = VoiceParticipant(room_id=room.id,
                              user_id=current_user.id,
                              role="host")
        db.session.add(vp)
        db.session.commit()
        return jsonify({"id": room.id, "name": room.name})

    @app.route("/api/messages")
    @login_required
    def api_messages():
        """Get messages for lobby or private chat"""
        room = request.args.get("room")
        recipient_id = request.args.get("recipient_id", type=int)
        
        query = Message.query
        if room:
            query = query.filter_by(room=room)
        elif recipient_id:
            # Get messages between current_user and recipient
            query = query.filter(
                ((Message.sender_id == current_user.id) & (Message.recipient_id == recipient_id)) |
                ((Message.sender_id == recipient_id) & (Message.recipient_id == current_user.id))
            )
        else:
            return jsonify({"error": "room or recipient_id required"}), 400
        
        messages = query.order_by(Message.created_at.asc()).limit(100).all()
        result = []
        for msg in messages:
            sender = User.query.get(msg.sender_id)
            result.append({
                "id": msg.id,
                "body": msg.body,
                "sender_id": msg.sender_id,
                "sender_username": sender.username if sender else "Unknown",
                "recipient_id": msg.recipient_id,
                "room": msg.room,
                "created_at": msg.created_at.isoformat()
            })
        return jsonify(result)

    @app.route("/logout")
    @login_required
    def logout():
        try:
            current_user.status = "offline"
            db.session.commit()
        except Exception as e:
            db.session.rollback()
        logout_user()
        return redirect(url_for("login"))

    # ---------------- HELPERS ----------------
    def dm_allowed(sender_id, recipient_id):
        """Return True if sender can DM recipient without coins (<=3 msgs since last reply)."""
        unlock = DMUnlock.query.filter_by(user_id=sender_id,
                                          target_id=recipient_id).first()
        if unlock and (not unlock.expires_at or unlock.expires_at > datetime.utcnow()):
            return True

        last_reply = (Message.query
                      .filter_by(sender_id=recipient_id, recipient_id=sender_id)
                      .order_by(Message.created_at.desc())
                      .first())
        since = last_reply.created_at if last_reply else datetime.min

        count = (Message.query
                 .filter(Message.sender_id == sender_id,
                         Message.recipient_id == recipient_id,
                         Message.created_at > since)
                 .count())
        return count < DM_FREE_MSG_LIMIT

    # ---------------- SOCKET.IO ----------------
    def authenticated_only(f):
        """Decorator to ensure user is authenticated in socket handlers"""
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                disconnect()
                return False
            return f(*args, **kwargs)
        return wrapped

    @socketio.on("connect")
    def sio_connect(auth):
        """Handle Socket.IO connection with proper authentication"""
        try:
            # Debug: Print session contents
            print(f"Connect attempt - Session keys: {list(session.keys())}")
            print(f"Connect attempt - current_user: {current_user}")
            print(f"Connect attempt - current_user.is_authenticated: {getattr(current_user, 'is_authenticated', False)}")
            
            user_id = None
            
            # Try multiple ways to get user ID
            # Flask-Login uses '_user_id' by default, but check all possibilities
            if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
                user_id = current_user.id
                print(f"Got user_id from current_user: {user_id}")
            elif '_user_id' in session:
                user_id = session['_user_id']
                print(f"Got user_id from session['_user_id']: {user_id}")
            elif 'user_id' in session:
                user_id = session['user_id']
                print(f"Got user_id from session['user_id']: {user_id}")
            elif '_id' in session:
                user_id = session['_id']
                print(f"Got user_id from session['_id']: {user_id}")
            
            if user_id:
                try:
                    user_id = int(user_id)
                except (ValueError, TypeError):
                    print(f"Invalid user_id: {user_id}")
                    # Allow connection anyway, auth will be checked in handlers
                    join_room("lobby")
                    return True
                
                user = User.query.get(user_id)
                if user:
                    # Ensure user is logged in for this context
                    if not hasattr(current_user, 'is_authenticated') or not current_user.is_authenticated:
                        login_user(user, remember=True)
                    
                    join_room(str(user_id))
                    join_room("lobby")
                    try:
                        user.status = "online"
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                        print(f"Error updating user status: {e}")
                    
                    emit("status", {"user_id": user_id, "status": "online"},
                         broadcast=True)
                    print(f"✅ User {user_id} ({user.username}) connected to Socket.IO")
                    return True
                else:
                    print(f"⚠️ User {user_id} not found in database - allowing connection")
                    # Allow connection, will check auth in message handlers
                    join_room("lobby")
                    return True
            else:
                print("⚠️ No authenticated user found - allowing connection (auth checked in handlers)")
                # Allow connection even without auth - will check in message handlers
                join_room("lobby")
                return True
        except Exception as e:
            print(f"❌ Error in connect handler: {e}")
            import traceback
            traceback.print_exc()
            # Allow connection for debugging
            return True

    @socketio.on("disconnect")
    def sio_disconnect():
        try:
            user_id = None
            if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
                user_id = current_user.id
            elif '_user_id' in session:
                try:
                    user_id = int(session['_user_id'])
                except (ValueError, TypeError, KeyError):
                    pass
            
            if user_id:
                try:
                    user = User.query.get(user_id)
                    if user:
                        user.status = "offline"
                        db.session.commit()
                        emit("status", {"user_id": user_id, "status": "offline"},
                             broadcast=True)
                except Exception as e:
                    db.session.rollback()
                    print(f"Error in disconnect handler: {e}")
        except Exception as e:
            print(f"Error in disconnect handler: {e}")
            import traceback
            traceback.print_exc()

    @socketio.on("join_room")
    def sio_join_room(data):
        try:
            room = data.get("room") if data else None
            if room:
                join_room(room)
        except Exception as e:
            print(f"Error in join_room handler: {e}")
            import traceback
            traceback.print_exc()

    @socketio.on("send_message")
    def sio_send_message(data):
        """Handle message sending - allow even without strict auth for debugging"""
        try:
            # Get user ID from session or current_user
            sender_id = None
            if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
                sender_id = current_user.id
            elif '_user_id' in session:
                try:
                    sender_id = int(session['_user_id'])
                except (ValueError, TypeError, KeyError):
                    sender_id = None
            elif 'user_id' in session:
                try:
                    sender_id = int(session['user_id'])
                except (ValueError, TypeError, KeyError):
                    sender_id = None
            
            if not sender_id:
                print("❌ No sender_id found in send_message")
                emit("blocked_message", {"reason": "Not authenticated."}, room=request.sid)
                return
            
            body = (data.get("body") or "").strip()
            recipient_id = data.get("recipient_id")
            room = data.get("room")

            if not body:
                return

            print(f"📨 Message from user {sender_id}: {body[:50]}... (room={room}, recipient={recipient_id})")

            # DM gate
            if recipient_id and not dm_allowed(sender_id, recipient_id):
                emit("blocked_message",
                     {"reason": "You must receive a response or send coins to unlock."},
                     room=str(sender_id))
                return

            msg = Message(body=body,
                          sender_id=sender_id,
                          recipient_id=recipient_id,
                          room=room)
            db.session.add(msg)
            db.session.commit()

            sender = User.query.get(sender_id)
            payload = {
                "id": msg.id,
                "body": msg.body,
                "sender_id": msg.sender_id,
                "sender_username": sender.username if sender else "Unknown",
                "recipient_id": msg.recipient_id,
                "room": msg.room,
                "created_at": msg.created_at.isoformat()
            }

            print(f"📤 Emitting message: {payload}")

            if room:
                # Lobby message - send to all in lobby room
                emit("new_message", payload, to=room)
                print(f"✅ Sent to room: {room}")
            elif recipient_id:
                # Private message - send to both users
                emit("new_message", payload, room=str(recipient_id))
                emit("new_message", payload, room=str(sender_id))
                print(f"✅ Sent to users: {recipient_id} and {sender_id}")
            else:
                # Default to lobby
                emit("new_message", payload, to="lobby")
                print(f"✅ Sent to lobby")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error sending message: {e}")
            import traceback
            traceback.print_exc()
            emit("blocked_message", {"reason": "Error sending message."}, room=request.sid)

    @socketio.on("send_coins")
    @authenticated_only
    def sio_send_coins(data):
        to_id = data.get("to")
        amount = int(data.get("amount", 0))

        if amount <= 0:
            return

        try:
            if current_user.coins < amount:
                emit("blocked_message", {"reason": "Not enough coins."},
                     room=str(current_user.id))
                return

            recipient = User.query.get(to_id)
            if not recipient:
                emit("blocked_message", {"reason": "User not found."},
                     room=str(current_user.id))
                return

            current_user.coins -= amount
            recipient.coins += amount
            tx = CoinTransaction(from_id=current_user.id,
                                 to_id=recipient.id,
                                 amount=amount,
                                 note="gift")
            db.session.add(tx)

            unlock = DMUnlock.query.filter_by(user_id=current_user.id,
                                              target_id=recipient.id).first()
            if not unlock:
                unlock = DMUnlock(user_id=current_user.id,
                                  target_id=recipient.id,
                                  expires_at=datetime.utcnow() + timedelta(days=30))
                db.session.add(unlock)
            else:
                unlock.expires_at = datetime.utcnow() + timedelta(days=30)

            db.session.commit()
            emit("coins_update",
                 {"user_id": current_user.id, "coins": current_user.coins},
                 room=str(current_user.id))
            emit("coins_update",
                 {"user_id": recipient.id, "coins": recipient.coins},
                 room=str(recipient.id))
        except Exception as e:
            db.session.rollback()
            emit("blocked_message", {"reason": "Error sending coins."}, room=str(current_user.id))

    # Lobby voice invite (optional quick group call hook)
    @socketio.on("lobby_voice_invite")
    @authenticated_only
    def sio_lobby_voice_invite():
        emit("lobby_voice_invite", {"from": current_user.id},
             to="lobby", skip_sid=request.sid)

    # Voice room join/leave
    @socketio.on("voice_join")
    @authenticated_only
    def sio_voice_join(data):
        room_id = data.get("room_id")
        room_name = f"voice_{room_id}"
        join_room(room_name)

        try:
            vp = VoiceParticipant.query.filter_by(room_id=room_id,
                                                  user_id=current_user.id).first()
            if not vp:
                vp = VoiceParticipant(room_id=room_id,
                                      user_id=current_user.id,
                                      role="listener")
                db.session.add(vp)
                db.session.commit()

            emit("voice_user_joined",
                 {"user_id": current_user.id, "role": vp.role},
                 to=room_name)
        except Exception as e:
            db.session.rollback()
            emit("blocked_message", {"reason": "Error joining voice room."}, room=str(current_user.id))

    @socketio.on("voice_leave")
    @authenticated_only
    def sio_voice_leave(data):
        room_id = data.get("room_id")
        room_name = f"voice_{room_id}"
        leave_room(room_name)

        try:
            VoiceParticipant.query.filter_by(room_id=room_id,
                                             user_id=current_user.id).delete()
            db.session.commit()
            emit("voice_user_left", {"user_id": current_user.id}, to=room_name)
        except Exception as e:
            db.session.rollback()

    @socketio.on("voice_request_stage")
    @authenticated_only
    def sio_voice_request_stage(data):
        room_id = data.get("room_id")
        host_ids = [p.user_id for p in
                    VoiceParticipant.query.filter_by(room_id=room_id, role="host").all()]
        for hid in host_ids:
            emit("voice_stage_request",
                 {"from": current_user.id, "room_id": room_id},
                 room=str(hid))

    @socketio.on("voice_stage_decision")
    @authenticated_only
    def sio_voice_stage_decision(data):
        room_id = data.get("room_id")
        target_id = data.get("user_id")
        accept = data.get("accept", False)
        room_name = f"voice_{room_id}"

        try:
            if accept:
                speakers = VoiceParticipant.query.filter_by(room_id=room_id, role="speaker").count()
                if speakers >= MAX_STAGE:
                    emit("voice_stage_full", {}, room=str(target_id))
                    return

                vp = VoiceParticipant.query.filter_by(room_id=room_id, user_id=target_id).first()
                if vp:
                    vp.role = "speaker"
                    db.session.commit()

                emit("voice_stage_granted", {"user_id": target_id}, to=room_name)
            else:
                emit("voice_stage_denied", {"user_id": target_id}, room=str(target_id))
        except Exception as e:
            db.session.rollback()

    @socketio.on("voice_comment")
    @authenticated_only
    def sio_voice_comment(data):
        room_id = data.get("room_id")
        body = (data.get("body") or "").strip()
        if not body:
            return

        try:
            vc = VoiceComment(room_id=room_id, user_id=current_user.id, body=body)
            db.session.add(vc)
            db.session.commit()

            emit("voice_comment",
                 {"user_id": current_user.id, "body": body},
                 to=f"voice_{room_id}")
        except Exception as e:
            db.session.rollback()

    # -------------- WebRTC signaling --------------
    @socketio.on("webrtc-offer")
    @authenticated_only
    def sio_offer(data):
        emit("webrtc-offer",
             {"from": current_user.id, "offer": data["offer"], "room_id": data.get("room_id")},
             room=str(data["to"]))

    @socketio.on("webrtc-answer")
    @authenticated_only
    def sio_answer(data):
        emit("webrtc-answer",
             {"from": current_user.id, "answer": data["answer"], "room_id": data.get("room_id")},
             room=str(data["to"]))

    @socketio.on("webrtc-ice-candidate")
    @authenticated_only
    def sio_ice(data):
        emit("webrtc-ice-candidate",
             {"from": current_user.id, "candidate": data["candidate"], "room_id": data.get("room_id")},
             room=str(data["to"]))

    return app, socketio


if __name__ == "__main__":
    app, socketio = create_app()
    
    # Ensure instance directory exists and is writable
    instance_path = app.instance_path
    os.makedirs(instance_path, exist_ok=True)
    
    # Set proper permissions (Unix-like systems)
    if os.name != 'nt':  # Not Windows
        try:
            os.chmod(instance_path, 0o755)
        except Exception:
            pass  # Ignore permission errors if we can't set them
    
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"Error creating database: {e}")
            print(f"Database path: {app.config['SQLALCHEMY_DATABASE_URI']}")
            print(f"Instance path: {instance_path}")
            raise
    
    # Use environment variable for debug mode (set to False in production)
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=debug_mode)
