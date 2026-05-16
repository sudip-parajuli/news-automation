# News Automation Channel — Upgrade Implementation Plan
### For use in Google Antigravity (Planning Mode)

> **How to use this file in Antigravity:**
> Open your `news-automation` repo as a workspace. Switch to **Planning Mode**. Paste each prompt block from this file into the Manager View as a separate task. Let the agent generate its artifact (task list + implementation plan), review it, leave inline comments if needed, then approve. Work through phases in order — each phase depends on the previous.

---

## Context snapshot (paste this once at the start of every session)

```
Project: news-automation
Purpose: Automated YouTube channel "On Trending Today" — fetches news, generates scripts,
         creates videos, uploads to YouTube with zero human intervention.
Current state: Shorts are posting and getting some views. Long-form videos are compiled
               from multiple Shorts news clips — they have very low watch-time retention.
               Channel has enough subscribers for monetisation but is short on watch hours.
Goal: Redesign the pipeline so long-form videos are narrative explainer-style content
     (8–15 minutes, high retention), Shorts are upgraded with better editing hooks, and
     the entire stack uses modern video rendering tools including Remotion.
Stack context: Python-based automation, likely uses MoviePy or FFmpeg for video editing,
               LLM API for script generation, YouTube Data API v3 for upload.
```

> Paste the above context block at the top of every new Antigravity session so the agent has full project memory.

---

## Phase 1 — Codebase audit and dependency mapping

### Antigravity prompt

```
Using Planning Mode, perform a full audit of this repository. I need you to:

1. Map every file and its purpose — produce an artifact showing the directory tree
   annotated with a one-line description of what each file does.

2. Identify the current video pipeline: trace the exact flow from news fetch → 
   script generation → media assembly → video render → YouTube upload. Document 
   every function, class, and external API call involved in this pipeline as a 
   numbered sequence diagram artifact.

3. Identify all current dependencies (requirements.txt or equivalent). Flag any that
   are outdated, deprecated, or should be replaced as part of this upgrade.

4. Find every place in the code where the LLM is prompted. Extract all prompt strings
   and list them in an artifact so I can review and rewrite them.

5. Find every place where video editing happens (FFmpeg calls, MoviePy operations, 
   image/clip assembly). List each operation and what it produces.

6. Identify how long-form videos are currently generated — specifically whether they
   are just concatenations of Shorts clips or have their own pipeline.

Do not make any changes yet. Produce only the audit artifacts.
```

---

## Phase 2 — Dependency and tooling upgrade

### Antigravity prompt

```
Using Planning Mode, upgrade the project's tooling and add the new dependencies 
required for this pipeline redesign. Perform these steps:

1. Add Remotion to the project as the primary video rendering engine for long-form
   content. Set up a new `remotion/` directory at the project root with:
   - A base Remotion composition named `LongFormExplainer` (1920×1080, 30fps)
   - A base Remotion composition named `ShortFormNews` (1080×1920, 30fps)
   - A root `index.tsx` entry point
   - A `package.json` with @remotion/cli, @remotion/player, and @remotion/google-fonts
   - A render script `render.mjs` that accepts a JSON data file and outputs an mp4
   Install all Node dependencies with `npm install`.

2. In the Python side, add these packages to requirements.txt and install them:
   - `httpx` (async HTTP for media fetching)
   - `pexels-api-py` or direct Pexels REST client for video B-roll fetching
   - `pixabay-python` for fallback stock footage
   - `python-dotenv` if not already present
   - `tenacity` for retry logic on API calls
   Keep existing packages. Do not remove anything yet.

3. Create a `.env.example` file listing every environment variable the project needs,
   including: PEXELS_API_KEY, PIXABAY_API_KEY, REMOTION_SERVE_URL, and any existing
   keys already in use. Do not write actual values — only key names with comments.

4. Add a top-level `Makefile` with targets:
   - `make audit` — runs a health check on all API keys
   - `make shorts` — runs the Shorts pipeline
   - `make longform` — runs the long-form pipeline  
   - `make render` — triggers Remotion render for a given composition
   - `make upload` — uploads the latest rendered video to YouTube

Verify everything installs cleanly and the project still runs its existing pipeline
without errors before proceeding.
```

---

## Phase 3 — Long-form script generator (complete rewrite)

### Antigravity prompt

```
Using Planning Mode, rewrite the long-form video script generator module. The current
implementation likely produces a summary or list of news items. Replace it entirely with
a narrative explainer script generator. Here is exactly what I need:

TASK: Create a new Python module `scripts/longform_script_generator.py` that replaces
the existing long-form script logic. It must do the following:

1. Accept a topic string (e.g. "Why oil prices are spiking globally") as input.

2. Call the LLM API with the following prompt template — implement this EXACTLY:

   System prompt:
   """
   You are a senior documentary scriptwriter for a YouTube explainer channel.
   Your scripts are structured like mini-documentaries: they open with a mystery
   or surprising fact, build tension through context, deliver a twist or reveal
   in the middle, and close with a satisfying resolution plus a strong call to
   action. Your tone is authoritative but conversational — like a trusted friend
   who happens to know everything about the topic. Never use bullet points or
   numbered lists in the script. Write in flowing prose that sounds natural when
   spoken aloud.
   """

   User prompt:
   """
   Write a YouTube explainer script on this topic: {topic}

   Structure the script in exactly these labelled sections:
   
   [HOOK] - 30-45 seconds. Open with a single stunning fact, statistic, or
   question that makes the viewer need to know more. End with "And in this video,
   I'm going to show you exactly why." Never start with "In today's video."
   
   [CONTEXT] - 60-90 seconds. Give the essential background. What was the 
   situation before this happened? Who are the main players?
   
   [CONFLICT] - 90-120 seconds. What changed? What is the central tension or 
   problem? Use a specific event or moment as the turning point.
   
   [EVIDENCE] - 90-120 seconds. Back up the conflict with 2-3 specific facts,
   quotes, or data points. Each one should deepen the mystery or raise the stakes.
   
   [TWIST] - 60-90 seconds. The part most people don't know. The angle that
   makes your video worth watching even if they've heard about this topic before.
   
   [RESOLUTION] - 60 seconds. What does this mean going forward? What should
   the viewer think or feel differently about now?
   
   [CTA] - 15 seconds. Tell them to watch the next video: "If you want to
   understand [related topic], I've already covered that — link is right there."
   
   Total target: 1,400–1,800 words (approx 8–10 minutes of speech at 160 wpm).
   
   After the script, on a new line, output a JSON block in this exact format:
   {"title_options": ["...", "...", "..."], "thumbnail_keywords": ["...", "...", "..."],
    "search_keywords": ["...", "...", "..."], "estimated_duration_minutes": 0}
   
   The three title_options must use different hooks: one curiosity gap, one number,
   one "nobody is talking about this" framing.
   """

3. Parse the LLM response to extract:
   - The labelled script sections as a dict
   - The JSON metadata block
   - A flat `full_script` string for TTS

4. Save the output as `output/scripts/{topic_slug}_{timestamp}.json` containing
   both the structured sections and metadata.

5. Add a `select_best_title(title_options: list) -> str` function that uses the LLM
   to pick the highest-CTR title from the three options by asking it to reason about
   YouTube click-through psychology.

Write unit tests for the parser (the JSON extraction and section parsing logic).
Run the tests and confirm they pass before finishing.
```

---

## Phase 4 — B-roll media fetcher

### Antigravity prompt

```
Using Planning Mode, build a B-roll video clip fetcher module. This replaces any
existing static image fetching logic for long-form videos. Here is exactly what I need:

TASK: Create `scripts/broll_fetcher.py` with the following behaviour:

1. Accept a script section (text string) as input.

2. Use the LLM to extract 3–5 visual search queries from the section text. Prompt:
   """
   Given this script excerpt, generate 3-5 short search queries (2-4 words each)
   suitable for finding relevant stock video footage on Pexels or Pixabay.
   Prefer concrete visual subjects over abstract concepts.
   Return only a JSON array of strings. Example: ["city traffic aerial", "stock market screen"]
   """

3. For each query, search the Pexels Video API first (GET https://api.pexels.com/videos/search).
   Filter results to: orientation=landscape, min_duration=4, max_duration=15.
   Download the first matching clip (SD quality, ≤15MB) to `output/broll/`.

4. If Pexels returns no results for a query, fall back to Pixabay video API.

5. If neither API has results, fall back to a relevant still image from Pexels Photos API
   and mark it with `{"type": "still_image", "needs_kenburns": true}` in the metadata.

6. Return a list of media items, each with:
   {"query": "...", "file_path": "...", "type": "video|still_image",
    "duration_seconds": 0, "needs_kenburns": false}

7. Add a `apply_kenburns(image_path: str, output_path: str, duration: int)` function
   that uses FFmpeg to apply a slow zoom-in Ken Burns effect to a still image,
   producing a {duration}-second video clip. Use this filter:
   `zoompan=z='zoom+0.0015':d={fps*duration}:s=1920x1080`

8. Add retry logic (max 3 attempts, exponential backoff) on all API calls using tenacity.

9. Cache downloaded files — if `output/broll/{query_slug}.mp4` already exists, skip
   the download. This prevents redundant API calls on re-runs.

Write a test that mocks the Pexels API and verifies the fallback chain works correctly.
```

---

## Phase 5 — Remotion long-form composition

### Antigravity prompt

```
Using Planning Mode, build the Remotion composition for long-form explainer videos.
This is the core rendering engine for the new long-form format.

TASK: Build out `remotion/src/compositions/LongFormExplainer/` with:

1. `LongFormExplainer.tsx` — the root composition component. It accepts a prop:
   `data: LongFormVideoData` (define the type in a `types.ts` file). The data shape:
   {
     sections: Array<{
       id: string,           // "hook" | "context" | "conflict" etc.
       text: string,         // script text for this section
       broll: Array<{
         file: string,       // absolute path to video/image clip
         type: "video" | "still_image",
         duration: number    // seconds
       }>
     }>,
     title: string,
     voiceover_file: string, // path to the full TTS audio file
     background_music: string // path to background music track
   }

2. `ScriptSection.tsx` — renders one section. It:
   - Plays the B-roll clips in sequence for that section's duration
   - Shows animated lower-third text that fades in 0.5s after each clip starts
   - The lower-third shows a 1-line key fact extracted from the script text
   - Uses @remotion/google-fonts for Inter (clean, modern look)

3. `LowerThird.tsx` — animated lower-third bar component:
   - White text on a semi-transparent dark background strip
   - Slides in from left over 20 frames, holds, fades out 20 frames before section end
   - Font: Inter 28px bold for main text, 20px regular for sub-text

4. `ProgressBar.tsx` — thin coloured bar at the top of the frame showing video progress.
   Accent colour: #E84545 (YouTube red). This improves perceived retention.

5. `ChapterCard.tsx` — full-screen transition card shown between major sections (0.5s):
   - Dark background, centred chapter title, section number
   - Used between CONTEXT → CONFLICT → EVIDENCE → TWIST only (not hook or CTA)

6. `AudioSync.tsx` — component that plays the voiceover_file and background_music
   simultaneously. Background music volume ducked to 15% during speech.

7. Update `remotion/src/index.tsx` to register the LongFormExplainer composition with:
   - id: "LongFormExplainer"
   - width: 1920, height: 1080, fps: 30
   - durationInFrames: computed from total audio duration × 30

8. Update `render.mjs` to accept `--composition LongFormExplainer --data path/to/data.json`
   and output to `output/renders/{title_slug}_{timestamp}.mp4`

Test by rendering a 30-second stub composition using placeholder assets to verify
the component tree renders without errors.
```

---

## Phase 6 — Remotion Shorts composition

### Antigravity prompt

```
Using Planning Mode, build the Remotion composition for upgraded YouTube Shorts.
This improves the existing Shorts format with better hooks and editing rhythm.

TASK: Build out `remotion/src/compositions/ShortFormNews/` with:

1. `ShortFormNews.tsx` — root composition (1080×1920, 30fps, max 180s = 3 min).
   Accepts prop: `data: ShortFormVideoData`:
   {
     headline: string,
     body_text: string,         // 2-3 sentence news summary
     clips: Array<{ file: string, duration: number }>,
     caption_lines: string[],   // 5-8 short caption burns
     voiceover_file: string,
     hook_text: string,         // first 1.5s text overlay — the "make them click" line
     loop_hook: string,         // last 2s text overlay — creates loop
     audio_track: string        // trending background audio (optional)
   }

2. `HookOverlay.tsx` — full-screen text overlay for the first 1.5 seconds:
   - Large bold centred text (Inter 64px), white with black outline
   - Punches in with a scale animation from 0.85→1.0 over 8 frames
   - This is the most important element — it must be unmissable

3. `CaptionBurn.tsx` — animated word-by-word caption that tracks the voiceover:
   - Each word appears timed to speech (approximate: word_count / wpm × frame_rate)
   - Active word is white, previous words are grey, background is semi-transparent pill
   - Font: Inter 36px bold, positioned bottom-center (safe area: y > 75% of frame height)

4. `ClipReel.tsx` — cycles through the clips array. Each clip:
   - Hard cuts (no cross-fade) — Shorts need high cut frequency
   - Target: new visual every 1.5–2 seconds
   - If a clip is longer than 2s, trim it to 2s automatically

5. `LoopHook.tsx` — last 2 seconds of the Short:
   - Reuses the first frame of the first clip as background
   - Overlays the loop_hook text in the same style as HookOverlay
   - Creates a visual loop — last frame looks like the first, encouraging replays

6. `CTACard.tsx` — appears at second 50–58 (just before end):
   - "Full story on the channel ↑" text
   - Arrow pointing up (toward the Subscribe button area on mobile)
   - Fades in over 10 frames

7. Register the composition in `remotion/src/index.tsx`:
   - id: "ShortFormNews"
   - width: 1080, height: 1920, fps: 30
   - durationInFrames: computed from total clip duration × 30 (max 5400)

Render a 20-second test Short using placeholder assets to verify the layout
on a 9:16 viewport. Check that all text stays within safe zones (80px margin
from all edges).
```

---

## Phase 7 — TTS voiceover integration

### Antigravity prompt

```
Using Planning Mode, build a TTS (text-to-speech) voiceover generator module that
produces high-quality narration for both long-form and Shorts videos.

TASK: Create `scripts/voiceover_generator.py`:

1. Implement support for two TTS providers with automatic fallback:
   PRIMARY: Google Cloud Text-to-Speech API
   - Use voice: en-US-Journey-D (male) or en-US-Journey-F (female), configurable via env
   - Speaking rate: 0.95 (slightly slower than default — clearer for news content)
   - Audio encoding: LINEAR16, sample rate 24000Hz, output as .wav then convert to .mp3

   FALLBACK: ElevenLabs API (if ELEVENLABS_API_KEY is set)
   - Model: eleven_turbo_v2_5
   - Voice ID: configurable via ELEVENLABS_VOICE_ID env var
   - Output format: mp3_44100_128

2. `generate_voiceover(script_text: str, output_path: str, provider: str = "auto") -> str`
   - Splits text into chunks of max 4,500 characters at sentence boundaries
   - Generates audio for each chunk
   - Concatenates chunks using FFmpeg: `ffmpeg -i "concat:chunk1.mp3|chunk2.mp3" -acodec copy out.mp3`
   - Returns path to final audio file

3. `get_voiceover_duration(audio_path: str) -> float`
   - Uses FFprobe to get accurate duration in seconds
   - Returns float (e.g. 487.3 for 8 min 7 sec)
   - This is used by Remotion to set durationInFrames

4. Add SSML support for long-form scripts:
   - Wrap [HOOK] section text in `<emphasis level="strong">` tags
   - Add `<break time="500ms"/>` between script sections
   - Add `<prosody rate="fast">` around the CTA section

5. Add `estimate_word_timestamps(audio_path: str, script_text: str) -> list`
   - Uses forced alignment via gentle-aligner OR falls back to evenly distributing
     words across the audio duration
   - Returns list of {"word": "...", "start": 0.0, "end": 0.2} dicts
   - Used by CaptionBurn.tsx to sync captions to speech

Add the required API keys (GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_TTS_API_KEY,
ELEVENLABS_API_KEY) to .env.example.
```

---

## Phase 8 — Background music pipeline

### Antigravity prompt

```
Using Planning Mode, add a background music system that sources royalty-free music
and applies it correctly to both long-form and Shorts videos.

TASK: Create `scripts/music_selector.py`:

1. Maintain a local library of pre-approved royalty-free tracks in `assets/music/`.
   Create a `assets/music/catalog.json` with entries:
   {"id": "...", "file": "...", "mood": "tense|calm|upbeat|dramatic",
    "bpm": 0, "duration_seconds": 0, "suitable_for": ["longform", "shorts"]}

2. `select_music(mood: str, video_type: str, duration_seconds: float) -> str`:
   - Picks a track from catalog.json matching mood and video_type
   - If track is shorter than duration, loops it seamlessly using FFmpeg:
     `ffmpeg -stream_loop -1 -i track.mp3 -t {duration} -af "afade=t=out:st={fade_start}:d=3" out.mp3`
   - Returns path to the prepared music file

3. Seed the `assets/music/` folder by downloading 5 starter tracks from the
   Free Music Archive API (freemusicarchive.org/api) in these moods:
   - 2 × calm/background (for long-form body sections)
   - 1 × tense/dramatic (for CONFLICT and TWIST sections)
   - 1 × upbeat (for Shorts)
   - 1 × minimal/ambient (for HOOK sections)
   
   Only download tracks licensed under CC0 or CC BY. Save license info in catalog.json.

4. `apply_music_ducking(voiceover_path: str, music_path: str, output_path: str)`:
   - Mixes voiceover and music using FFmpeg
   - Music at 12% volume under speech, raises to 35% in 2-second gaps between sections
   - Use the `sidechaincompress` filter for clean ducking
   - This replaces the AudioSync Remotion component for cases where pre-mixed audio
     is preferred over mixing in Remotion

Update .env.example with FMA_API_KEY if needed.
```

---

## Phase 9 — Thumbnail generator

### Antigravity prompt

```
Using Planning Mode, build an automated thumbnail generator that produces high-CTR
YouTube thumbnails for both long-form and Shorts.

TASK: Create `scripts/thumbnail_generator.py`:

1. Use Pillow (PIL) to composite thumbnails programmatically. Do not use an external
   design API — keep it in-house and fast.

2. `generate_longform_thumbnail(title: str, keywords: list, output_path: str) -> str`:
   Template layout (1280×720):
   - Background: darkened B-roll still frame (first frame of strongest B-roll clip)
   - Left side: large bold text (title, max 6 words, white with 3px black stroke)
     Font: Load a bold font from assets/fonts/ — download Oswald Bold or Bebas Neue
   - Right side: placeholder for an icon or keyword image (fetch from Pexels Photos
     using keywords[0])
   - Bottom-left: channel logo watermark (create a placeholder if none exists)
   - Red accent bar across the bottom 8px
   - Generate 2 variants with different background crops (left-crop and right-crop)

3. `generate_shorts_thumbnail(headline: str, output_path: str) -> str`:
   Template layout (1080×1920):
   - Full bleed B-roll background
   - Top-center: bold headline text, max 4 words
   - Bottom: gradient overlay fading to black
   - No logo (Shorts thumbnails are less important than the first frame)

4. `select_best_thumbnail(variant_paths: list) -> str`:
   Use the LLM Vision API (Gemini 3 Vision or GPT-4o) to evaluate which thumbnail
   variant has higher predicted CTR. Prompt:
   """
   You are a YouTube thumbnail analyst. Given these two thumbnail images, choose which
   one is more likely to get clicked based on: visual contrast, text readability,
   emotional impact, and curiosity gap. Reply with only "A" or "B" and one sentence of
   reasoning.
   """
   Return the path of the winning variant.

5. Download Oswald-Bold.ttf and Inter-Bold.ttf to `assets/fonts/` using the Google
   Fonts API if not already present.

Add a `make thumbnails` target to the Makefile that generates thumbnails for all
pending videos in `output/scripts/`.
```

---

## Phase 10 — Orchestrator: new long-form pipeline

### Antigravity prompt

```
Using Planning Mode, build the master orchestrator that connects all Phase 3–9 modules
into a single end-to-end long-form video pipeline. This replaces the existing long-form
video generation flow entirely.

TASK: Create `scripts/longform_pipeline.py`:

1. `run_longform_pipeline(topic: str)` — the main entry point. It must:

   STEP 1 — Generate script
     Call longform_script_generator.generate_script(topic)
     Save to output/scripts/{slug}.json
     Log: "Script generated: {estimated_duration_minutes} min, {word_count} words"

   STEP 2 — Fetch B-roll
     For each section in the script, call broll_fetcher.fetch_broll(section_text)
     Collect all clips, log how many video vs still-image clips were found
     Apply ken burns to all still_image clips

   STEP 3 — Generate voiceover
     Call voiceover_generator.generate_voiceover(full_script)
     Get duration with voiceover_generator.get_voiceover_duration()
     Get word timestamps with voiceover_generator.estimate_word_timestamps()

   STEP 4 — Select and prepare music
     Determine mood from script (use LLM: "Given this script topic, choose one mood:
     tense, calm, upbeat, dramatic. Reply with one word.")
     Call music_selector.select_music(mood, "longform", duration)

   STEP 5 — Generate thumbnails
     Call thumbnail_generator.generate_longform_thumbnail(best_title, keywords)
     Call thumbnail_generator.select_best_thumbnail()

   STEP 6 — Build Remotion data file
     Assemble output/remotion_data/{slug}.json in the LongFormVideoData shape
     Map each script section to its B-roll clips and time offsets
     Include voiceover_file, background_music, title paths

   STEP 7 — Render video
     Run: `node remotion/render.mjs --composition LongFormExplainer --data output/remotion_data/{slug}.json`
     via subprocess.run(), stream stdout/stderr to the terminal in real time
     On render completion, confirm the output .mp4 exists and log its file size

   STEP 8 — Upload to YouTube
     Call the existing YouTube upload module (do not rewrite it — just integrate it)
     Pass: video_path, thumbnail_path, title (best_title), description, tags (search_keywords)
     Set privacy to "public", category to "25" (News & Politics)
     Log the resulting YouTube video ID and URL

2. Add error handling at every step — if any step fails, save the partial state to
   `output/pipeline_state/{slug}.json` so the pipeline can be resumed from the
   failed step without re-running earlier steps.

3. Add a `resume_pipeline(slug: str, from_step: int)` function that reads the saved
   state and continues from the specified step.

4. Update the Makefile `make longform` target to call this pipeline with a topic
   argument: `make longform TOPIC="why oil prices are spiking"`
```

---

## Phase 11 — Shorts pipeline upgrade

### Antigravity prompt

```
Using Planning Mode, upgrade the existing Shorts pipeline to use the new Remotion
ShortFormNews composition and improved script hooks.

TASK: Modify the existing Shorts pipeline (do not replace it — extend it):

1. Find the existing Shorts script generator. Add a post-processing step that calls
   the LLM to generate two additional fields for each Short:
   
   hook_text: One sentence, max 8 words, that creates a curiosity gap or shock.
   Must NOT start with "Did you know" or "Here's why." 
   Examples: "This changes everything about [X]." / "Nobody predicted [X] would happen."
   
   loop_hook: One sentence, max 6 words, that callbacks to the hook_text.
   Designed to be the last thing visible — it should feel like the start of the video.
   Example: "So now you know why [X]."
   
   Use this LLM prompt:
   """
   Given this news summary: {summary}
   Generate a hook_text and loop_hook for a YouTube Short.
   Return JSON: {"hook_text": "...", "loop_hook": "..."}
   hook_text: max 8 words, creates urgent curiosity, no clickbait clichés.
   loop_hook: max 6 words, callbacks to the hook, creates a loop (last frame = first frame feeling).
   """

2. Replace the existing video rendering step for Shorts with Remotion:
   - Assemble a ShortFormVideoData JSON object from the script + broll + voiceover
   - Run: `node remotion/render.mjs --composition ShortFormNews --data {data_file}`
   - The output replaces whatever the current Shorts rendering produces

3. Increase B-roll clip variety for Shorts:
   - Fetch at minimum 6 clips per Short (current is probably 2-3 stills)
   - Each clip must be ≤2 seconds long (trim longer clips with FFmpeg)
   - Ensure visual diversity — avoid fetching multiple clips with the same search query

4. Add a `pinned_comment` field to the Shorts upload metadata:
   Value: "Full story: [long-form video URL or 'dropping this week on the channel']"
   Pass this to the YouTube upload module to be posted as a pinned comment immediately
   after upload.

5. Add chapter-style tags to the description of every Short:
   #trending #news #[topic_keyword_1] #[topic_keyword_2]
   (derive topic keywords from the script metadata JSON)

Run the upgraded Shorts pipeline end-to-end on one test topic and verify the rendered
video plays correctly before marking this phase complete.
```

---

## Phase 12 — Scheduling and volume control

### Antigravity prompt

```
Using Planning Mode, build a scheduling system that controls upload cadence and
prevents the channel from being flagged for spam or inauthentic content.

TASK: Create `scripts/scheduler.py`:

1. Implement a weekly content calendar:
   - Monday, Wednesday, Friday: 1 long-form explainer (8–15 min)
   - Daily (Tue–Sun): 1–2 Shorts
   This is the target. The scheduler enforces it by queuing and rate-limiting uploads.

2. `UploadQueue` class backed by a SQLite database (`output/queue.db`):
   - Table: videos (id, type, topic, status, scheduled_for, video_path, thumbnail_path,
     youtube_id, created_at, uploaded_at)
   - `enqueue(type, topic, video_path, thumbnail_path)` — adds to queue with next
     available slot based on the weekly calendar
   - `get_next_upload()` — returns the next video whose scheduled_for <= now
   - `mark_uploaded(id, youtube_id)` — updates status and records YouTube URL
   - `get_pending()` — returns all queued but not yet uploaded videos

3. `schedule_week(topics_list: list)`:
   - Takes a list of topics (can be auto-generated from news trends)
   - Assigns 3 as long-form and the rest as Shorts for the current week
   - Runs the appropriate pipeline for each and adds to the upload queue

4. Add a `make schedule` Makefile target that:
   - Fetches top 10 trending topics from the news API
   - Calls schedule_week() with those topics
   - Prints the weekly calendar to stdout in a readable format

5. Add safeguards:
   - Never upload more than 3 videos in a 24-hour window
   - Add a 30-minute minimum gap between any two uploads
   - If the same topic was uploaded in the last 14 days, skip it (check queue.db)
   - Log every upload decision with timestamp to `output/logs/scheduler.log`

6. Add a daily cron-compatible entry point `scripts/daily_run.py` that:
   - Checks the queue for due uploads
   - Runs any pending pipelines for topics not yet rendered
   - Uploads due videos
   - Sends a summary to a configurable webhook URL (Slack/Discord) if WEBHOOK_URL is set

Update README.md with the full setup and run instructions for the new pipeline.
Do not use placeholder text in the README — write actual instructions.
```

---

## Final integration test prompt

### Antigravity prompt (run this last)

```
Using Planning Mode, run a full end-to-end integration test of the upgraded pipeline.

1. Pick this topic: "Why AI companies are losing money despite record revenues"

2. Run the full longform_pipeline.run_longform_pipeline() with this topic in DRY RUN mode
   (skip the actual YouTube upload — save the would-be upload payload to a JSON file instead).

3. Run the Shorts pipeline on the same topic.

4. Verify and report on:
   - Script length (must be 1,400–1,800 words)
   - Number of B-roll clips fetched (must be ≥8 for long-form, ≥6 for Shorts)
   - Voiceover file duration (must be 8–12 minutes for long-form)
   - Remotion render completed without errors
   - Thumbnail generated (both variants)
   - Best thumbnail selected
   - All output files present in output/renders/

5. Produce a final integration report artifact listing every check with PASS/FAIL status.
   For any FAIL, include the error message and suggested fix.

6. If all checks pass, remove the DRY RUN flag and run one real upload of the Shorts
   version only (not the long-form) as a final production smoke test.
```

---

## Notes on Antigravity-specific workflow

- Use **Planning Mode** for all phases above. This makes the agent produce artifacts
  (implementation plans, task lists) you can review before it executes.
- Use **Fast Mode** only for single-file quick fixes identified during a phase.
- After each phase, leave a comment on the implementation plan artifact saying
  `"Approved — proceed"` or specific feedback. The agent incorporates feedback without
  restarting.
- The **Knowledge Base** feature in Antigravity: after Phase 1, save the codebase audit
  artifact to the Knowledge Base. The agent will reference it in all subsequent phases
  without needing to re-read the whole repo each time.
- If the agent exceeds its context window mid-task, paste the Context Snapshot block
  (from the top of this file) into a new session before continuing.
- **Model recommendation**: Use Gemini 3.1 Pro for Phases 3, 5, 6 (complex multi-file
  work). Use Gemini 3 Flash for Phases 7, 8, 9 (faster, mostly boilerplate work).

---

*Generated for On Trending Today — news-automation repository upgrade*
*Target: 4,000 watch hours via high-retention long-form content*
