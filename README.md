# TeleWatch

Monitor Telegram chats for keywords and forward matches to multiple channels.

## Features

- Monitor multiple Telegram chats simultaneously
- Keyword-based filtering (case-insensitive)
- Multi-channel forwarding: Telegram, Email, SMS, WhatsApp
- Interactive configuration menu

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

# Core dependencies
pip install telethon python-dotenv

# Optional: for SMS/WhatsApp notifications
pip install twilio
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

```bash
# Interactive menu
python main.py

# Start monitoring directly (requires prior configuration)
python main.py -m

# Enable verbose logging
python main.py -v      # Warning level
python main.py -vv     # Debug level
```

## Project Structure

```
telewatch/
├── main.py              # Entry point and CLI menu
├── config.py            # Configuration management
├── config.json          # Runtime config (auto-generated)
├── .env                 # Credentials (create manually)
├── bot.log              # Application logs
└── notifiers/
    ├── __init__.py      # Base notifier class
    ├── telegram.py      # Telegram forwarding
    ├── email.py         # Gmail SMTP
    ├── sms.py           # Twilio SMS
    └── whatsapp.py      # Twilio WhatsApp
```
