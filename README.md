# Restart aligned reader

This project builds a local, searchable read-along edition of Gordon Korman’s
*Restart* from `Restart/Restart (1367)/Restart - Gordon Korman.epub`.
All 30 chapters retain their viewpoint character names and use the supplied
`Restart/001 - Restart.mp3` through `030 - Restart.mp3` audiobook tracks.
Offline forced alignment supplies word timings for synchronized highlighting.

Run the complete, resumable build:

```bash
./run.sh
```

Or run individual stages:

```bash
python3 -m tools.hunger_reader_pipeline extract
python3 -m tools.hunger_reader_pipeline align
python3 -m tools.hunger_reader_pipeline build
```

Open `aligned_reader/index.html` after the build. Audio files remain external to
the HTML in `aligned_reader/audio/`, so keep that directory beside the page.
Search is available from the magnifying-glass button or with Ctrl/Cmd+F.
Click a word to play from it; double-click a word to pause at that position.
Use the playback speed selector (0.75×–2×) to adjust narration speed. Your choice
is remembered across chapters and page reloads.
The top-right hamburger menu adjusts the reading font size (14–30 px) and switches
audio controls between full, speed only, and hidden. These preferences are saved too.

Extraction reads the EPUB’s chapter navigation and preserves paragraph boundaries
and inline text. Alignment requires Aeneas, eSpeak, FFmpeg, and ffprobe. By default,
the installed `~/miniconda3/envs/aeneas39/bin/python` runs Aeneas; override it with
`--alignment-python /path/to/python`. Your original MP3 files are copied unchanged
into the reader. No Edge-TTS or network access is needed for Restart.
Alignment is resumable and cached against the exact text and audio SHA-256 hash.
Use `--workers 3` to control concurrent chapter alignment.
Opening and closing credits remain in the MP3s; their audio is excluded from
the text alignment so it does not shift the story’s highlighting.
Progress and reading preferences are stored separately for each book.

The original Hunger Games PDF extractor is still available with
`python3 -m tools.hunger_reader_pipeline all --book hunger_games_1.pdf --output-dir hunger_reader`.
That legacy PDF workflow uses generated Edge-TTS narration.
# Restart
