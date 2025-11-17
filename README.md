# Content Repurposer

Turn your video reels into LinkedIn posts, Twitter threads, and blog posts in seconds.

## Why?

Everyone's making video content, but most people forget to repurpose it for text platforms. This tool does it automatically for ~$0.05 per video.

No monthly subscriptions. No usage limits. Just your API costs.

## How it works

1. Upload a video reel (MP4, MOV, AVI, MKV)
2. Extracts audio from the video using FFmpeg
3. Transcribes using OpenAI Whisper API
4. Reformats transcript into platform-specific posts using Claude API
5. Get formatted posts for LinkedIn, Twitter, and your blog

## Cost per video

- Whisper API: ~$0.006 per minute of audio
- Claude API: ~$0.015 per post × 3 platforms = ~$0.045
- **Total: ~$0.05 per video**

Compare that to $12-99/month for existing services with usage caps.

## Setup

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install FFmpeg (required for audio extraction):
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

3. Create `.env` file with your API keys:
```bash
cp .env.example .env
# Edit .env and add your keys
```

4. Run the app:
```bash
python app.py
```

5. Open http://localhost:5000

## Deploy to Railway

1. Install Railway CLI:
```bash
npm i -g @railway/cli
```

2. Login and initialize:
```bash
railway login
railway init
```

3. Add environment variables in Railway dashboard:
   - `ANTHROPIC_API_KEY`
   - `OPENAI_API_KEY`
   - `AUTH_USERNAME` (recommended for security)
   - `AUTH_PASSWORD` (recommended for security)

4. Deploy:
```bash
railway up
```

Railway will automatically detect it's a Python app and install FFmpeg in the container.

## Environment Variables

- `ANTHROPIC_API_KEY` - Your Anthropic API key for Claude
- `OPENAI_API_KEY` - Your OpenAI API key for Whisper
- `AUTH_USERNAME` - (Optional) Username for HTTP Basic Auth
- `AUTH_PASSWORD` - (Optional) Password for HTTP Basic Auth

### Authentication

The app includes optional HTTP Basic Authentication. When you set `AUTH_USERNAME` and `AUTH_PASSWORD` environment variables, users will be prompted with a browser login dialog before accessing the app.

If these variables are not set, the app runs without authentication (useful for local development).

**For production deployments**, it's recommended to set these credentials to prevent unauthorized access.

## File Structure

```
content-repurposer/
├── app.py              # Main Flask application
├── templates/
│   └── index.html      # UI template
├── uploads/            # Temporary storage (auto-created)
├── requirements.txt    # Python dependencies
├── .env.example        # Example environment variables
└── README.md          # This file
```

## Notes

- Max file size: 100MB
- Supported formats: MP4, MOV, AVI, MKV
- Files are automatically deleted after processing
- Uses Claude Sonnet 4 for content reformatting

## Contributing

PRs welcome. This is a simple tool - let's keep it that way.

## License

MIT - do whatever you want with it.

## Why I built this

I make content reels but was tired of manually reformatting them for different platforms. Existing tools are overpriced and limit usage. This does exactly what I need for pennies per video.

If you find this useful, feel free to share it.
