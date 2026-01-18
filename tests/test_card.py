import unittest
from unittest.mock import AsyncMock, patch

from bespoke import Card
from bespoke import languages


class TestCard(unittest.TestCase):
    def test_split_into_parts(self) -> None:
        language = languages.JAPANESE
        card = Card(
            id="test",
            sentence="大学生は学生より年上です。",
            native_sentence="A university student is older than a student.",
            audio_filename="audio.ogg",
            slow_audio_filename="slow_audio.ogg",
            native_audio_filename="native_audio.ogg",
            phonetic="だいがくせいはがくせいよりとしうえです。",
            units=["学生", "大学生"],
            unit_tags={"学生": "学生", "大学生": "大学生"},
            notes=[],
        )
        split = [
            ("大学生", "大学生"),
            ("は", None),
            ("学生", "学生"),
            ("より年上です。", None),
        ]
        self.assertEqual(card.split_into_parts(), split)
        split_text = "[大学生](大学生)は[学生](学生)より年上です。"
        str_text = f"Card: {split_text} = {card.native_sentence}"
        self.assertEqual(str(card), str_text)


if __name__ == "__main__":
    unittest.main()
