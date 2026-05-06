# YT Downloader

A simple, self-contained desktop app to download videos from YouTube and other sites. Works on Windows, macOS, and Linux.

## Features

- **Download videos** in MP4 format (best quality)
- **Extract audio** as MP3 from any video
- **Dark theme** GUI that's easy on the eyes
- **Automatic setup** — downloads ffmpeg on first run
- **No dependencies** — everything bundled, nothing to install
- **Progress tracking** — real-time download speed and status

## Quick Start

### Option 1: Run with Python (Easiest)

1. Install Python 3.11 or later from [python.org](https://www.python.org/)
2. Download this app folder
3. Double-click `main.py` or run in terminal:
   ```
   python main.py
   ```
4. On first run, the app will automatically download ffmpeg and deno
5. Paste a YouTube URL, select format (Video or Audio), and click Download

### Option 2: Use the Standalone .exe (No Python Required)

1. Download the latest `ytdownloader.exe` release
2. Double-click to run — no installation needed
3. Everything works offline after first run

## How to Use

1. **Paste a URL** — copy any YouTube link into the "URL" field
2. **Choose format** — select "Video (MP4)" or "Audio (MP3)"
3. **Pick output folder** — click "Output…" to choose where files are saved (defaults to Downloads)
4. **Click Download** — watch the progress bar and status log
5. **Find your file** — it's saved to the output folder with the video title as the filename

### First Run

The app checks for required tools (ffmpeg and deno) on startup:
- **Green dot** = Tool is ready
- **Yellow dot** = Downloading tool (first run only)
- **Red dot** = Tool download failed

If everything is green, you're good to download.

### Supported Sites

Works with YouTube and many other video sites supported by yt-dlp, including:
- Vimeo
- Dailymotion
- TikTok
- Instagram
- Twitter/X
- And hundreds more

## Troubleshooting

### "No JS runtime found" warning
This is normal on some videos. The app has deno built in to handle complex JavaScript protections. Downloads should still work.

### Download fails silently
Check the **status log** (bottom panel) for error messages. Common issues:
- Invalid URL (make sure it's a valid video link)
- Video unavailable or restricted
- Network connection issue — try again

### App won't start
If you get an error on first run, make sure:
- Python 3.11+ is installed (if running Python version)
- Internet connection is active (for tool download)
- You have permission to write to the app folder

## Building a Standalone Executable (for sharing)

Want to create a standalone single executable file to share or distribute?

### Quick Build (Recommended)

**Windows (easiest):**
1. Double-click `build.bat` in the app folder
2. Wait 3-7 minutes (first build is slower for single-file mode)
3. Done! Your `.exe` is in `dist/` folder

**macOS/Linux or Any OS (Python):**
1. Open Terminal in the app folder
2. Run:
   ```
   python build.py
   ```
3. Wait 3-7 minutes
4. Done! Your executable is in `dist/` folder

**macOS (alternative):**
```bash
python build.py
# Creates a standalone app bundle in dist/ytdownloader
```

**Linux (alternative):**
```bash
python build.py
# Creates a standalone binary in dist/ytdownloader
```

### Manual Build (if scripts don't work)

1. Install Python 3.11+ from [python.org](https://www.python.org)
2. Open Command Prompt/PowerShell in the app folder
3. Install build tools:
   ```
   pip install -r requirements.txt
   ```
4. Build the executable:
   ```
   pyinstaller build.spec --onefile
   ```
5. Your single `.exe` file is in `dist/`

### Result

- A **single `.exe` file** — everything bundled into one file
- **No folder needed** — just the one `.exe` to share
- Slower startup (2-3 seconds) than folder mode, but much simpler to distribute
- On first run, it auto-extracts tools and creates a temp folder (cleaned up automatically)

### Sharing Your Build

1. Find `ytdownloader.exe` in the `dist/` folder
2. Send it to friends or upload online
3. They just double-click it and it works
4. No folders, no zipping — just one `.exe` file!

No installation, no dependencies — it just works!

## Settings

### Change Output Folder

Click the **"Output…"** button to pick where downloads are saved. Default is `C:\Users\YourName\Downloads`.

### Remove Downloaded Tools

Tools are stored in platform-specific locations:
- **Windows**: `C:\tools` (or your system drive, e.g., `D:\tools`)
- **macOS**: `~/.yt-downloader/tools` (in your home directory)
- **Linux**: `~/.yt-downloader/tools` (in your home directory)

To reset:
- Delete the `tools/` folder
- On next run, the app re-downloads everything

**Examples:**
```bash
# macOS/Linux
rm -rf ~/.yt-downloader/tools

# Windows (PowerShell)
Remove-Item -Recurse -Force "C:\tools"
```

## Privacy

- All downloads run locally on your computer
- No data is sent to any server
- ffmpeg and deno are open-source tools used to process videos

## Support

If something breaks:
1. Check the **status log** for error details
2. Try restarting the app
3. Delete the `tools/` folder and restart (forces fresh download)
4. Check that your internet connection is working

## License

This app uses:
- **yt-dlp** — open-source video downloader
- **ffmpeg** — open-source audio/video processor
- **deno** — open-source JavaScript runtime
- **PySide6** — cross-platform GUI framework

All included tools are free and open-source.

---

**Made with ❤️ for simple video downloading**
