# 🏃 Garmin LiveTrack Public

A self-hosted web application that provides a permanent, public view of your Garmin LiveTrack activities.

## ✨ Key Features

- **Single Permanent URL**: One link that always shows your latest activity
- **No Blocking**: Web service responds instantly (<10ms)
- **Microservices Architecture**: Independent monitor and web services
- **Real-time Updates**: Automatic frontend refresh when activity detected
- **Responsive Design**: Works on all devices
- **Easy Deployment**: Docker Compose setup with health checks

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
│   ├── templates/          # HTML templates
│   ├── Dockerfile
│   └── README.md
├── docker-compose.yml      # Service orchestration
├── .env                    # Configuration
├── credentials.json        # Gmail OAuth (not in repo)
├── token.json              # Gmail token (not in repo)
└── README.md               # This file
```

## 🏗️ Architecture

```
┌───────────────────┐
│  Monitor Service  │ Polls Gmail every 30s
│   (Background)    │ Writes state to JSON
└────────┬──────────┘
         │
         ▼
  ┌──────────────┐
  │ State Volume │    Shared Docker volume
  │  JSON file   │
  └──────┬───────┘
         │
         ▼
┌──────────────────┐
│   Web Service    │  Reads JSON
│     (Flask)      │  Serves HTML
└──────────────────┘
```

## 🚀 Quick Start

### 1. Prerequisites

- Docker and Docker Compose
- Gmail account for LiveTrack notifications
- Google Cloud Project with Gmail API enabled
- `credentials.json` from Google Cloud Console

### 2. Configure

Edit docker-compose environment variables:

```bash
# Gmail Configuration
GMAIL_ACCOUNT=your-livetrack@gmail.com
EMAIL_CHECK_INTERVAL=30

# Web Configuration
APP_TITLE=My LiveTrack
ACTIVITY_MAX_AGE_HOURS=24
```

### 3. Deploy

```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f

# Check health
curl http://localhost:5002/api/health
```

### 4. Access

Open `http://localhost:5002` in your browser.


## 🔧 Configuration

All configuration is done via environment variables in `docker-compose.yml` file:

| Variable | Service | Default | Description |
|----------|---------|---------|-------------|
| `GMAIL_ACCOUNT` | Monitor | - | Gmail account email |
| `EMAIL_CHECK_INTERVAL` | Monitor | 30 | Seconds between checks |
| `APP_TITLE` | Web | Garmin LiveTrack Public | Page title |
| `ACTIVITY_MAX_AGE_HOURS` | Web | 24 | Hours before "stale" |

## 🛠️ Development

```bash
# Monitor service (standalone)
cd monitor
python monitor_service.py

# Web service (standalone)
cd web
python main.py
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE.txt) file for details.