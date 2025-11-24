#!/usr/bin/env python3
"""Background service that monitors Gmail for LiveTrack emails.

This service runs independently and writes the current state to a JSON file
that the web app can read without any blocking operations.
"""

import os
import sys
import json
import time
import signal
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from gmail_client import GmailClient

# Load environment variables
load_dotenv()

# State file path
STATE_FILE = Path(os.getenv('STATE_FILE', '/tmp/livetrack_state.json'))

# Global flag for graceful shutdown
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global running
    print(f"\nReceived signal {signum}, shutting down gracefully...", flush=True)
    running = False


def save_state(email_data=None, error=None):
    """Save current LiveTrack state to JSON file.

    Args:
        email_data: Dict with email details or None
        error: Error message if any
    """
    state = {
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'url': None,
        'timestamp': None,
        'email_id': None,
        'subject': None,
        'error': error
    }

    if email_data:
        state.update({
            'url': email_data.get('livetrack_url'),
            'timestamp': email_data.get('timestamp').isoformat() if email_data.get('timestamp') else None,
            'email_id': email_data.get('id'),
            'subject': email_data.get('subject')
        })

    try:
        # Atomic write using temp file + rename
        temp_file = STATE_FILE.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(state, f, indent=2)
        temp_file.replace(STATE_FILE)
        print(f"✓ State updated: {state['url'] if state['url'] else 'No activity'}", flush=True)
    except Exception as e:
        print(f"✗ Error saving state: {e}", file=sys.stderr, flush=True)


def monitor_loop(gmail_client, check_interval):
    """Main monitoring loop.

    Args:
        gmail_client: Configured GmailClient instance
        check_interval: Seconds between checks
    """
    last_email_id = None

    print(f"Starting email monitoring (check interval: {check_interval}s)", flush=True)
    print(f"State file: {STATE_FILE}", flush=True)
    print("-" * 60, flush=True)

    while running:
        try:
            print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Checking for emails...", flush=True)
            email_data = gmail_client.get_latest_livetrack_email()

            if email_data:
                email_id = email_data['id']

                # Check if this is a new email
                if email_id != last_email_id:
                    print(f"📧 New email detected:", flush=True)
                    print(f"   Subject: {email_data.get('subject')}", flush=True)
                    print(f"   URL: {email_data.get('livetrack_url')}", flush=True)
                    print(f"   Time: {email_data.get('timestamp')}", flush=True)
                    last_email_id = email_id
                else:
                    print(f"   Email unchanged (ID: {email_id[:10]}...)", flush=True)

                # Update state file
                save_state(email_data)
            else:
                print("   No LiveTrack emails found", flush=True)
                # Clear state if no email found
                if last_email_id is not None:
                    print("   Clearing previous state", flush=True)
                    last_email_id = None
                save_state()

        except Exception as e:
            error_msg = f"Error checking emails: {e}"
            print(f"✗ {error_msg}", file=sys.stderr, flush=True)
            save_state(error=error_msg)

        # Sleep until next check
        if running:
            time.sleep(check_interval)

    print("\nMonitoring stopped", flush=True)


def main():
    """Initialize and run the email monitoring service."""
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("=" * 60, flush=True)
    print("Garmin LiveTrack Email Monitor Service", flush=True)
    print("=" * 60, flush=True)

    # Get configuration
    expected_email = os.getenv('GMAIL_ACCOUNT')
    credentials_file = os.getenv('GMAIL_CREDENTIALS_FILE', 'credentials.json')
    token_file = os.getenv('GMAIL_TOKEN_FILE', 'token.json')
    check_interval = int(os.getenv('EMAIL_CHECK_INTERVAL', '30'))

    print(f"Configuration:", flush=True)
    print(f"  Gmail account: {expected_email}", flush=True)
    print(f"  Credentials: {credentials_file}", flush=True)
    print(f"  Token: {token_file}", flush=True)
    print(f"  Check interval: {check_interval}s", flush=True)
    print(f"  State file: {STATE_FILE}", flush=True)
    print("-" * 60, flush=True)

    # Ensure state directory exists
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Initialize with empty state
    save_state()

    try:
        print("Initializing Gmail client...", flush=True)
        gmail_client = GmailClient(
            credentials_file=credentials_file,
            token_file=token_file,
            expected_email=expected_email
        )
        print("✓ Gmail client initialized", flush=True)
        print("-" * 60, flush=True)

        # Run monitoring loop
        monitor_loop(gmail_client, check_interval)

    except KeyboardInterrupt:
        print("\nShutdown requested", flush=True)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}", file=sys.stderr, flush=True)
        save_state(error=str(e))
        sys.exit(1)

    print("Service stopped", flush=True)


if __name__ == "__main__":
    main()
