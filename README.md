# Swarm Wrapped

Generate your own Spotify Wrapped-style report from your Foursquare Swarm check-ins.

![Swarm Wrapped Preview](https://alexpriest.github.io/swarm-2025-wrapped/swarm-wrapped-preview.png)

## Features

- 📊 Total check-ins, venues, cities, and countries
- 🔥 Longest check-in streak
- 🏆 Top venues and categories
- ⏰ Time personality analysis
- 👥 Check-in crew stats
- 🗺️ Interactive map of all your check-ins

## Setup

### Prerequisites

- Python 3.9+
- Foursquare Developer Account

### Foursquare API Setup

1. Go to [Foursquare Developer Console](https://foursquare.com/developers/apps)
2. Sign in with your Foursquare account (create one if needed)
3. Click **Create a new app**
4. Fill in the app details:
   - **App Name**: e.g., "Swarm Wrapped"
   - **App URL**: Your website or `http://localhost:8000`
5. After creation, you'll see your **Client ID** and **Client Secret** - save these!
6. Under **Redirect URIs**, add: `http://localhost:8000/callback`
   - For production, also add your deployed URL (e.g., `https://yourapp.com/callback`)

**What you need:**
- `FOURSQUARE_CLIENT_ID` - The Client ID shown in your app dashboard
- `FOURSQUARE_CLIENT_SECRET` - The Client Secret (click to reveal)
- `FOURSQUARE_REDIRECT_URI` - Must exactly match what you registered (including trailing slash if any)

### Installation

```bash
# Clone the repo
git clone https://github.com/alexpriest/swarm-wrapped-app.git
cd swarm-wrapped-app

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export FOURSQUARE_CLIENT_ID="your_client_id"
export FOURSQUARE_CLIENT_SECRET="your_client_secret"
export SESSION_SECRET="your_random_secret_key"

# Run the app
uvicorn app:app --reload
```

Visit `http://localhost:8000` and connect your Swarm account!

## Deployment

This app can be deployed to Vercel, Railway, or any Python hosting platform.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `FOURSQUARE_CLIENT_ID` | Your Foursquare app client ID |
| `FOURSQUARE_CLIENT_SECRET` | Your Foursquare app client secret |
| `FOURSQUARE_REDIRECT_URI` | OAuth callback URL (e.g., `https://yourapp.com/callback`) |
| `SESSION_SECRET` | Random string for session encryption |

## Privacy

- Your check-in data is fetched directly from Foursquare
- Data is processed in-memory and never stored
- Your access token is only kept in your browser session
- Disconnect anytime to clear your session

## Credits

Built with [swarm-mcp](https://github.com/alexpriest/swarm-mcp)

## License

MIT
