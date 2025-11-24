"""Garmin LiveTrack Public Web Application."""

import os
import queue
from dotenv import load_dotenv
from flask import Flask, render_template, Response, jsonify
from gmail_client import GmailClient
from email_monitor import EmailMonitor

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize Gmail client and email monitor
gmail_client = None
email_monitor = None

# Queue for Server-Sent Events
update_queues = []


def on_livetrack_update(url):
    """Callback when LiveTrack URL changes."""
    print(f"Broadcasting update to {len(update_queues)} clients")

    # Send update to all connected clients
    for q in update_queues[:]:  # Create copy to avoid modification during iteration
        try:
            q.put(url)
        except Exception as e:
            print(f"Error sending update to client: {e}")
            update_queues.remove(q)


@app.route('/')
def index():
    """Serve the main page with LiveTrack iframe."""
    # Get custom title from environment or use default
    app_title = os.getenv('APP_TITLE', 'Garmin LiveTrack Public')
    return render_template('index.html', app_title=app_title)


@app.route('/api/current')
def get_current():
    """Get the current LiveTrack URL and activity status."""
    if email_monitor:
        status = email_monitor.get_activity_status()
        return jsonify(status)
    else:
        return jsonify({
            'url': None,
            'timestamp': None,
            'is_stale': False,
            'age_hours': None,
            'status': 'waiting'
        })


@app.route('/api/stream')
def stream():
    """Server-Sent Events endpoint for real-time updates."""
    def event_stream():
        q = queue.Queue()
        update_queues.append(q)

        try:
            # Send initial current URL
            current_url = email_monitor.get_current_url() if email_monitor else None
            yield f"data: {current_url or ''}\n\n"

            # Stream updates
            while True:
                url = q.get()  # Block until new update
                yield f"data: {url or ''}\n\n"
        except GeneratorExit:
            # Client disconnected
            if q in update_queues:
                update_queues.remove(q)

    return Response(event_stream(), mimetype='text/event-stream')


def initialize_services():
    """Initialize Gmail client and email monitor."""
    global gmail_client, email_monitor

    try:
        # Get configuration from environment
        expected_email = os.getenv('GMAIL_ACCOUNT')
        credentials_file = os.getenv('GMAIL_CREDENTIALS_FILE', 'credentials.json')
        token_file = os.getenv('GMAIL_TOKEN_FILE', 'token.json')
        check_interval = int(os.getenv('EMAIL_CHECK_INTERVAL', '30'))
        max_age_hours = int(os.getenv('ACTIVITY_MAX_AGE_HOURS', '24'))

        # Initialize Gmail client with optional account validation
        gmail_client = GmailClient(
            credentials_file=credentials_file,
            token_file=token_file,
            expected_email=expected_email
        )

        # Initialize email monitor
        email_monitor = EmailMonitor(
            gmail_client,
            check_interval=check_interval,
            max_age_hours=max_age_hours
        )
        email_monitor.add_update_callback(on_livetrack_update)
        
        # Start monitoring
        # Note: With Gunicorn multi-worker mode, each worker will have its own monitor
        # This is acceptable as they're independent processes
        email_monitor.start()

        print(f"Services initialized successfully (PID: {os.getpid()})")
    except Exception as e:
        print(f"Error initializing services: {e}")
        raise


def main():
    """Run the Flask application."""
    # Run Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


# Initialize services when module is loaded (for both direct run and Gunicorn)
initialize_services()

if __name__ == "__main__":
    main()
