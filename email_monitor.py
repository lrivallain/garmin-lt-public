"""Service for monitoring Gmail inbox for Garmin LiveTrack emails."""

import threading
import time
from typing import Optional, Callable
from datetime import datetime, timezone
from gmail_client import GmailClient


class EmailMonitor:
    """Monitor Gmail inbox for new Garmin LiveTrack emails."""

    def __init__(self, gmail_client: GmailClient, check_interval: int = 30,
                 max_age_hours: int = 24):
        """Initialize email monitor.

        Args:
            gmail_client: Configured GmailClient instance
            check_interval: Seconds between email checks (default: 30)
            max_age_hours: Maximum age in hours before activity is considered stale (default: 24)
        """
        self.gmail_client = gmail_client
        self.check_interval = check_interval
        self.max_age_hours = max_age_hours
        self.current_livetrack_url: Optional[str] = None
        self.current_timestamp: Optional[datetime] = None
        self.last_email_id: Optional[str] = None
        self.callbacks = []
        self._running = False
        self._thread = None

    def add_update_callback(self, callback: Callable[[Optional[str]], None]):
        """Register a callback to be called when LiveTrack URL changes.

        Args:
            callback: Function that accepts the new LiveTrack URL
        """
        self.callbacks.append(callback)

    def start(self):
        """Start monitoring emails in a background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print("Email monitoring started")

    def stop(self):
        """Stop monitoring emails."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("Email monitoring stopped")

    def _monitor_loop(self):
        """Main monitoring loop running in background thread."""
        # Initial check
        self._check_for_updates()

        while self._running:
            time.sleep(self.check_interval)
            self._check_for_updates()

    def _check_for_updates(self):
        """Check Gmail for new LiveTrack emails and trigger callbacks if URL changed."""
        try:
            print(f"Checking for email updates...")
            email_data = self.gmail_client.get_latest_livetrack_email()

            if email_data:
                email_id = email_data['id']
                livetrack_url = email_data['livetrack_url']
                timestamp = email_data.get('timestamp')

                # Check if this is a new email or URL changed
                if email_id != self.last_email_id or livetrack_url != self.current_livetrack_url:
                    print(f"New LiveTrack URL detected: {livetrack_url}")
                    self.last_email_id = email_id
                    self.current_livetrack_url = livetrack_url
                    self.current_timestamp = timestamp

                    # Notify all registered callbacks
                    for callback in self.callbacks:
                        try:
                            callback(livetrack_url)
                        except Exception as e:
                            print(f"Error in callback: {e}")
                else:
                    print(f"Email unchanged (ID: {email_id[:10]}...)")
            else:
                # No LiveTrack email found
                print("No LiveTrack email found in inbox")
                if self.current_livetrack_url is not None:
                    print("Clearing previous URL")
                    self.current_livetrack_url = None
                    self.last_email_id = None

                    # Notify callbacks of cleared state
                    for callback in self.callbacks:
                        try:
                            callback(None)
                        except Exception as e:
                            print(f"Error in callback: {e}")

        except Exception as e:
            print(f"Error checking for email updates: {e}")

    def get_current_url(self) -> Optional[str]:
        """Get the current LiveTrack URL.

        Returns:
            Current LiveTrack URL or None if no active track
        """
        return self.current_livetrack_url

    def get_activity_status(self) -> dict:
        """Get the current activity status including age.

        Returns:
            Dictionary with url, timestamp, is_stale, and age_hours
        """
        if not self.current_livetrack_url or not self.current_timestamp:
            return {
                'url': None,
                'timestamp': None,
                'is_stale': False,
                'age_hours': None,
                'status': 'waiting'
            }

        # Calculate age
        now = datetime.now(timezone.utc)
        # Ensure timestamp is timezone-aware
        timestamp = self.current_timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        age_delta = now - timestamp
        age_hours = age_delta.total_seconds() / 3600
        is_stale = age_hours >= self.max_age_hours

        return {
            'url': self.current_livetrack_url,
            'timestamp': timestamp.isoformat(),
            'is_stale': is_stale,
            'age_hours': round(age_hours, 1),
            'status': 'last_activity' if is_stale else 'active'
        }
