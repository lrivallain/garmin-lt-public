"""Garmin LiveTrack Public Web Application.

This is a lightweight web service that reads LiveTrack state from a JSON file
written by the monitor_service.py background process. No email monitoring
happens in this process - it's purely for serving the web interface.
"""

import os
import json
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify, redirect, request, session, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.exceptions import RefreshError

# Load environment variables
load_dotenv()

app = Flask(__name__,
            static_folder='static', static_url_path='/static')

# Session secret for OAuth state management
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Session configuration for better state handling
app.config['SESSION_COOKIE_SECURE'] = False  # Allow HTTP for development
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour

# State file path (shared with monitor service)
STATE_FILE = Path(os.getenv('STATE_FILE', '/tmp/livetrack_state.json'))

# Token file path (where OAuth token is stored)
TOKEN_FILE = Path(os.getenv('GMAIL_TOKEN_FILE', '/app/config/token.json'))

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Google OAuth2 client ID file
CREDENTIALS_FILE = os.getenv('GMAIL_CREDENTIALS_FILE', 'credentials.json')

# OAuth redirect URI (explicit, can be overridden via environment)
OAUTH_REDIRECT_URI = os.getenv('OAUTH_REDIRECT_URI', None)

# Expected Gmail account (for admin access control)
EXPECTED_GMAIL_ACCOUNT = os.getenv('GMAIL_ACCOUNT', '').lower().strip()

# OAuth state file (for storing state between requests - more reliable than Flask session)
OAUTH_STATE_FILE = Path('/tmp/oauth_state.json')


def save_oauth_state(state):
    """Save OAuth state to file for verification in callback."""
    try:
        with open(OAUTH_STATE_FILE, 'w') as f:
            json.dump({'state': state}, f)
        print(f"✓ OAuth state saved to {OAUTH_STATE_FILE}", flush=True)
    except Exception as e:
        print(f"✗ Error saving OAuth state: {e}", flush=True)


def load_oauth_state():
    """Load and clear OAuth state from file."""
    try:
        if OAUTH_STATE_FILE.exists():
            with open(OAUTH_STATE_FILE, 'r') as f:
                data = json.load(f)
            # Delete file immediately after reading (one-time use)
            OAUTH_STATE_FILE.unlink()
            return data.get('state')
    except Exception as e:
        print(f"✗ Error loading OAuth state: {e}", flush=True)
    return None


def read_state():
    """Read current LiveTrack state from JSON file.

    Returns:
        Dict with current state or empty state if file doesn't exist
    """
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        else:
            return {
                'url': None,
                'timestamp': None,
                'email_id': None,
                'subject': None,
                'error': 'Monitor service not running'
            }
    except Exception as e:
        print(f"Error reading state file: {e}")
        return {
            'url': None,
            'timestamp': None,
            'email_id': None,
            'subject': None,
            'error': f'Error reading state: {e}'
        }


def calculate_activity_status(state):
    """Calculate activity status based on state and age.

    Args:
        state: Dict from read_state()

    Returns:
        Dict with url, timestamp, is_stale, age_hours, and status
    """
    url = state.get('url')
    timestamp_str = state.get('timestamp')
    max_age_hours = int(os.getenv('ACTIVITY_MAX_AGE_HOURS', '24'))
    dead_age_hours = int(os.getenv('DEAD_ACTIVITY_MAX_AGE_HOURS', '48'))

    # Parse timestamp if available
    timestamp = None
    age_hours = None
    is_stale = False
    is_dead = False

    if timestamp_str:
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            now = datetime.now(timezone.utc)
            age_hours = (now - timestamp).total_seconds() / 3600
            # Check against dead age threshold: if exceeded, return waiting status
            if age_hours > dead_age_hours:
                print("Activity age exceeds dead age threshold: returning waiting status.")
                return {
                    'url': None,
                    'timestamp': None,
                    'is_stale': False,
                    'age_hours': None,
                    'status': 'waiting'
                }
            # Check if activity is stale: beyond max age but within dead age
            is_stale = age_hours > max_age_hours
        except Exception as e:
            print(f"Error parsing timestamp: {e}")

    # Determine status
    if url and not is_stale:
        status = 'active'
    elif url and is_stale:
        print("Activity is stale: returning last_activity status.")
        status = 'last_activity'
    else:
        status = 'waiting'

    return {
        'url': url,
        'timestamp': timestamp_str,
        'is_stale': is_stale,
        'age_hours': age_hours,
        'status': status
    }


@app.route('/')
def index():
    """Serve the main page with LiveTrack iframe."""
    # No authentication required for viewing - this is public!
    app_title = os.getenv('APP_TITLE', 'Garmin LiveTrack Public')
    return render_template('index.html', app_title=app_title)


@app.route('/admin')
def admin():
    """Admin page for OAuth authentication (password protected)."""
    # Check if already authenticated
    if TOKEN_FILE.exists():
        return render_template('admin.html', authenticated=True)

    # Show login form
    error = request.args.get('error')
    return render_template('admin.html', authenticated=False, error=error)


@app.route('/admin/verify', methods=['POST'])
def admin_verify():
    """Verify admin email and start OAuth flow."""
    email = request.form.get('email', '').lower().strip()

    if not EXPECTED_GMAIL_ACCOUNT:
        return redirect(url_for('admin', error='GMAIL_ACCOUNT not configured'))

    if email != EXPECTED_GMAIL_ACCOUNT:
        return redirect(url_for('admin', error='Invalid email address'))

    # Email verified, redirect to OAuth start
    return redirect(url_for('start_oauth'))


@app.route('/login')
def login():
    """Redirect to admin page (backward compatibility)."""
    return redirect(url_for('admin'))


@app.route('/auth/start')
def start_oauth():
    """Start OAuth2 flow."""
    if not os.path.exists(CREDENTIALS_FILE):
        error_msg = f'credentials.json not found at {CREDENTIALS_FILE}'
        print(f"✗ {error_msg}", flush=True)
        return redirect(url_for('login', error=error_msg))

    try:
        print(f"OAuth redirect_uri will be: {OAUTH_REDIRECT_URI or url_for('auth_callback', _external=True)}", flush=True)

        # Validate credentials file is valid JSON and has correct format
        with open(CREDENTIALS_FILE, 'r') as f:
            creds_content = f.read()
            if not creds_content.strip():
                raise ValueError('credentials.json is empty')

            creds_data = json.loads(creds_content)

            # Check for service account (wrong type)
            if creds_data.get('type') == 'service_account':
                raise ValueError(
                    'Wrong credential type: You have a Service Account credential. '
                    'This app requires a Web Application credential. '
                    'Please create a new OAuth Client ID with type "Web application" '
                    'in Google Cloud Console (APIs & Services > Credentials).'
                )

            # Check for web apps or installed apps (both work)
            if 'web' not in creds_data and 'installed' not in creds_data:
                raise ValueError(
                    'credentials.json does not contain "web" or "installed" key. '
                    'This must be a Web Application or Desktop Application credential. '
                    'Go to Google Cloud Console > APIs & Services > Credentials, '
                    'click "Create Credentials" > "OAuth Client ID" > "Web application".'
                )

        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE,
            scopes=SCOPES,
            redirect_uri=OAUTH_REDIRECT_URI or url_for('auth_callback', _external=True)
        )

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force consent screen to always get refresh_token
        )

        # Save state to file (more reliable than Flask session in Docker)
        save_oauth_state(state)
        print(f"✓ OAuth flow started, redirecting to Google", flush=True)
        return redirect(authorization_url)

    except json.JSONDecodeError as e:
        error_msg = f'credentials.json is not valid JSON: {str(e)}'
        print(f"✗ {error_msg}", flush=True)
        return redirect(url_for('login', error=error_msg))
    except ValueError as e:
        error_msg = str(e)
        print(f"✗ {error_msg}", flush=True)
        return redirect(url_for('login', error=error_msg))
    except Exception as e:
        error_msg = f'Authentication error: {str(e)}'
        print(f"✗ Error starting OAuth flow: {e}", flush=True)
        return redirect(url_for('login', error=error_msg))


@app.route('/auth/callback')
def auth_callback():
    """Handle OAuth2 callback from Google."""
    try:
        # Verify state parameter
        request_state = request.args.get('state')
        saved_state = load_oauth_state()  # Load from file (one-time use)

        print(f"Callback received: request_state={request_state}, saved_state={saved_state}", flush=True)

        if not request_state or not saved_state:
            print(f"✗ State validation failed: request_state={request_state}, saved_state={saved_state}", flush=True)
            return jsonify({'error': 'State parameter missing or expired'}), 400

        if request_state != saved_state:
            print(f"✗ State mismatch: expected {saved_state}, got {request_state}", flush=True)
            return jsonify({'error': 'State mismatch'}), 400

        # Exchange code for credentials
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE,
            scopes=SCOPES,
            redirect_uri=OAUTH_REDIRECT_URI or url_for('auth_callback', _external=True)
        )

        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials

        # Verify we got a refresh token
        if not creds.refresh_token:
            print(f"⚠ Warning: No refresh_token received. Token may expire.", flush=True)
            # This can happen if user already authorized the app before
            # The token will still work but won't auto-refresh

        # Ensure token directory exists
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Save token
        token_data = creds.to_json()
        with open(TOKEN_FILE, 'w') as f:
            f.write(token_data)

        # Verify the saved token
        token_obj = json.loads(token_data)
        if 'refresh_token' in token_obj:
            print(f"✓ OAuth token saved to {TOKEN_FILE} (with refresh_token)", flush=True)
        else:
            print(f"✓ OAuth token saved to {TOKEN_FILE} (without refresh_token - may need re-auth later)", flush=True)

        # Notify monitor service to reload
        try:
            subprocess.run(
                ['pkill', '-HUP', '-f', 'monitor_service'],
                check=False,
                capture_output=True
            )
            print("✓ Sent HUP signal to monitor service", flush=True)
        except Exception as e:
            print(f"Warning: Could not signal monitor service: {e}", flush=True)

        # Redirect to home page
        return redirect(url_for('index'))

    except Exception as e:
        print(f"✗ OAuth callback error: {e}", flush=True)
        return jsonify({
            'error': 'Authentication failed',
            'message': str(e)
        }), 500


@app.route('/logout')
def logout():
    """Logout and delete token."""
    try:
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()
            print(f"✓ Token deleted", flush=True)

        session.clear()
        return redirect(url_for('login'))

    except Exception as e:
        print(f"✗ Error during logout: {e}", flush=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/current')
def get_current():
    """Get the current LiveTrack URL and activity status."""
    state = read_state()
    status = calculate_activity_status(state)
    return jsonify(status)


@app.route('/api/health')
def health():
    """Health check endpoint.

    Returns service status and monitor service health.
    """
    state = read_state()

    # Check if state file exists and is recent
    state_age = None
    monitor_healthy = False

    if STATE_FILE.exists():
        state_mtime = datetime.fromtimestamp(STATE_FILE.stat().st_mtime, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        state_age = (now - state_mtime).total_seconds()
        # Consider healthy if updated within last 2 check intervals
        check_interval = int(os.getenv('EMAIL_CHECK_INTERVAL', '30'))
        monitor_healthy = state_age < (check_interval * 2)

    return jsonify({
        'web_service': 'healthy',
        'monitor_service': 'healthy' if monitor_healthy else 'stale',
        'state_age_seconds': state_age,
        'state_file_exists': STATE_FILE.exists(),
        'has_activity': state.get('url') is not None
    })


@app.route('/api/reauth', methods=['POST'])
def reauth():
    """Trigger reauthentication by deleting token and redirecting to login.

    This endpoint deletes the token file and signals the monitor service
    to force re-authentication on next check.

    Returns:
        JSON response with redirect URL
    """
    try:
        # Delete token file to force re-authentication
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()
            print(f"✓ Deleted token file: {TOKEN_FILE}", flush=True)

        # Send SIGHUP to monitor service
        try:
            subprocess.run(
                ['pkill', '-HUP', '-f', 'monitor_service'],
                check=False,
                capture_output=True
            )
            print("✓ Sent HUP signal to monitor service", flush=True)
        except Exception as e:
            print(f"Warning: Could not send signal to monitor: {e}", flush=True)

        return jsonify({
            'status': 'success',
            'message': 'Reauthentication triggered. Redirecting to login...',
            'redirect_url': url_for('login')
        }), 200

    except Exception as e:
        print(f"✗ Error triggering reauthentication: {e}", flush=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


def main():
    """Run the Flask application."""
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


if __name__ == "__main__":
    main()
