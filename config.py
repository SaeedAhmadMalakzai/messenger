import os
BASEDIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # SECRET_KEY should be set via environment variable in production
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(32).hex()
    
    # Ensure instance directory exists
    INSTANCE_DIR = os.path.join(BASEDIR, "instance")
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    
    # Use absolute path for database - SQLite with 3 slashes needs absolute path
    # When Flask uses instance_relative_config, we need to ensure absolute path
    _db_path = os.path.abspath(os.path.join(INSTANCE_DIR, "chat.db"))
    # Normalize path separators for SQLite URI (use forward slashes)
    _db_path = _db_path.replace("\\", "/")  # Windows compatibility
    
    # If DATABASE_URL is not set, use absolute path
    # SQLite URI format: sqlite:///absolute/path (3 slashes for absolute)
    default_db_uri = f"sqlite:///{_db_path}"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or default_db_uri
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # In production, set this to your actual domain(s)
    # Handle CORS_ORIGINS: "*" means allow all, otherwise split by comma
    cors_origins_env = os.environ.get("CORS_ORIGINS", "*")
    if cors_origins_env == "*":
        SOCKETIO_CORS_ALLOWED_ORIGINS = "*"  # Allow all origins
    else:
        SOCKETIO_CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins_env.split(",")]
    TEMPLATES_AUTO_RELOAD = True
