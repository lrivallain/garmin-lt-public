"""Garmin LiveTrack Public Web Application.

This is a lightweight web service that reads LiveTrack state from a JSON file
written by the monitor_service.py background process. No email monitoring
happens in this process - it's purely for serving the web interface.
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify

# Load environment variables
load_dotenv()

app = Flask(__name__)

# State file path (shared with monitor service)
STATE_FILE = Path(os.getenv('STATE_FILE', '/tmp/livetrack_state.json'))


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

    # Parse timestamp if available
    timestamp = None
    age_hours = None
    is_stale = False

    if timestamp_str:
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            now = datetime.now(timezone.utc)
            age_hours = (now - timestamp).total_seconds() / 3600
            is_stale = age_hours > max_age_hours
        except Exception as e:
            print(f"Error parsing timestamp: {e}")

    # Determine status
    if url and not is_stale:
        status = 'active'
    elif url and is_stale:
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
    app_title = os.getenv('APP_TITLE', 'Garmin LiveTrack Public')
    return render_template('index.html', app_title=app_title)


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


def main():
    """Run the Flask application."""
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


if __name__ == "__main__":
    main()
