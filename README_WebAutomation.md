# Web Automation Server

This is a simplified web automation server based on the Nextcloud Talk Recording application. It provides browser automation capabilities for navigating to URLs and performing automated login operations.

## Features

- Navigate to any URL using Chrome or Firefox in a virtual display
- Automatic detection and filling of login forms
- Execute JavaScript on web pages
- Take screenshots of current page
- RESTful HTTP API for automation control
- Session-based management for multiple simultaneous automations

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -e .
   ```

2. **Start the server:**
   ```bash
   web-automation-server --config web-automation.conf
   ```

3. **Create a session and navigate to a URL:**
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/session \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com", "username": "user@example.com", "password": "password123"}'
   ```

## API Endpoints

### Session Management

- `POST /api/v1/session` - Create new automation session
- `GET /api/v1/session/<id>` - Get session status
- `DELETE /api/v1/session/<id>` - Stop and delete session
- `GET /api/v1/sessions` - List all active sessions

### Navigation and Interaction

- `POST /api/v1/session/<id>/navigate` - Navigate to new URL
- `POST /api/v1/session/<id>/login` - Perform login on current page
- `POST /api/v1/session/<id>/execute` - Execute JavaScript
- `GET /api/v1/session/<id>/screenshot` - Take screenshot (base64)

### System

- `GET /api/v1/welcome` - Get server information

## Example Usage

### Create Session with Login
```json
POST /api/v1/session
{
  "url": "https://example.com/login",
  "username": "user@example.com", 
  "password": "secretpassword"
}
```

### Navigate to New URL
```json
POST /api/v1/session/{session_id}/navigate
{
  "url": "https://example.com/dashboard"
}
```

### Execute JavaScript
```json
POST /api/v1/session/{session_id}/execute
{
  "script": "return document.querySelector('h1').textContent;"
}
```

## Configuration

The server uses the same configuration format as the original Nextcloud Talk Recording server. Key settings:

```ini
[http]
listen = 127.0.0.1:8000

[recording]
browser = firefox
videowidth = 1920
videoheight = 1080

[backend]
skipverify = true
```

## Testing

Run the test script to verify functionality:

```bash
# Start server in one terminal
web-automation-server --config web-automation.conf

# Run tests in another terminal  
python test_web_automation.py
```

## Dependencies

- Python 3.8+
- Flask - Web framework
- Selenium - Browser automation
- PyVirtualDisplay - Virtual display support
- Chrome/Chromium or Firefox browser
- Appropriate WebDriver (geckodriver for Firefox, chromedriver for Chrome)

## Removed Functionality

The following components from the original Nextcloud Talk Recording server have been removed to create this simplified web automation server:

- Video/audio recording capabilities
- FFMPEG integration
- PulseAudio support
- Nextcloud Talk specific API calls
- WebRTC signaling
- File upload functionality
- Prometheus metrics
- Backend authentication (simplified)

## License

GNU AGPLv3+ (same as original Nextcloud Talk Recording server)