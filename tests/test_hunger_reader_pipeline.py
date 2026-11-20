import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.hunger_reader_pipeline import build_manifest, build_reader_html, extract_chapters, narration_command


ROOT = Path(__file__).resolve().parents[1]


class HungerReaderPipelineTests(unittest.TestCase):
    def test_epub_extracts_restart_chapters_with_exact_paragraph_offsets(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            chapters = extract_chapters(
                ROOT / "Restart/Restart (1367)/Restart - Gordon Korman.epub", output)
            self.assertEqual([c["number"] for c in chapters], list(range(1, 31)))
            self.assertEqual(chapters[0]["title"], "Chapter 1: Chase Ambrose")
            self.assertEqual(chapters[1]["title"], "Chapter 2: Shoshanna Weber")
            self.assertEqual(chapters[0]["paragraphs"][0]["text"], "I remember falling.")
            self.assertEqual(chapters[-1]["paragraphs"][-1]["text"],
                             "Even Chase Ambrose turning out to be a nice guy.")
            metadata = json.loads((output / "chapters.json").read_text())
            self.assertEqual((metadata["title"], metadata["author"]), ("Restart", "Gordon Korman"))
            for chapter in chapters:
                source = (output / chapter["textFile"]).read_text()
                for paragraph in chapter["paragraphs"]:
                    self.assertEqual(source[paragraph["startChar"]:paragraph["endChar"]], paragraph["text"])
            self.assertIn("everything just stops.", (output / "text/chapter_001.txt").read_text())

    def test_restart_progress_does_not_restore_another_books_position(self):
        reader = build_reader_html({"title": "Restart", "author": "Gordon Korman", "chapters": []})
        self.assertIn("'restart-aligned-reader-progress-v1'", reader)
        self.assertNotIn("hunger-games", reader)

    def test_pdf_extracts_all_chapters_and_maps_paragraph_offsets(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            chapters = extract_chapters(ROOT / "hunger_games_1.pdf", output)
            self.assertEqual([c["number"] for c in chapters], list(range(1, 28)))
            self.assertEqual(chapters[0]["sourceStartPage"], 3)
            self.assertEqual(chapters[-1]["sourceEndPage"], 357)
            self.assertTrue(chapters[0]["paragraphs"][0]["text"].startswith("When I wake up"))
            self.assertTrue(chapters[-1]["paragraphs"][-1]["text"].endswith("have to let go."))
            for chapter in chapters:
                source = (output / chapter["textFile"]).read_text()
                self.assertNotIn("Suzanne Collins", source)
                self.assertNotIn("P a g e", source)
                for paragraph in chapter["paragraphs"]:
                    self.assertEqual(source[paragraph["startChar"]:paragraph["endChar"]], paragraph["text"])
            self.assertIn("flesh-eaters", (output / "text/chapter_001.txt").read_text())

    def test_narration_cache_rejects_audio_from_another_book(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            for name in ("text", "audio", "timings"):
                (output / name).mkdir()
            chapter = {"number": 1, "textFile": "text/chapter_001.txt"}
            (output / chapter["textFile"]).write_text("New book text")
            (output / "audio/chapter_001.mp3").write_bytes(b"x" * 2048)
            stale = {"text": "Old book text", "voice": "voice", "rate": "-5%", "words": [{}]}
            (output / "timings/chapter_001.words.json").write_text(json.dumps(stale))
            def generate(*args, **kwargs):
                (output / "audio/chapter_001.words.json").write_text(json.dumps({**stale, "text": "New book text"}))
            with patch("tools.hunger_reader_pipeline.subprocess.run", side_effect=generate) as run:
                self.assertEqual(narration_command(chapter, output, Path("tts.py"), "voice", "-5%"), (1, "generated"))
                run.assert_called_once()
                self.assertEqual(narration_command(chapter, output, Path("tts.py"), "voice", "-5%"), (1, "cached"))
                run.assert_called_once()

    def test_build_refuses_stale_word_timings(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "audio").mkdir()
            (output / "timings").mkdir()
            (output / "chapter.txt").write_text("New book text")
            metadata = {"title": "The Hunger Games", "author": "Suzanne Collins", "voice": "voice",
                        "chapters": [{"number": 1, "textFile": "chapter.txt"}]}
            (output / "chapters.json").write_text(json.dumps(metadata))
            (output / "audio/chapter_001.mp3").write_bytes(b"x")
            (output / "timings/chapter_001.words.json").write_text(json.dumps({"text": "Old text", "voice": "voice"}))
            with self.assertRaisesRegex(RuntimeError, "Stale narration"):
                build_manifest(output)


if __name__ == "__main__":
    unittest.main()
