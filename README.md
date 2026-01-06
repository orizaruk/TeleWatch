# TeleWatch

Monitor Telegram chats for keywords and forward matches to multiple channels.

## Features

- Monitor multiple Telegram chats simultaneously
- Keyword-based filtering (case-insensitive)
- Multi-channel forwarding: Telegram, Email, SMS, WhatsApp
- Interactive configuration menu
- **Docker support** for 24/7 daemon operation
- Health monitoring for external watchdogs
- Log rotation (prevents disk fill)
- Graceful shutdown with session stats

## Prerequisites

- Python 3.12+
- Telegram API credentials (API_ID and API_HASH)

## Installation

```bash
git clone <repository-url>
cd telewatch
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install all dependencies
pip install -r requirements.txt
```

Or manually:
```bash
pip install telethon python-dotenv   # Core
pip install twilio                   # Optional: SMS/WhatsApp
```

## Quick Start

1. Get your Telegram API credentials from [my.telegram.org/apps](https://my.telegram.org/apps)
2. Create a `.env` file with your credentials (see Configuration below)
3. Run `python main.py`
4. On first run, authenticate with your Telegram account
5. Use the interactive menu to configure chats, keywords, and destinations

## Configuration

### Environment Variables (.env)

Create a `.env` file in the project root:

```bash
# Required - Telegram API
API_ID=your_api_id
API_HASH=your_api_hash

# Optional - Email notifications (Gmail)
EMAIL_ADDRESS=your@gmail.com
EMAIL_APP_PASSWORD=your_app_password

# Optional - SMS/WhatsApp (Twilio)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+1234567890
```

### Config File (config.json)

Auto-generated on first run. Stores:
- `chats`: List of Telegram chat IDs to monitor
- `keywords`: List of keywords to match (case-insensitive)
- `destinations`: Settings for each notification channel

## External Service Setup

### Telegram API (Required)

1. Go to [my.telegram.org/apps](https://my.telegram.org/apps)
2. Log in with your phone number
3. Create a new application
4. Copy the `api_id` and `api_hash` to your `.env` file

### Gmail (for Email notifications)

1. Enable 2-Factor Authentication on your Google account
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Generate a new App Password for "Mail"
4. Use the 16-character password (without spaces) in your `.env`

### Twilio (for SMS/WhatsApp)

1. Create an account at [twilio.com](https://www.twilio.com/)
2. Get your Account SID and Auth Token from the [Console](https://console.twilio.com/)
3. Get or purchase a phone number with SMS capability
4. For WhatsApp: Recipients must first opt-in via the [Twilio WhatsApp Sandbox](https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn)

## Usage

### Interactive Mode (for configuration)

```bash
python main.py
```

Use the menu to configure chats, keywords, and destinations. This creates `config.json` and `sesh.session`.

### Daemon Mode (for 24/7 operation)

```bash
python main.py -m
```

Skips menu, starts monitoring immediately. Stops on SIGTERM/SIGINT.

### Verbose Logging

```bash
python main.py -v      # Warning level
python main.py -vv     # Debug level
```

## Docker Deployment

For 24/7 unattended operation:

### 1. Configure first (on host)

```bash
python main.py
# Authenticate with Telegram, configure chats/keywords/destinations
# This creates: sesh.session, config.json
```

### 2. Create .env file

```bash
# Required
API_ID=your_api_id
API_HASH=your_api_hash

# Optional - for notifications
EMAIL_ADDRESS=your@gmail.com
EMAIL_APP_PASSWORD=your_app_password
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx
TWILIO_PHONE_NUMBER=+1234567890
```

### 3. Run with Docker Compose

```bash
docker-compose up -d      # Start in background
docker-compose logs -f    # View logs
docker-compose down       # Stop gracefully
```

### Environment Variable Overrides

Instead of `config.json`, you can configure via environment:

```bash
TELEWATCH_CHATS=123456789,-987654321      # Comma-separated chat IDs
TELEWATCH_KEYWORDS=python,remote,developer # Comma-separated keywords
TELEWATCH_DESTINATIONS='{"telegram":{"enabled":true,"chat_id":123}}'  # JSON
```

These override `config.json` values (useful for CI/CD deployments).

## Health Monitoring

The bot writes a timestamp to `health.txt` every 60 seconds. External monitoring can check file age:

```bash
# Example: alert if file older than 2 minutes
find . -name "health.txt" -mmin -2 | grep -q . && echo "healthy" || echo "stale"
```

## Project Structure

```
telewatch/
├── main.py              # Entry point, CLI menu, monitoring loop
├── config.py            # Configuration management + env var loading
├── Dockerfile           # Container image definition
├── docker-compose.yml   # Container orchestration
├── requirements.txt     # Python dependencies
├── notifiers/
│   ├── __init__.py      # Base class, retry logic, registry
│   ├── telegram.py      # Telegram forwarding
│   ├── email.py         # Gmail SMTP
│   ├── sms.py           # Twilio SMS
│   └── whatsapp.py      # Twilio WhatsApp
│
# Generated files (gitignored):
├── config.json          # Runtime config (auto-generated)
├── sesh.session         # Telegram auth session
├── health.txt           # Health check timestamp
└── bot.log              # Application logs (rotated at 5MB)
```
