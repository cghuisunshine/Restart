import unittest
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.audiobook_alignment import align_chapter, map_word_timings


class AudiobookAlignmentTests(unittest.TestCase):
    def test_preserves_original_audio_and_invalidates_changed_audio_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("audio", "timings", "source", "work"):
                (root / name).mkdir()
            text = "Chapter 2.\n\nHello."
            (root / "chapter.txt").write_text(text)
            source = root / "source/002 - Restart.mp3"
            source.write_bytes(b"original audiobook bytes")
            chapter = {"number": 2, "textFile": "chapter.txt"}

            def align(command, **kwargs):
                fragments = [{"lines": [token], "begin": str(i), "end": str(i+1)}
                             for i, token in enumerate(text.split())]
                Path(command[-2]).write_text(json.dumps({"fragments": fragments}))
                return SimpleNamespace(returncode=0)

            with patch("tools.audiobook_alignment.subprocess.run", side_effect=align) as run:
                args = (chapter, root, root / "source", Path("python"), root / "work")
                self.assertEqual(align_chapter(*args), (2, "aligned"))
                self.assertEqual((root / "audio/chapter_002.mp3").read_bytes(), source.read_bytes())
                self.assertEqual(align_chapter(*args), (2, "cached"))
                run.assert_called_once()
                source.write_bytes(b"updated original audiobook bytes")
                self.assertEqual(align_chapter(*args), (2, "aligned"))
                self.assertEqual(run.call_count, 2)
                self.assertEqual((root / "audio/chapter_002.mp3").read_bytes(), source.read_bytes())

    def test_maps_exact_source_spans_without_changing_punctuation(self):
        text = "Chapter 1.\n\n“I remember”—falling."
        tokens = text.split()
        sync = {"fragments": [{"lines": [token], "begin": str(30 + i),
                               "end": str(31 + i)} for i, token in enumerate(tokens)]}
        words = map_word_timings(text, sync)
        self.assertEqual(words[0]["start"], 30)
        for word in words:
            self.assertEqual(text[word["start_char"]:word["end_char"]], word["text"])

    def test_rejects_missing_words(self):
        with self.assertRaisesRegex(ValueError, "expected 2"):
            map_word_timings("Two words", {"fragments": []})

    def test_rejects_different_text_and_backward_timestamps(self):
        with self.assertRaisesRegex(ValueError, "text mismatch"):
            map_word_timings("Restart", {"fragments": [
                {"lines": ["Other"], "begin": "0", "end": "1"}]})
        with self.assertRaisesRegex(ValueError, "Nonmonotonic"):
            map_word_timings("Restart", {"fragments": [
                {"lines": ["Restart"], "begin": "2", "end": "1"}]})


if __name__ == "__main__":
    unittest.main()
