# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Contains all functions that call LLMs.

If you want to use different models, all you need to modify is this file.
Change the implementation of these functions while keeping their signature.
"""

import abc
import os
import random

import numpy as np
import pydantic
import tenacity
import typing
from bespoke.languages import Language
from bespoke.unit import DictionaryUnit
from bespoke.unit import Difficulty
from bespoke.unit import Unit
from bespoke.unit import UnitTag
from bespoke.unit import UnitTags


DIFFICULTY_EXPLANATIONS = {
    Difficulty.A1: "Beginner, understands and uses simple phrases and sentences.",
    Difficulty.A2: "Basic knowledge of frequently used expressions in areas of immediate relevance.",
    Difficulty.B1: "Intermediate, understands main points of clear standard language.",
    Difficulty.B2: "Independent, can interact with native speakers without strain.",
    Difficulty.C1: "Proficient, can understand demanding, longer clauses and recognise implicit meaning.",
    Difficulty.C2: "Near native, understands virtually everything heard or read with ease.",
}

standard_retry = tenacity.retry(
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=4, min=5, max=300),
)


class SuggestedNamesSchema(pydantic.BaseModel):
    names: list[str]


class DisambiguatedTagSchema(pydantic.BaseModel):
    occurance: str
    word: str
    index: int


class DisambiguatedTagsSchema(pydantic.BaseModel):
    tags: list[DisambiguatedTagSchema]


JAPANESE_SUGGEST_NAMES_EXAMPLES = """
Examples:
Sentence: 私が注目しているのはゲーム業界の成長だ。
Names: ["私", "が", "注目", "する", "いる", "の", "は", "ゲーム", "業界", "成長", "だ"]

Sentence: この店は安くて美味しいし、料理もいい。
Names: ["この", "店", "は", "安い", "美味しい", "おいしい", "し", "料理", "も", "いい", "良い"]

Sentence: 忙しい仕事のスケジュールにしても休日の計画を立てたい。
Names: ["忙しい", "仕事", "の", "スケジュール", "に", "する", "も", "休日", "計画", "を", "立てる"]

Sentence: 計画的に仕事を進めることが重要だ。
Names: ["計画", "的", "計画的", "に", "仕事", "を", "進める", "こと", "事", "が", "重要", "だ"]

Sentence: 最近新しい技術が次々と導入されている。
Names: ["最近", "新しい", "技術", "が", "次々", "と", "導入", "する", "いる"]

Sentence: 彼こそ本当の意味でのリーダーになりやすい人です。
Names: ["彼", "こそ", "本当", "の", "意味", "で", "リーダー", "に", "なる", "やすい", "人", "です"]

Sentence: これといった理由はないはずだ。
Names: ["これ", "と", "言う", "いう", "理由", "は", "ない", "はず", "筈", "だ"]

Sentence: 彼の行動の理由は理解しがたい。
Names: ["彼", "の", "行動", "理由", "は", "理解", "する", "がたい", "だ"]
"""

JAPANESE_TAG_SENTENCE_EXAMPLES = """
Examples of correct tagging for Japanese:

Example 1:
Sentence: 私が注目しているのはゲーム業界の成長だ。
Hints: ["私", "が", "注目", "する", "いる", "の", "は", "ゲーム", "業界", "成長", "だ"]
Tags:
- occurance: "私", unit_id: "私"
- occurance: "が", unit_id: "が"
- occurance: "注目", unit_id: "注目"
- occurance: "して", unit_id: "する"
- occurance: "いる", unit_id: "いる"
- occurance: "の", unit_id: "の"
- occurance: "は", unit_id: "は"
- occurance: "ゲーム", unit_id: "ゲーム"
- occurance: "業界", unit_id: "業界"
- occurance: "の", unit_id: "の"
- occurance: "成長", unit_id: "成長"
- occurance: "だ", unit_id: "だ"

Example 2:
Sentence: この店は安くて美味しいし、料理もいい。
Hints: ["この", "店", "は", "安い", "おいしい", "し", "料理", "も", "良い"]
Tags:
- occurance: "この", unit_id: "この"
- occurance: "店", unit_id: "店"
- occurance: "は", unit_id: "は"
- occurance: "安くて", unit_id: "安い"
- occurance: "美味しい", unit_id: "おいしい"
- occurance: "し", unit_id: "し"
- occurance: "料理", unit_id: "料理"
- occurance: "も", unit_id: "も"
- occurance: "いい", unit_id: "良い"

Example 3:
Sentence: 忙しい仕事のスケジュールにしても休日の計画を立てたい。
Hints: ["忙しい", "仕事", "の", "に", "する", "も", "休日", "計画", "を", "立てる"]
Tags:
- occurance: "忙しい", unit_id: "忙しい"
- occurance: "仕事", unit_id: "仕事"
- occurance: "の", unit_id: "の"
- occurance: "スケジュール", unit_id: "スケジュール"
- occurance: "に", unit_id: "に"
- occurance: "して", unit_id: "する"
- occurance: "も", unit_id: "も"
- occurance: "休日", unit_id: "休日"
- occurance: "の", unit_id: "の"
- occurance: "計画", unit_id: "計画"
- occurance: "を", unit_id: "を"
- occurance: "立てたい", unit_id: "立てる"

Example 4:
Sentence: 計画的に仕事を進めることが重要だ。
Hints: ["計画", "的", "計画的", "に", "仕事", "を", "進める", "こと", "が", "重要", "だ"]
Tags:
- occurance: "計画", unit_id: "計画"
- occurance: "的", unit_id: "的"
- occurance: "に", unit_id: "に"
- occurance: "仕事", unit_id: "仕事"
- occurance: "を", unit_id: "を"
- occurance: "進める", unit_id: "進める"
- occurance: "こと", unit_id: "こと"
- occurance: "が", unit_id: "が"
- occurance: "重要", unit_id: "重要"
- occurance: "だ", unit_id: "だ"

Example 5:
Sentence: 最近新しい技術が次々と導入されている。
Hints: ["最近", "新しい", "技術", "が", "次々", "と", "導入", "する", "いる"]
Tags:
- occurance: "最近", unit_id: "最近"
- occurance: "新しい", unit_id: "新しい"
- occurance: "技術", unit_id: "技術"
- occurance: "が", unit_id: "が"
- occurance: "次々", unit_id: "次々"
- occurance: "と", unit_id: "と"
- occurance: "導入", unit_id: "導入"
- occurance: "されて", unit_id: "する"
- occurance: "いる", unit_id: "いる"

Example 6:
Sentence: 彼こそ本当の意味でのリーダーになりやすい人です。
Hints: ["彼", "こそ", "本当", "の", "意味", "で", "リーダー", "に", "なる", "やすい", "人", "です"]
Tags:
- occurance: "彼", unit_id: "彼"
- occurance: "こそ", unit_id: "こそ"
- occurance: "本当", unit_id: "本当"
- occurance: "の", unit_id: "の"
- occurance: "意味", unit_id: "意味"
- occurance: "で", unit_id: "で"
- occurance: "の", unit_id: "の"
- occurance: "リーダー", unit_id: "リーダー"
- occurance: "に", unit_id: "に"
- occurance: "なり", unit_id: "なる"
- occurance: "やすい", unit_id: "やすい"
- occurance: "人", unit_id: "人"
- occurance: "です", unit_id: "です"

Example 7:
Sentence: これといった理由はないはずだ。
Hints: ["これ", "と", "言う", "理由", "は", "ない", "はず", "だ"]
Tags:
- occurance: "これ", unit_id: "これ"
- occurance: "と", unit_id: "と"
- occurance: "いった", unit_id: "言う"
- occurance: "理由", unit_id: "理由"
- occurance: "は", unit_id: "は"
- occurance: "ない", unit_id: "ない"
- occurance: "はず", unit_id: "はず"
- occurance: "だ", unit_id: "だ"

Example 8:
Sentence: 彼の行動の理由は理解しがたい。
Hints: ["彼", "の", "行動", "理由", "は", "理解", "する", "がたい", "だ"]
Tags:
- occurance: "彼", unit_id: "彼"
- occurance: "の", unit_id: "の"
- occurance: "行動", unit_id: "行動"
- occurance: "の", unit_id: "の"
- occurance: "理由", unit_id: "理由"
- occurance: "は", unit_id: "は"
- occurance: "理解", unit_id: "理解"
- occurance: "し", unit_id: "する"
- occurance: "がたい", unit_id: "がたい"
"""


def _build_suggest_names_prompt(sentence: str, language: Language) -> str:
    japanese_instruction = ""
    if language.code_name == "japanese":
        japanese_instruction = (
            "For Japanese, list dictionary base forms of all content words, "
            "verbs, adjectives, particles, and individual components of "
            "compound words. "
            "If a word is a compound (e.g. 効率的, 予想外, 計画的, 見直し), "
            "list both the compound and its individual component words "
            "(e.g. 効率, 的, 予想, 外, 計画, 見直す). "
            "For verbs and adjectives, provide all dictionary/base forms "
            "(e.g. 忘れる and しまう for 忘れてしまう, 発生 and する for "
            "発生したい, 言う for いう/といった/といえば/という). "
            "For verbs or adjectives with auxiliary suffixes (e.g. -やすい, "
            "-にくい, -づらい, -がたい, -がち, -だらけ, -っぱなし, -たて, "
            "-べからず, -かねる, -すぎる, -たい, -そう), output both the base "
            "dictionary form of the verb/adjective (e.g. 見る for 見やすい, "
            "なる for なりやすい, 理解 and する for 理解しがたい, 忙しい for "
            "忙しすぎて) and the suffix/grammar word itself (e.g. やすい, "
            "がたい, すぎる). "
            "Create hiragana and possible multiple kanji versions of the "
            "word, if both are used. \n"
            f"{JAPANESE_SUGGEST_NAMES_EXAMPLES}\n"
        )
    return (
        f"Given is a sentence in {language.writing_system}: \n{sentence} \n"
        "List all base forms of words in the sentence. "
        f"{japanese_instruction}"
    )


def _build_tag_sentence_prompt(
    sentence: str,
    language: Language,
    hint: list[Unit],
    marked_sentence: str | None = None,
    existing_tags: list[UnitTag] | None = None,
) -> str:
    hints_str = "\n".join(u.id() for u in hint)
    uses_dictionary_unit = bool(hint and isinstance(hint[0], DictionaryUnit))
    equal_occurance_text = ""
    examples_text = ""
    if language.code_name in ["simp_chinese", "trad_chinese"]:
        equal_occurance_text = "The occurance needs to exactly match the "
        if uses_dictionary_unit:
            equal_occurance_text += 'part of unit ID before " - ". '
        else:
            equal_occurance_text += "unit ID. "
    else:
        equal_occurance_text = (
            "You may leave words, particles or grammatical word parts "
            "untagged if there is no good matching unit in the hints. "
            "Do not invent or force tags for unlisted words. "
        )
        if language.code_name == "japanese":
            equal_occurance_text += (
                "For Japanese, grammatical endings of words "
                "(such as verb or adjective inflections like -た, -たり, "
                "-て, -ます, -ない) should be included in the occurrence "
                "of the word stem, but particles (such as を, に, は, が, で, "
                "と) must NOT be included in verb or adjective occurrences. "
                "For suru-verbs (Noun + する), tag the full inflection of する "
                "as unit する. "
                "Compound or consecutive particles (such as よりも, さえも, "
                "には, とは, からも, だけの) may be split into separate "
                "individual particle tags (e.g. tag より as より and "
                "も as も). \n"
            )
            examples_text = f"{JAPANESE_TAG_SENTENCE_EXAMPLES}\n"
    unit_id_shape_text = ""
    if uses_dictionary_unit:
        unit_id_shape_text = (
            'Output unit IDs in the format of the examples: "NAME - DEFINITION"'
        )
    only_missing_text = ""
    if marked_sentence:
        only_missing_text = (
            "Only the parts enclosed in brackets `[]` need to be tagged. "
            f"The rest is already tagged correctly: \n{marked_sentence}\n"
        )
    existing_tags_text = ""
    if existing_tags:
        existing_tags_list = "\n".join(
            f"- {tag.occurance} -> {tag.unit_id}" for tag in existing_tags
        )
        existing_tags_text = (
            "The following tags were identified in previous rounds:\n"
            f"{existing_tags_list}\n"
            "You can keep correct tags, correct mistakes, and add tags for "
            "untagged parts of the sentence using the provided unit IDs.\n"
        )

    return (
        f"Given is a sentence in {language.writing_system}: \n{sentence} \n"
        f"{only_missing_text}"
        f"{existing_tags_text}"
        "I want to tag the words in this sentence with vocabulary. "
        "From the suggested unit IDs, find which best fits the occurance in "
        "the sentence. \n"
        f"The tags are a list of occurrences and unit IDs. {equal_occurance_text}\n"
        f"{examples_text}"
        "Output them in order of occurance without overlap. \n"
        "Unit IDs need to precisely match our stored IDs, so stick to the "
        "example format. "
        f"{unit_id_shape_text}"
        "The following are example unit IDs, each line is exactly one unit ID:\n"
        f"{hints_str}\n"
    )


class LlmClient(abc.ABC):
    @abc.abstractmethod
    async def text_call(self, prompt: str) -> str:
        """Sends a prompt to the LLM and returns the text response."""

    async def translate(self, sentence: str, language: Language) -> str:
        """Translates a sentence to the given language."""
        prompt = (
            "Translate the following sentence to "
            f"{language.writing_system}: \n{sentence} \n"
            "Only respond with the translation, no introduction or explanations."
        )
        return await self.text_call(prompt)

    async def to_phonetic(self, sentence: str, language: Language) -> str | None:
        """Converts a sentence to its phonetic representation."""
        if not language.phonetic_system:
            return None

        prompt = (
            "Take the following sentence and convert it to "
            f"{language.phonetic_system}. "
            "Don't add any introduction or explanations, just the pure response. "
            f"The sentence is: \n{sentence}"
        )
        return await self.text_call(prompt)

    @abc.abstractmethod
    async def create_sentences(
        self,
        language: Language,
        difficulty: Difficulty,
        grammar: str,
        units: list[Unit],
    ) -> list[str]:
        """Creates sentences using specific vocabulary and grammar."""

    @abc.abstractmethod
    async def suggest_names(self, sentence: str, language: Language) -> list[str]:
        """Lists all base forms of words in the sentence."""

    @abc.abstractmethod
    async def tag_sentence(
        self,
        sentence: str,
        language: Language,
        hint: list[Unit],
        marked_sentence: str | None = None,
        existing_tags: list[UnitTag] | None = None,
    ) -> UnitTags:
        """Tags words in a sentence with their dictionary form."""

    @abc.abstractmethod
    async def speak(
        self,
        sentence: str,
        *,
        slowly: bool = False,
    ) -> np.ndarray:
        """Converts text to speech."""


class GeminiLlmClient(LlmClient):
    TEXT_MODEL = "gemini-3.5-flash-lite"
    SPEAK_MODEL = "gemini-3.1-flash-tts-preview"
    VOICES = [
        "Aoede",
        "Achernar",
        "Achird",
        "Algenib",
        "Algieba",
        "Alnilam",
        "Autonoe",
        "Callirrhoe",
        "Charon",
        "Despina",
        "Enceladus",
        "Erinome",
        "Fenrir",
        "Gacrux",
        "Iapetus",
        "Kore",
        "Laomedeia",
        "Leda",
        "Orus",
        "Puck",
        "Pulcherrima",
        "Rasalgethi",
        "Sadachbia",
        "Sadaltager",
        "Schedar",
        "Sulafat",
        "Umbriel",
        "Vindemiatrix",
        "Zephyr",
        "Zubenelgenubi",
    ]

    def __init__(self, api_key: str):
        self._api_key = api_key
        from google import genai

        self._genai = genai
        self._client = genai.Client(api_key=api_key)

    @standard_retry
    async def text_call(self, prompt: str) -> str:
        response = await self._client.aio.models.generate_content(
            model=self.TEXT_MODEL,
            contents=[prompt],
            config=self._genai.types.GenerateContentConfig(
                response_modalities=["TEXT"],
            ),
        )
        if response.text is None:
            raise ValueError("Missing content")
        return response.text.strip()

    @standard_retry
    async def create_sentences(
        self,
        language: Language,
        difficulty: Difficulty,
        grammar: str,
        units: list[Unit],
    ) -> list[str]:
        difficulty_explanation = DIFFICULTY_EXPLANATIONS[difficulty]
        if language.name in ["Chinese", "Japanese"]:
            spaces = "or with spaces "
        else:
            spaces = ""
        unit_infos = [str(u) for u in units]
        prompt = (
            f"Create example sentences in the language {language.writing_system}. "
            f"The output should be exactly {len(units)} lines. "
            "Each line will be interpreted as a sentence. "
            f"Don't add numbering. Don't mark words as bold {spaces}etc. "
            "Only respond with the sentences, no introduction or explanations. "
            "The sentences should represent how native speakers naturally talk. \n"
            "All sentences together should use the following words as defined: \n"
            f"{unit_infos} \n"
            "All words should occur with the meaning matching their definition. "
            "If the word is part of a longer compound word, don't use the compound. "
            "Make the sentences unique and different. "
            "Use correct punctuation. "
            f"All sentences should use this grammar concept: \n{grammar} \n"
            f"The target difficulty of the sentence is {difficulty}. "
            f"This difficulty level is defined as: \n{difficulty_explanation}"
        )

        response = await self._client.aio.models.generate_content(
            model=self.TEXT_MODEL,
            contents=[prompt],
            config=self._genai.types.GenerateContentConfig(
                response_modalities=["TEXT"],
            ),
        )
        if response.text is None:
            raise ValueError("Missing content")
        sentences = [s.strip() for s in response.text.strip().split("\n")]
        return [s for s in sentences if s]

    @standard_retry
    async def suggest_names(self, sentence: str, language: Language) -> list[str]:
        prompt = _build_suggest_names_prompt(sentence, language)
        response = await self._client.aio.models.generate_content(
            model=self.TEXT_MODEL,
            contents=[prompt],
            config=self._genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SuggestedNamesSchema,
            ),
        )
        if response.parsed is None:
            raise ValueError("Missing content")
        parsed = typing.cast(SuggestedNamesSchema, response.parsed)
        return parsed.names

    @standard_retry
    async def tag_sentence(
        self,
        sentence: str,
        language: Language,
        hint: list[Unit],
        marked_sentence: str | None = None,
        existing_tags: list[UnitTag] | None = None,
    ) -> UnitTags:
        prompt = _build_tag_sentence_prompt(
            sentence=sentence,
            language=language,
            hint=hint,
            marked_sentence=marked_sentence,
            existing_tags=existing_tags,
        )
        response = await self._client.aio.models.generate_content(
            model=self.TEXT_MODEL,
            contents=[prompt],
            config=self._genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=UnitTags,
            ),
        )
        if response.parsed is None:
            raise ValueError("Missing content")
        return typing.cast(UnitTags, response.parsed)

    @standard_retry
    async def speak(
        self,
        sentence: str,
        *,
        slowly: bool = False,
    ) -> np.ndarray:
        voice_name = random.choice(self.VOICES)
        if slowly:
            instruction = "Speak slowly: "
        else:
            instruction = "Speak: "
        text = f"{instruction}{sentence}"
        response = await self._client.aio.models.generate_content(
            model=self.SPEAK_MODEL,
            contents=[
                self._genai.types.Content(
                    role="user",
                    parts=[
                        self._genai.types.Part.from_text(text=text),
                    ],
                ),
            ],
            config=self._genai.types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=self._genai.types.SpeechConfig(
                    voice_config=self._genai.types.VoiceConfig(
                        prebuilt_voice_config=self._genai.types.PrebuiltVoiceConfig(
                            voice_name=voice_name,
                        )
                    )
                ),
            ),
        )
        audio_data = []
        if not response.candidates:
            raise ValueError("Missing candidates")
        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            raise ValueError("Missing content")

        for part in candidate.content.parts:
            if part.inline_data:
                if part.inline_data.data is None:
                    raise ValueError("Missing inline data")
                audio_data.append(np.frombuffer(part.inline_data.data, dtype=np.int16))
        if not audio_data:
            raise ValueError("Empty response")
        return np.concatenate(audio_data)


class OpenRouterElevenLabsLlmClient(LlmClient):
    TEXT_MODEL = "openrouter/google/gemma-2-9b-it"
    ELEVENLABS_MODEL = "eleven_multilingual_v2"
    ELEVENLABS_VOICES = [
        "21m00Tcm4TlvDq8ikWAM",  # Rachel
        "AZnzlk1XvdvUeBnXmlld",  # Domi
        "EXAVITQu4vr4xnSDxMaL",  # Bella
        "ErXwobaYiN019PkySvjV",  # Antoni
        "MF3mGyEYCl7XYWbV9V6O",  # Elli
        "TxGEqnHWrfWFTfGW9XjX",  # Josh
        "VR6AewLTigWg4xSOukaG",  # Arnold
        "pNInz6obpgDQGcFmaJgB",  # Adam
        "yoZ06aMxZJJ28mfd3POQ",  # Sam
    ]

    def __init__(self, openrouter_api_key: str, elevenlabs_api_key: str):
        self.openrouter_api_key = openrouter_api_key
        self.elevenlabs_api_key = elevenlabs_api_key
        import httpx
        import litellm

        litellm.suppress_debug_info = True

        self._httpx = httpx
        self._litellm = litellm

    @standard_retry
    async def text_call(self, prompt: str) -> str:
        response = await self._litellm.acompletion(
            model=self.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            api_key=self.openrouter_api_key,
        )
        return response.choices[0].message.content.strip()

    @standard_retry
    async def create_sentences(
        self,
        language: Language,
        difficulty: Difficulty,
        grammar: str,
        units: list[Unit],
    ) -> list[str]:
        difficulty_explanation = DIFFICULTY_EXPLANATIONS[difficulty]
        if language.name in ["Chinese", "Japanese"]:
            spaces = "or with spaces "
        else:
            spaces = ""
        unit_infos = [u.definition() for u in units]
        prompt = (
            f"Create example sentences in the language {language.writing_system}. "
            f"The output should be exactly {len(units)} lines. "
            "Each line will be interpreted as a sentence. "
            f"Don't add numbering. Don't mark words as bold {spaces}etc. "
            "Only respond with the sentences, no introduction or explanations. "
            "The sentences should represent how native speakers naturally talk. \n"
            "All sentences together should use the following words as defined: \n"
            f"{unit_infos} \n"
            "All words should occur with the meaning matching their definition. "
            "If the word is part of a longer compound word, don't use the compound. "
            "Make the sentences unique and different. "
            "Use correct punctuation. "
            f"All sentences should use this grammar concept: \n{grammar} \n"
            f"The target difficulty of the sentence is {difficulty}. "
            f"This difficulty level is defined as: \n{difficulty_explanation}"
        )

        response = await self._litellm.acompletion(
            model=self.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            api_key=self.openrouter_api_key,
        )
        sentences = [
            s.strip() for s in response.choices[0].message.content.strip().split("\n")
        ]
        return [s for s in sentences if s]

    @standard_retry
    async def suggest_names(self, sentence: str, language: Language) -> list[str]:
        prompt = _build_suggest_names_prompt(sentence, language)
        prompt += "Respond with a JSON list of strings."
        response = await self._litellm.acompletion(
            model=self.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format=SuggestedNamesSchema,
            api_key=self.openrouter_api_key,
        )
        content = response.choices[0].message.content
        parsed = SuggestedNamesSchema.model_validate_json(content)
        return parsed.names

    @standard_retry
    async def tag_sentence(
        self,
        sentence: str,
        language: Language,
        hint: list[Unit],
        marked_sentence: str | None = None,
        existing_tags: list[UnitTag] | None = None,
    ) -> UnitTags:
        prompt = _build_tag_sentence_prompt(
            sentence=sentence,
            language=language,
            hint=hint,
            marked_sentence=marked_sentence,
            existing_tags=existing_tags,
        )
        response = await self._litellm.acompletion(
            model=self.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format=UnitTags,
            api_key=self.openrouter_api_key,
        )
        content = response.choices[0].message.content
        return pydantic.TypeAdapter(UnitTags).validate_json(content)

    @standard_retry
    async def speak(
        self,
        sentence: str,
        *,
        slowly: bool = False,
    ) -> np.ndarray:
        voice_id = random.choice(self.ELEVENLABS_VOICES)
        url = (
            "https://api.elevenlabs.io/v1/text-to-speech/"
            f"{voice_id}?output_format=pcm_16000"
        )
        headers = {
            "xi-api-key": self.elevenlabs_api_key,
            "Content-Type": "application/json",
        }
        data = {"text": sentence, "model_id": self.ELEVENLABS_MODEL}
        try:
            async with self._httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                return np.frombuffer(response.content, dtype=np.int16)
        except self._httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"ElevenLabs TTS failed: HTTP {e.response.status_code}"
            ) from None


class OpenAiLlmClient(LlmClient):
    TEXT_MODEL = "gpt-4o-mini"
    SPEAK_MODEL = "tts-1"
    VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

    def __init__(self, api_key: str):
        self._api_key = api_key
        import litellm

        self._litellm = litellm
        self._litellm.suppress_debug_info = True

    @standard_retry
    async def text_call(self, prompt: str) -> str:
        response = await self._litellm.acompletion(
            model=self.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            api_key=self._api_key,
        )
        return response.choices[0].message.content.strip()

    @standard_retry
    async def create_sentences(
        self,
        language: Language,
        difficulty: Difficulty,
        grammar: str,
        units: list[Unit],
    ) -> list[str]:
        difficulty_explanation = DIFFICULTY_EXPLANATIONS[difficulty]
        if language.name in ["Chinese", "Japanese"]:
            spaces = "or with spaces "
        else:
            spaces = ""
        unit_infos = [u.definition() for u in units]
        prompt = (
            f"Create example sentences in the language {language.writing_system}. "
            f"The output should be exactly {len(units)} lines. "
            "Each line will be interpreted as a sentence. "
            f"Don't add numbering. Don't mark words as bold {spaces}etc. "
            "Only respond with the sentences, no introduction or explanations. "
            "The sentences should represent how native speakers naturally talk. \n"
            "All sentences together should use the following words as defined: \n"
            f"{unit_infos} \n"
            "All words should occur with the meaning matching their definition. "
            "If the word is part of a longer compound word, don't use the compound. "
            "Make the sentences unique and different. "
            "Use correct punctuation. "
            f"All sentences should use this grammar concept: \n{grammar} \n"
            f"The target difficulty of the sentence is {difficulty}. "
            f"This difficulty level is defined as: \n{difficulty_explanation}"
        )

        response = await self._litellm.acompletion(
            model=self.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            api_key=self._api_key,
        )
        sentences = [
            s.strip() for s in response.choices[0].message.content.strip().split("\n")
        ]
        return [s for s in sentences if s]

    @standard_retry
    async def suggest_names(self, sentence: str, language: Language) -> list[str]:
        prompt = _build_suggest_names_prompt(sentence, language)
        prompt += "Respond with a JSON list of strings."
        response = await self._litellm.acompletion(
            model=self.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format=SuggestedNamesSchema,
            api_key=self._api_key,
        )
        content = response.choices[0].message.content
        parsed = SuggestedNamesSchema.model_validate_json(content)
        return parsed.names

    @standard_retry
    async def tag_sentence(
        self,
        sentence: str,
        language: Language,
        hint: list[Unit],
        marked_sentence: str | None = None,
        existing_tags: list[UnitTag] | None = None,
    ) -> UnitTags:
        prompt = _build_tag_sentence_prompt(
            sentence=sentence,
            language=language,
            hint=hint,
            marked_sentence=marked_sentence,
            existing_tags=existing_tags,
        )
        response = await self._litellm.acompletion(
            model=self.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format=UnitTags,
            api_key=self._api_key,
        )
        content = response.choices[0].message.content
        return pydantic.TypeAdapter(UnitTags).validate_json(content)

    @standard_retry
    async def speak(
        self,
        sentence: str,
        *,
        slowly: bool = False,
    ) -> np.ndarray:
        voice_name = random.choice(self.VOICES)
        response = await self._litellm.aspeech(
            model=self.SPEAK_MODEL,
            voice=voice_name,
            input=sentence,
            api_key=self._api_key,
        )
        return np.frombuffer(response.content, dtype=np.int16)


def get_llm_client() -> LlmClient:
    """Returns an LLM client based on available API keys."""
    if api_key := os.environ.get("GEMINI_API_KEY"):
        return GeminiLlmClient(api_key)
    elif api_key := os.environ.get("OPENROUTER_API_KEY"):
        elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY")
        if not elevenlabs_key:
            raise ValueError(
                "OPENROUTER_API_KEY found but ELEVENLABS_API_KEY is missing."
            )
        return OpenRouterElevenLabsLlmClient(api_key, elevenlabs_key)
    elif api_key := os.environ.get("OPENAI_API_KEY"):
        return OpenAiLlmClient(api_key)
    else:
        raise ValueError(
            "No API key found. Please set GEMINI_API_KEY, "
            "OPENAI_API_KEY, or OPENROUTER_API_KEY and ELEVENLABS_API_KEY."
        )
