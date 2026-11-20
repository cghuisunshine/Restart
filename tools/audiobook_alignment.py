"""Align an EPUB's exact word spans to existing audiobook tracks, offline."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


VOICE = "Original audiobook"
METHOD = "aeneas-multilevel-words-v1"


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def map_word_timings(text: str, sync_map: dict) -> list[dict]:
    fragments = sync_map["fragments"]
    tokens = list(re.finditer(r"\S+", text))
    if len(fragments) != len(tokens):
        raise ValueError(f"Alignment has {len(fragments)} words; expected {len(tokens)}")
    words = []
    previous_end = 0.0
    for token, fragment in zip(tokens, fragments):
        if " ".join(fragment["lines"]) != token.group():
            raise ValueError(f"Alignment text mismatch at character {token.start()}")
        begin, end = float(fragment["begin"]), float(fragment["end"])
        if begin < previous_end - 0.001 or end < begin:
            raise ValueError(f"Nonmonotonic alignment at character {token.start()}")
        words.append({"text": token.group(), "start": begin, "end": end,
                      "duration": round(end - begin, 6),
                      "start_char": token.start(), "end_char": token.end()})
        previous_end = end
    return words


def align_chapter(chapter: dict, output_dir: Path, audio_dir: Path,
                  python: Path, work_dir: Path) -> tuple[int, str]:
    number = chapter["number"]
    source = audio_dir / f"{number:03d} - Restart.mp3"
    text_path = output_dir / chapter["textFile"]
    text = text_path.read_text(encoding="utf-8")
    basename = f"chapter_{number:03d}"
    audio_path = output_dir / "audio" / f"{basename}.mp3"
    timing_path = output_dir / "timings" / f"{basename}.words.json"
    fingerprint = file_hash(source)
    # Measured from the supplied audiobook: Chapter 1 starts after the opening
    # credits; the story ends before the publisher/Audible credits in track 30.
    head = 30.0 if number == 1 else 0.0
    tail = 49.0 if number == 30 else 0.0
    region = (f"|is_audio_file_head_length={head:.3f}" if head else "")
    region += (f"|is_audio_file_tail_length={tail:.3f}" if tail else "")
    if timing_path.exists():
        cached = json.loads(timing_path.read_text(encoding="utf-8"))
        if (cached.get("text") == text and cached.get("sourceAudioSha256") == fingerprint
                and cached.get("alignment") == METHOD and cached.get("words")
                and cached.get("alignmentHead", 0) == head
                and cached.get("alignmentTail", 0) == tail):
            if not audio_path.exists() or file_hash(audio_path) != fingerprint:
                shutil.copy2(source, audio_path)
            return number, "cached"
    key = hashlib.sha256((METHOD + fingerprint + text + region).encode()).hexdigest()[:16]
    raw_map = work_dir / f"{basename}-{key}.json"
    log_path = raw_map.with_suffix(".log")
    if not raw_map.exists():
        config = ("task_language=eng|is_text_type=mplain|os_task_file_format=json|"
                  "os_task_file_levels=3|task_adjust_boundary_no_zero=True" + region)
        command = [str(python), "-u", "-m", "aeneas.tools.execute_task", str(source),
                   str(text_path), config, str(raw_map), "--presets-word"]
        with log_path.open("w", encoding="utf-8") as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f"Chapter {number} alignment failed; see {log_path}")
    words = map_word_timings(text, json.loads(raw_map.read_text(encoding="utf-8")))
    payload = {"text": text, "voice": VOICE, "audio": audio_path.name,
               "alignment": METHOD, "sourceAudio": str(source),
               "alignmentHead": head, "alignmentTail": tail,
               "sourceAudioSha256": fingerprint, "words": words}
    # Install only after the complete alignment has been validated.
    shutil.copy2(source, audio_path)
    temporary = timing_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(timing_path)
    return number, "aligned"


def align_audiobook(output_dir: Path, audio_dir: Path, python: Path,
                    workers: int = 2, chapter_range=None) -> None:
    if not python.exists():
        raise FileNotFoundError(f"Aeneas Python not found: {python}; set --alignment-python")
    metadata_path = output_dir / "chapters.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    chapters = metadata["chapters"]
    if chapter_range:
        first, last = chapter_range
        chapters = [c for c in chapters if first <= c["number"] <= last]
        if not chapters:
            raise ValueError(f"No chapters in range {first}-{last}")
    for chapter in chapters:
        source = audio_dir / f"{chapter['number']:03d} - Restart.mp3"
        if not source.exists():
            raise FileNotFoundError(source)
    for name in ("audio", "timings"):
        (output_dir / name).mkdir(parents=True, exist_ok=True)
    work_dir = output_dir.parent / ".reader-build" / "alignment"
    work_dir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(align_chapter, c, output_dir, audio_dir, python, work_dir)
                   for c in chapters]
        for future in as_completed(futures):
            number, status = future.result()
            print(f"Chapter {number:02d}: {status}", flush=True)
    metadata["voice"] = VOICE
    metadata["alignment"] = METHOD
    metadata.pop("rate", None)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
