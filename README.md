# 🏃 Garmin LiveTrack Public

A self-hosted web application that provides a permanent, public view of your Garmin LiveTrack activities. Unlike Garmin's default LiveTrack feature which generates a new link for each activity, this app maintains a single URL that automatically updates when you start a new activity.

## ✨ Features

- **Permanent Public URL**: Share one URL that always shows your latest LiveTrack activity
- **Real-time Updates**: Connected browsers automatically refresh when a new activity starts
- **Gmail Integration**: Automatically retrieves LiveTrack links from Garmin notification emails
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Zero Configuration for Viewers**: Just share the URL, no setup needed for people watching

## 🎯 How It Works

1. Configure Garmin to send LiveTrack emails to a dedicated Gmail account
2. The app monitors this Gmail account for new LiveTrack notifications
3. When a new activity starts, it extracts the LiveTrack URL
4. All connected web browsers are automatically updated via Server-Sent Events (SSE)
5. The iframe updates to show your live activity on the map

## 📋 Prerequisites

- Python 3.11 or higher
- A Gmail account dedicated to receiving Garmin LiveTrack emails
- Google Cloud Project with Gmail API enabled
- Garmin device with LiveTrack feature

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd garmin-livetrack-public
```

### 2. Install Dependencies

Using `uv` (recommended):

```bash
uv sync
```

### 3. Set Up Gmail API

#### 3.1 Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Gmail API** for your project:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Gmail API"
   - Click "Enable"

#### 3.2 Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. Choose "Desktop app" as the application type
4. Download the credentials JSON file
5. Save it as `credentials.json` in the project root directory

### 4. Configure Garmin LiveTrack

1. Log in to your Garmin Connect account
2. Go to Settings > LiveTrack
3. Add the dedicated Gmail address to your LiveTrack contacts
4. Ensure email notifications are enabled for LiveTrack activities

### 5. Configure Environment (Optional)

Copy the example environment file and customize if needed:

```bash
cp .env.example .env
```

Edit `.env` to customize:

- **`PORT`**: Web server port (default: 5000)
- **`APP_TITLE`**: Custom title for your LiveTrack page (default: "Garmin LiveTrack Public")
  - Examples: "John's LiveTrack", "Family Tracker", "Marathon Watch"
  - Appears in the browser tab and page header
- **`GMAIL_ACCOUNT`**: Email address that receives LiveTrack emails (recommended)
  - If set, the app verifies the authenticated Gmail account matches this email
  - Prevents accidentally using the wrong Gmail account
  - Leave empty to skip validation
- **`EMAIL_CHECK_INTERVAL`**: Seconds between Gmail checks (default: 30)
- **`ACTIVITY_MAX_AGE_HOURS`**: Hours before activity is marked as "Last activity" (default: 24)
  - Activities older than this are shown with "Last activity" status instead of "Activity in progress"
  - Helps distinguish current activities from old ones
  - Set higher (e.g., 48) if you want longer activity display
- **`GMAIL_CREDENTIALS_FILE`**: Path to OAuth credentials (default: credentials.json)
- **`GMAIL_TOKEN_FILE`**: Path to auth token (default: token.json)

**For detailed configuration options, see [CONFIGURATION.md](CONFIGURATION.md)**

## 🏃‍♂️ Running the Application

### First Run (Authentication)

The first time you run the app, it will open a browser window for Gmail authentication:

```bash
python main.py
```

1. Select your Gmail account
2. Click "Allow" to grant read access to your Gmail
3. The authentication token will be saved as `token.json`

### Subsequent Runs

After initial authentication, simply run:

```bash
python main.py
```

The application will be available at `http://localhost:5000` (or your configured port).

## 🌐 Accessing the Web Interface

- **Local Access**: `http://localhost:5000`
- **Network Access**: `http://<your-ip>:5000`
- **Public Access**: Use a reverse proxy (nginx, Caddy) or tunnel service (ngrok, Cloudflare Tunnel)

## 🔧 Architecture

```
┌─────────────────┐
│  Garmin Device  │
└────────┬────────┘
         │ Sends LiveTrack email
         ▼
┌─────────────────┐
│  Gmail Account  │
└────────┬────────┘
         │
         │ Gmail API
         ▼
┌─────────────────┐      ┌──────────────────┐
│  Email Monitor  │─────▶│  Flask Web App   │
│  (Background)   │      │  (Server-Sent    │
└─────────────────┘      │   Events)        │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   Web Browsers   │
                         │  (Auto-refresh)  │
                         └──────────────────┘
```

### Components

- **`main.py`**: Flask web application with SSE support
- **`gmail_client.py`**: Gmail API integration for email retrieval
- **`email_monitor.py`**: Background service monitoring for new LiveTrack emails
- **`templates/index.html`**: Responsive frontend with auto-updating iframe

## 🔒 Security Considerations

- **Gmail Credentials**: Never commit `credentials.json` or `token.json` to version control
- **Dedicated Account**: Use a dedicated Gmail account only for LiveTrack notifications
- **Read-Only Access**: The app only requires Gmail read permissions
- **HTTPS**: Use HTTPS in production (via reverse proxy)
- **Authentication**: Consider adding authentication for public deployments

## 🐳 Deployment

### Docker Compose (Recommended)

```bash
docker-compose up -d
```

### Docker

```bash
docker build -t garmin-livetrack-public .
docker run -p 5000:5000 -v $(pwd)/credentials.json:/app/config/credentials.json -v $(pwd)/token.json:/app/config/token.json garmin-livetrack-public
```

## 🛠️ Troubleshooting

### No LiveTrack URL Detected

- Verify emails are being sent to the configured Gmail account
- Check that emails are from `noreply@garmin.com`
- Ensure the email contains the LiveTrack link
- Check application logs for parsing errors

### Authentication Issues

- Delete `token.json` and re-authenticate
- Verify `credentials.json` is valid
- Ensure Gmail API is enabled in Google Cloud Console

### Browser Not Updating

- Check browser console for EventSource errors
- Verify the `/api/stream` endpoint is accessible
- Try refreshing the browser page

## 📝 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📧 Support

For issues and questions, please open a GitHub issue.
