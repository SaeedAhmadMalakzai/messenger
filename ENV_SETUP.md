# How to Set Environment Variables

There are two main ways to set environment variables for this application:

## Method 1: Using a `.env` File (Recommended for Development)

1. **Create a `.env` file** in the project root directory (`/Users/saeedahmadmalakzai/messenger/final_chatapp/`)

2. **Add the following content** to the `.env` file:

```bash
# Flask Configuration
# Generate a secure secret key: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=change-this-to-a-secure-random-key-in-production

# Debug Mode (set to False in production)
FLASK_DEBUG=True

# Database Configuration
# For SQLite (default):
DATABASE_URL=sqlite:///instance/chat.db
# For PostgreSQL (production):
# DATABASE_URL=postgresql://user:password@localhost/dbname

# Server Configuration
PORT=8000

# CORS Configuration (comma-separated list of allowed origins)
# For development, use * to allow all origins
# For production, specify your domain: https://yourdomain.com
CORS_ORIGINS=*
```

3. **Generate a secure SECRET_KEY** (optional but recommended):
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
   Copy the output and replace `change-this-to-a-secure-random-key-in-production` in your `.env` file.

4. **The app will automatically load** the `.env` file when you run it (python-dotenv is already installed).

## Method 2: Export in Terminal (For Current Session)

### macOS/Linux (zsh/bash):

```bash
# Set individual variables
export SECRET_KEY="your-secret-key-here"
export FLASK_DEBUG=False
export PORT=8000
export CORS_ORIGINS="https://yourdomain.com"

# Or set all at once
export SECRET_KEY="your-secret-key-here" FLASK_DEBUG=False PORT=8000 CORS_ORIGINS="*"
```

### To make it permanent (add to your shell profile):

1. **For zsh** (default on macOS):
   ```bash
   echo 'export SECRET_KEY="your-secret-key-here"' >> ~/.zshrc
   echo 'export FLASK_DEBUG=False' >> ~/.zshrc
   echo 'export PORT=8000' >> ~/.zshrc
   source ~/.zshrc
   ```

2. **For bash**:
   ```bash
   echo 'export SECRET_KEY="your-secret-key-here"' >> ~/.bash_profile
   echo 'export FLASK_DEBUG=False' >> ~/.bash_profile
   echo 'export PORT=8000' >> ~/.bash_profile
   source ~/.bash_profile
   ```

## Method 3: Set in Production (Hosting Platforms)

### For Heroku:
```bash
heroku config:set SECRET_KEY="your-secret-key"
heroku config:set FLASK_DEBUG=False
heroku config:set PORT=8000
```

### For DigitalOcean App Platform:
Add environment variables in the App Settings → Environment Variables section.

### For AWS/EC2:
Add to your systemd service file or use AWS Systems Manager Parameter Store.

### For Docker:
Add to your `docker-compose.yml`:
```yaml
environment:
  - SECRET_KEY=your-secret-key
  - FLASK_DEBUG=False
  - PORT=8000
```

## Quick Start

1. **Create `.env` file**:
   ```bash
   cd /Users/saeedahmadmalakzai/messenger/final_chatapp
   cat > .env << 'EOF'
   SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
   FLASK_DEBUG=True
   PORT=8000
   CORS_ORIGINS=*
   DATABASE_URL=sqlite:///instance/chat.db
   EOF
   ```

2. **Or manually create** the file and copy the template above.

3. **Run your app** - it will automatically load the `.env` file!

## Important Notes

- **Never commit `.env` to git** - it's already in `.gitignore`
- **Use different SECRET_KEY for production** - generate a new one
- **Set FLASK_DEBUG=False in production** - for security
- **Set CORS_ORIGINS to your actual domain** in production

## Verify Environment Variables

To check if your environment variables are set:

```bash
# Check all Flask-related env vars
env | grep -E "SECRET_KEY|FLASK_DEBUG|PORT|CORS_ORIGINS|DATABASE_URL"

# Or in Python
python3 -c "import os; print('SECRET_KEY:', os.environ.get('SECRET_KEY', 'Not set'))"
```

