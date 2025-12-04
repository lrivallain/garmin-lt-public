"""Gmail API client for retrieving Garmin LiveTrack emails."""

import os
import base64
import re
from typing import Optional
from datetime import datetime
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class GmailClient:
    """Client for interacting with Gmail API to fetch Garmin LiveTrack emails."""

    def __init__(self, credentials_file: str = 'credentials.json', token_file: str = 'token.json',
                 expected_email: Optional[str] = None):
        """Initialize Gmail client with OAuth2 authentication.

        Args:
            credentials_file: Path to Google OAuth2 credentials JSON file
            token_file: Path to store/retrieve OAuth2 token
            expected_email: Optional email address to validate against authenticated account
        """
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.expected_email = expected_email
        self.service = None
        self.authenticated_email = None
        self.creds = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Gmail API using OAuth2."""
        creds = None

        # Load existing token if available
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
                print(f"✓ Token loaded from {self.token_file}", flush=True)
            except Exception as e:
                print(f"⚠ Could not load token file: {e}", flush=True)
                creds = None

        # If no valid credentials, try to refresh
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    print("⟳ Refreshing expired token...", flush=True)
                    creds.refresh(Request())
                    print("✓ Token refreshed successfully", flush=True)
                except RefreshError as e:
                    print(f"⚠ Token refresh failed: {e}", flush=True)
                    print("⚠ Token has expired or been revoked - waiting for re-authentication via /admin", flush=True)
                    raise Exception("Token expired - re-authentication required via /admin")
                except Exception as e:
                    print(f"⚠ Unexpected error during refresh: {e}", flush=True)
                    raise
            else:
                # No valid token - this is expected on first run or after logout
                print(f"⚠ No valid token found - waiting for authentication via /admin", flush=True)
                raise FileNotFoundError("Token not found - authenticate via /admin panel")

        # Save updated token if it was refreshed
        if creds and creds.valid:
            try:
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
                print(f"✓ Token saved to {self.token_file}", flush=True)
            except Exception as e:
                print(f"⚠ Could not save token file: {e}", flush=True)

        self.creds = creds
        self.service = build('gmail', 'v1', credentials=creds)

        # Verify authenticated email if expected_email is provided
        if self.expected_email:
            self._verify_account()

    def _verify_account(self):
        """Verify that the authenticated Gmail account matches the expected email."""
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            self.authenticated_email = profile.get('emailAddress', '').lower()

            if self.authenticated_email != self.expected_email.lower():
                raise ValueError(
                    f"Gmail account mismatch!\n"
                    f"Expected: {self.expected_email}\n"
                    f"Authenticated: {self.authenticated_email}\n"
                    f"Please delete token.json and authenticate with the correct account."
                )

            print(f"✓ Authenticated as: {self.authenticated_email}", flush=True)
        except Exception as e:
            if "Gmail account mismatch" in str(e):
                raise
            print(f"Warning: Could not verify Gmail account: {e}", flush=True)

    def get_latest_livetrack_email(self) -> Optional[dict]:
        """Fetch the most recent Garmin LiveTrack email.

        Returns:
            Dictionary with email details or None if no email found
        """
        try:
            # Search for emails from Garmin LiveTrack
            query = 'from:noreply@garmin.com subject:LiveTrack'
            print(f"Querying Gmail with: {query}", flush=True)
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=1
            ).execute()

            messages = results.get('messages', [])

            if not messages:
                print("No LiveTrack emails found", flush=True)
                return None

            # Get the most recent message
            msg_id = messages[0]['id']
            print(f"Fetching email ID: {msg_id}", flush=True)
            message = self.service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()

            return self._parse_message(message)

        except HttpError as e:
            if e.resp.status == 401:
                print(f"✗ Unauthorized (401): Token is invalid or revoked", flush=True)
            else:
                print(f"✗ HTTP Error {e.resp.status}: {e}", flush=True)
            raise
        except Exception as e:
            print(f"✗ Error fetching emails: {e}", flush=True)
            raise

    def _parse_message(self, message: dict) -> Optional[dict]:
        """Parse Gmail message to extract LiveTrack URL.

        Args:
            message: Gmail API message object

        Returns:
            Dictionary with email details including LiveTrack URL
        """
        headers = message.get('payload', {}).get('headers', [])

        # Extract subject and date
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '')

        # Parse email timestamp
        timestamp = None
        if date_str:
            try:
                timestamp = parsedate_to_datetime(date_str)
            except Exception as e:
                print(f"Warning: Could not parse email date '{date_str}': {e}", flush=True)

        # Use internal date as fallback
        if not timestamp and 'internalDate' in message:
            try:
                # internalDate is in milliseconds since epoch
                timestamp = datetime.fromtimestamp(int(message['internalDate']) / 1000)
            except Exception as e:
                print(f"Warning: Could not parse internal date: {e}", flush=True)

        # Extract email body
        body = self._get_message_body(message.get('payload', {}))

        if not body:
            return None

        # Extract LiveTrack URL
        livetrack_url = self._extract_livetrack_url(body)

        if not livetrack_url:
            return None

        return {
            'id': message['id'],
            'subject': subject,
            'date': date_str,
            'timestamp': timestamp,
            'livetrack_url': livetrack_url
        }

    def _get_message_body(self, payload: dict) -> str:
        """Extract message body from Gmail payload.

        Args:
            payload: Gmail message payload

        Returns:
            Decoded message body
        """
        body = ''

        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/html':
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(
                            part['body']['data']
                        ).decode('utf-8')
                        break
                elif part['mimeType'] == 'text/plain' and not body:
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(
                            part['body']['data']
                        ).decode('utf-8')
        else:
            if 'body' in payload and 'data' in payload['body']:
                body = base64.urlsafe_b64decode(
                    payload['body']['data']
                ).decode('utf-8')

        return body

    def _extract_livetrack_url(self, html_body: str) -> Optional[str]:
        """Extract LiveTrack URL from email body.

        Args:
            html_body: HTML content of the email

        Returns:
            LiveTrack URL or None if not found
        """
        # Parse HTML
        soup = BeautifulSoup(html_body, 'html.parser')

        # Find link with text "Afficher l'activité sur LiveTrack"
        # Also check for "View activity on LiveTrack" for English emails
        for link in soup.find_all('a'):
            link_text = link.get_text(strip=True)
            if 'LiveTrack' in link_text and ('Afficher' in link_text or 'View' in link_text):
                url = link.get('href')
                if url and 'livetrack' in url.lower():
                    return url

        # Fallback: search for LiveTrack URL in text using regex
        livetrack_pattern = r'https?://[^\s<>"]+livetrack[^\s<>"]*'
        match = re.search(livetrack_pattern, html_body, re.IGNORECASE)
        if match:
            return match.group(0)

        return None