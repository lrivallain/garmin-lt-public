# 🏃 Garmin LiveTrack Public

A self-hosted web application that provides a permanent, public view of your Garmin LiveTrack activities.

## ✨ Key Features

- **Public Access**: Anyone can view your live activity - no authentication required
- **Single Permanent URL**: One link that always shows your latest activity
- **Real-time Updates**: Automatic frontend refresh when activity detected
- **Responsive Design**: Works on all devices

## 📁 Project Structure

```
garmin-livetrack-public/
├── monitor/                # Email monitoring service
│   ├── monitor_service.py  # Main daemon
│   ├── gmail_client.py     # Gmail API wrapper
│   ├── Dockerfile
│   └── README.md
├── web/                    # Web frontend service
│   ├── main.py             # Flask application
│   ├── healthcheck.py      # Health check script
│   ├── templates/
│   │   ├── index.html      # Public LiveTrack view
│   │   └── admin.html      # Admin authentication panel
│   ├── Dockerfile
│   └── README.md
├── docker-compose.yml      # Production configuration
└── README.md               # This file
```


## 🚀 Quick Start

### 1. Prerequisites

- Docker and Docker Compose
- Gmail account for LiveTrack notifications
- Google Cloud Project with Gmail API enabled

### 2. Create OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable **Gmail API**: APIs & Services → Library → "Gmail API" → Enable
4. Create OAuth Client ID:
   - APIs & Services → Credentials → Create Credentials → OAuth Client ID
   - Application Type: **Web application**
   - Add Authorized redirect URIs:
     - Development: `http://localhost:5000/auth/callback`
     - Production: `https://your-domain.com/auth/callback`
   - Download JSON → save as `credentials.json` in project root

### 3. Configure Environment

Edit `docker-compose.yml` for production):

```yaml
environment:
  - GMAIL_ACCOUNT=your-livetrack@gmail.com  # Your Gmail account
  - OAUTH_REDIRECT_URI=http://localhost:5000/auth/callback
  - FLASK_SECRET_KEY=change-me-to-random-value
```

### 4. Start Services

```bash
# Development
docker-compose -f docker-compose-dev.yml up -d

# Production
docker-compose up -d

# View logs
docker-compose logs -f web
docker-compose logs -f monitor
```

### 5. Admin Authentication

1. Visit the **admin page**: `http://localhost:5000/admin`
2. Enter your Gmail account email (from `GMAIL_ACCOUNT`)
3. Click "Authenticate"
4. Complete Google OAuth flow
5. Done! Monitor service starts automatically

### 6. Share Your Public URL

Share URI with anyone!

- No authentication required to view
- Shows your latest LiveTrack activity
- Auto-updates when new activity detected

## 🔧 Configuration

Configure via environment variables in `docker-compose.yml`:

| Variable | Service | Default | Description |
|----------|---------|---------|-------------|
| `GMAIL_ACCOUNT` | Both | - | Gmail account email (required for admin access) |
| `EMAIL_CHECK_INTERVAL` | Monitor | 30 | Seconds between Gmail checks |
| `APP_TITLE` | Web | Garmin LiveTrack Public | Page title |
| `ACTIVITY_MAX_AGE_HOURS` | Web | 12 | Hours before activity marked "stale" |
| `DEAD_ACTIVITY_MAX_AGE_HOURS` | Web | 24 | Hours before hiding old activity |
| `OAUTH_REDIRECT_URI` | Web | - | OAuth callback URL (set for production) |
| `FLASK_SECRET_KEY` | Web | dev-secret | Session secret (change in production!) |
| `OAUTHLIB_INSECURE_TRANSPORT` | Web | 0 | Set to 1 for HTTP (dev only) |

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE.txt) file for details.