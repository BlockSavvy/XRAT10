# X Thread Analyzer (XRAT10)

An intelligent web application that analyzes X (formerly Twitter) threads for sentiment analysis, bot detection, and engagement metrics.

## Features

- Real-time thread monitoring and analysis
- Advanced sentiment analysis using VADER
- Lightweight bot detection
- Engagement-optimized responses
- Web interface for manual analysis
- Historical analysis storage
- Automated engagement strategies

## Prerequisites

- Python 3.8+
- X Developer Account with API access
- SQLite3

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/XRAT10.git
cd XRAT10
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
```
Edit `.env` with your X API credentials and other configuration settings.

### Environment Variables

The following environment variables are required:

- `X_API_KEY`: Your X API Key
- `X_API_SECRET`: Your X API Secret
- `X_ACCESS_TOKEN`: Your X Access Token
- `X_ACCESS_TOKEN_SECRET`: Your X Access Token Secret
- `X_BEARER_TOKEN`: Your X Bearer Token
- `CLIENT_ID`: Your OAuth 2.0 Client ID
- `CLIENT_SECRET`: Your OAuth 2.0 Client Secret
- `SECRET_KEY`: A secure secret key for the application
- `DEBUG`: Set to False in production
- `DATABASE_URL`: Your database URL (default: SQLite)

For development, copy `.env.example` to `.env` and fill in your values.
For production deployment (e.g., Vercel), set these in your deployment platform's environment variables.

## Project Structure

```
XRAT10/
├── app/
│   ├── api/
│   │   └── endpoints/
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   ├── db/
│   │   └── models.py
│   ├── services/
│   │   ├── sentiment.py
│   │   └── bot_detection.py
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   └── templates/
├── tests/
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

## Usage

1. Start the application:
```bash
uvicorn app.main:app --reload
```

2. Access the web interface at `http://localhost:8000`

3. Enter a tweet ID to analyze or wait for mentions to trigger automatic analysis

## API Endpoints

- `GET /`: Home page
- `POST /analyze`: Analyze a specific thread
- `GET /past_analyses`: View historical analyses
- `GET /api/v1/stats`: Get analysis statistics (API)

## Deployment

### Local Development
Follow the installation instructions above.

### Production (Vercel)
1. Fork/clone this repository
2. Import to Vercel
3. Set up environment variables in Vercel project settings
4. Deploy!

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- VADER Sentiment Analysis
- FastAPI framework
- X API 