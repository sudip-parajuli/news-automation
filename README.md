# International News Automation System

A fully automated international news publishing system that detects breaking news for YouTube Shorts and produces daily summaries for long-form videos.

## Features
- **Breaking News Detection**: Scans RSS feeds, Telegram, and DDG for urgent updates.
- **AI Scripting**: Uses Google Gemini to rewrite news into catchy video scripts.
- **Natural Narration**: High-quality English voiceovers via `edge-tts`.
- **Vertical & Horizontal Video**: Programmatically generates video with animated subtitles.
- **Auto-Upload**: Publishes directly to YouTube with optimized metadata.
- **Hands-Free**: Powered by GitHub Actions for periodic execution.

## Project Structure
```
international_news_automation/
├── fetchers/            # RSS, Telegram, and DDG fetchers
├── processors/          # Classification and AI scripting
├── media/               # TTS and video generation logic
├── uploader/            # YouTube API integration
├── storage/             # Trackers and temporary media
├── main_breaking.py     # Entry point for Shorts
├── main_daily.py        # Entry point for Daily Summaries
└── .github/workflows/   # Scheduling logic
```

## Setup Instructions

### 1. Prerequisites
- **Python 3.9+**
- **FFmpeg**: [Download here](https://ffmpeg.org/download.html) and add to PATH.
- **ImageMagick**: Required for subtitles.
  - **Windows**: Install [ImageMagick](https://imagemagick.org/script/download.php#windows). During installation, check "Install legacy utilities (e.g. convert)".
  - **Important**: You may need to tell MoviePy where ImageMagick is. In your Python environment, you can set the `IMAGEMAGICK_BINARY` environment variable to the path of `magick.exe`.

### 2. API Credentials
- **Gemini AI**: Add `GEMINI_API_KEY` to your `.env` file. The system is configured to use `gemini-2.0-flash`.
- **YouTube API**: 
  - Place `client_secrets.json` in the project root.
  - Run the script once locally. It will open a browser for authentication and create `token.pickle`.
- **Telegram (Optional)**: Get `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org).

### 3. Environment Variables
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### 4. Running Locally
```bash
pip install -r requirements.txt
python international_news_automation/main_breaking.py
```

## GitHub Actions Deployment
1. Go to your GitHub Repository Settings -> Secrets and variables -> Actions.
2. Add the following secrets:
   - `GEMINI_API_KEY`
   - `TELEGRAM_API_ID` (if used)
   - `TELEGRAM_API_HASH` (if used)
3. Ensure the `token.pickle` is committed to the repository (or handle authentication via service accounts if preferred).

## Monetization Compliance
- Content is rewritten from scratch (no verbatim copying).
- Original narration (no source audio used).
- Educational/News context (Transformative work).

---

## Music Assets

Background music for the long-form pipeline lives in `assets/music/`.

### Adding Real Tracks

1. Download a CC0-licensed track from one of these free sources:
   - **YouTube Audio Library** (studio.youtube.com/channel/music) � filter by "CC0"
   - **Pixabay Music** (pixabay.com/music) � all tracks are royalty-free
   - **Incompetech** (incompetech.filmmusic.io) � Kevin MacLeod's catalog, CC BY 4.0

2. Place the `.mp3` file in `assets/music/`.

3. Update `assets/music/catalog.json` � add an entry and set `"replace_with_real_track": false`:
```json
{
  "file": "your_track.mp3",
  "mood": "calm",
  "bpm": 80,
  "duration_seconds": 180,
  "replace_with_real_track": false,
  "source": "YouTube Audio Library � Track Name"
}
```

### Mood ? Section Mapping

| Mood | Sections |
|------|---------|
| calm | hook, context, resolution |
| tense | conflict, evidence |
| dramatic | twist |
| upbeat | cta |

The `scripts/music_selector.py` module uses this mapping automatically.
The current placeholder files in `assets/music/` are 60-second silent `.mp3` files
that allow the pipeline to run end-to-end without real audio.
