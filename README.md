# YT Downloader

A simple, self-contained desktop app to download videos from YouTube and other sites. Works on Windows, macOS, and Linux.

## Features

- **Download videos** in MP4, MKV, WebM, AVI, or MOV format
- **Quality & FPS control** — pick resolution (Max, 1080p, 720p, 480p…) and frame rate
- **Extract audio** — MP3, M4A (AAC), WAV, FLAC, or OGG (Vorbis)
- **Batch download** — queue multiple URLs with individual format settings
- **Trim segments** — download only part of a video using a range slider
- **Custom filename** — override the default title-based name with any template
- **Playlist support** — optionally download entire playlists
- **Subtitle download** — auto-download available subtitles (auto-generated or manual)
- **Auto-update** — checks for new versions on launch and updates in one click
- **Automatic setup** — downloads ffmpeg and deno on first run
- **No dependencies** — everything bundled, nothing to install (when running as an .exe)
- **Real-time progress** — download speed, percent, and status log

## Quick Start

### Option 1: Run with Python

1. Install Python 3.11 or later from [python.org](https://www.python.org/)
2. Download this app folder
3. Run in terminal:
   ```
   python main.py
   ```
4. On first run, the app automatically downloads ffmpeg and deno
5. Paste a YouTube URL, pick your settings, and click Download

### Option 2: Use the Standalone .exe (No Python Required)

1. Download the latest `ytdownloader.exe` from the [Releases](https://github.com/MR-kartoshki/YT-Downloader/releases) page
2. Double-click to run — no installation needed
3. Everything works offline after the first run

## How to Use

1. **Paste a URL** — copy any YouTube link into the URL field, or drag and drop it in
2. **Save as** *(optional)* — enter a custom filename; leave blank to use the video title
3. **Choose type** — select **Video** or **Audio** from the Type dropdown
4. **Video options** (when Video is selected):
   - **Format** — MP4, MKV, WebM, AVI, or MOV
   - **Quality** — Max, 1080p, 720p, 480p, 360p, 240p, or 144p (populated from the video)
   - **FPS** — Max or a specific frame rate (populated from the video)
5. **Audio options** (when Audio is selected):
   - **Codec** — choose your preferred format (see table below)
   - **Bitrate** — Max or a specific bitrate (populated from the video)
6. **Subtitles** — check to download available subtitles
7. **Playlist** — check to download all videos in a playlist instead of just one
8. **Trim** *(optional)* — check Trim and drag the range slider to clip a segment
9. **Output folder** — click **Output…** to choose where files are saved (defaults to Downloads)
10. **Click Download** — watch the progress bar and status log
11. **Open folder** — an "Open Folder" button appears after the download finishes

### Batch Downloading

Click **Batch…** to open the batch window. You can:
- Add multiple URLs, each with its own format, quality, codec, and filename settings
- Paste URLs individually or one per row
- Start all downloads in sequence with one click

### Audio Formats

| Format | Quality | File Size | Best For |
|--------|---------|-----------|----------|
| **MP3** | Good | Medium | General use, maximum compatibility |
| **M4A** | Very Good | Medium | iPhones, iTunes, better quality than MP3 |
| **WAV** | Lossless | Large | Editing, archiving, professional use |
| **FLAC** | Lossless | Medium | Archiving with compression, audiophiles |
| **OGG** | Good | Small | Open-source projects, Linux |

### Video Formats

| Format | Container | Best For |
|--------|-----------|----------|
| **MP4** | MPEG-4 | Universal — plays everywhere |
| **MKV** | Matroska | Best for preserving any codec without re-encoding |
| **WebM** | WebM | Web use, VP8/VP9 + Opus/Vorbis |
| **AVI** | AVI | Legacy compatibility |
| **MOV** | QuickTime | Apple devices and Final Cut Pro |

### Supported Sites

Works with YouTube and hundreds of other sites supported by yt-dlp, including:
- Vimeo
- Dailymotion
- TikTok
- Instagram
- Twitter/X
- And hundreds more (see the full list at [yt-dlp supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md))

### First Run

The app checks for required tools (ffmpeg and deno) on startup:
- **Green dot** = Tool is ready
- **Yellow dot** = Downloading tool (first run only)
- **Red dot** = Tool download failed

If everything is green, you're ready to download. If a dot is yellow, wait a moment for the tool to finish downloading.

## Auto-Update

The app silently checks for a new version 3 seconds after launch. If one is found, an **Update available** button appears in the toolbar. Click it to download and apply the update automatically. The app restarts after updating.

## Troubleshooting

### Download fails or has no audio
Check the **status log** (bottom panel) for error messages. Common issues:
- Invalid or private URL
- Video unavailable or region-restricted
- Network connection issue — try again

### Quality or FPS dropdown only shows "Max"
Quality and FPS options are fetched from the video after you paste a URL. If no options appear, the video info fetch may have failed — check the log.

### App won't start
- Python 3.11+ is installed (if running the Python version)
- Internet is active for the initial tool download
- You have write permission to the app folder

### "No JS runtime found" warning
This is expected on some videos. Deno is bundled to handle JavaScript-protected streams. Downloads should still work.

## Building a Standalone Executable

### Quick Build (Recommended)

**Windows:**
```
python build.py
```

**macOS/Linux:**
```
python build.py
```

Wait 2–5 minutes. Your executable will be in the `dist/` folder:
- Windows: `dist/ytdownloader.exe`
- macOS: `dist/ytdownloader.app`
- Linux: `dist/ytdownloader`

**Windows shortcut:** double-click `build.bat` instead.

### Manual Build

1. Install Python 3.11+ from [python.org](https://www.python.org)
2. Open a terminal in the app folder
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Run the build script:
   ```
   python build.py
   ```
5. Your executable is in `dist/`

### Sharing Your Build

1. Find the executable in `dist/`
2. Send it to friends or upload it online
3. They just double-click it — no folders, no installation

## Settings

### Change Output Folder

Click the **Output…** button to pick where downloads are saved. The current path is shown next to the button. Default is your system Downloads folder.

### Reset Downloaded Tools

Tools are stored in platform-specific locations:
- **Windows**: `C:\tools` (or your system drive, e.g. `D:\tools`)
- **macOS**: `~/.yt-downloader/tools`
- **Linux**: `~/.yt-downloader/tools`

To reset:
```bash
# macOS/Linux
rm -rf ~/.yt-downloader/tools

# Windows (PowerShell)
Remove-Item -Recurse -Force "C:\tools"
```

On next run, the app re-downloads everything automatically.

## Privacy

- All downloads run locally on your computer
- No data is sent to any server (update checks only contact GitHub)
- ffmpeg, deno, and yt-dlp are open-source tools

## License

This app uses:
- **yt-dlp** — open-source video downloader
- **ffmpeg** — open-source audio/video processor
- **deno** — open-source JavaScript runtime
- **PySide6** — cross-platform GUI framework

All included tools are free and open-source.

---

**Made with ❤️ for simple video downloading**
