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


class LlmClient(abc.ABC):
    @abc.abstractmethod
    async def translate(self, sentence: str, language: Language) -> str:
        """Translates a sentence to the given language."""

    @abc.abstractmethod
    async def to_phonetic(self, sentence: str, language: Language) -> str | None:
        """Converts a sentence to its phonetic representation."""

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
    TEXT_MODEL = "gemini-3.1-flash-lite"
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
    async def translate(self, sentence: str, language: Language) -> str:
        prompt = (
            "Translate the following sentence to "
            f"{language.writing_system}: \n{sentence} \n"
            "Only respond with the translation, no introduction or explanations."
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
        return response.text.strip()

    @standard_retry
    async def to_phonetic(self, sentence: str, language: Language) -> str | None:
        if not language.phonetic_system:
            return None

        prompt = (
            "Take the following sentence and convert it to "
            f"{language.phonetic_system}. "
            "Don't add any introduction or explanations, just the pure response. "
            f"The sentence is: \n{sentence}"
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
            f"All sentences together should use the following words as defined: \n{unit_infos} \n"
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
        prompt = (
            f"Given is a sentence in {language.writing_system}: \n{sentence} \n"
            "List all base forms of words in the sentence. "
        )

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
    ) -> UnitTags:
        hints_str = "\n".join(u.id() for u in hint)
        uses_dictionary_unit = hint and isinstance(hint[0], DictionaryUnit)
        equal_occurance_text = ""
        if language.code_name in ["simp_chinese", "trad_chinese"]:
            equal_occurance_text = "The occurance needs to exactly match the "
            if uses_dictionary_unit:
                equal_occurance_text += 'part of unit ID before " - ". '
            else:
                equal_occurance_text += "unit ID. "
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

        prompt = (
            f"Given is a sentence in {language.writing_system}: \n{sentence} \n"
            f"{only_missing_text}"
            "I want to tag all words in each sentence with vocabulary. \n"
            "For each unit suggested in the hints, find its occurrence in the sentence. \n"
            f"The tags are a list of occurrences and unit IDs. {equal_occurance_text}\n"
            "Output them in order of occurance without overlap. \n"
            "Unit IDs need to precisely match our stored IDs, so stick to the example format. "
            f"{unit_id_shape_text}"
            f"The following are example unit IDs, each line is exactly one unit ID:\n{hints_str}\n"
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
            instruction = "Speak like a voice actor: "
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
    async def translate(self, sentence: str, language: Language) -> str:
        prompt = (
            "Translate the following sentence to "
            f"{language.writing_system}: \n{sentence} \n"
            "Only respond with the translation, no introduction or explanations."
        )

        response = await self._litellm.acompletion(
            model=self.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            api_key=self.openrouter_api_key,
        )
        return response.choices[0].message.content.strip()

    @standard_retry
    async def to_phonetic(self, sentence: str, language: Language) -> str | None:
        if not language.phonetic_system:
            return None

        prompt = (
            "Take the following sentence and convert it to "
            f"{language.phonetic_system}. "
            "Don't add any introduction or explanations, just the pure response. "
            f"The sentence is: \n{sentence}"
        )

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
            f"All sentences together should use the following words as defined: \n{unit_infos} \n"
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
        prompt = (
            f"Given is a sentence in {language.writing_system}: \n{sentence} \n"
            "List all base forms of words in the sentence. "
            "Respond with a JSON list of strings."
        )

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
    ) -> UnitTags:
        hints_str = "\n".join(u.id() for u in hint)
        uses_dictionary_unit = hint and isinstance(hint[0], DictionaryUnit)
        equal_occurance_text = ""
        if language.code_name in ["simp_chinese", "trad_chinese"]:
            equal_occurance_text = "The occurance needs to exactly match the "
            if uses_dictionary_unit:
                equal_occurance_text += 'part of unit ID before " - ". '
            else:
                equal_occurance_text += "unit ID. "
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

        prompt = (
            f"Given is a sentence in {language.writing_system}: \n{sentence} \n"
            f"{only_missing_text}"
            "I want to tag all words in each sentence with vocabulary. \n"
            "For each unit suggested in the hints, find its occurrence in the sentence. \n"
            f"The tags are a list of occurrences and unit IDs. {equal_occurance_text}\n"
            "Output them in order of occurance without overlap. \n"
            "Unit IDs need to precisely match our stored IDs, so stick to the example format. "
            f"{unit_id_shape_text}"
            f"The following are example unit IDs, each line is exactly one unit ID:\n{hints_str}\n"
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
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=pcm_16000"
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
    async def translate(self, sentence: str, language: Language) -> str:
        prompt = (
            "Translate the following sentence to "
            f"{language.writing_system}: \n{sentence} \n"
            "Only respond with the translation, no introduction or explanations."
        )

        response = await self._litellm.acompletion(
            model=self.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            api_key=self._api_key,
        )
        return response.choices[0].message.content.strip()

    @standard_retry
    async def to_phonetic(self, sentence: str, language: Language) -> str | None:
        if not language.phonetic_system:
            return None

        prompt = (
            "Take the following sentence and convert it to "
            f"{language.phonetic_system}. "
            "Don't add any introduction or explanations, just the pure response. "
            f"The sentence is: \n{sentence}"
        )

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
            f"All sentences together should use the following words as defined: \n{unit_infos} \n"
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
        prompt = (
            f"Given is a sentence in {language.writing_system}: \n{sentence} \n"
            "List all base forms of words in the sentence. "
            "Respond with a JSON list of strings."
        )

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
        hint: typing.Sequence[Unit],
        marked_sentence: str | None = None,
    ) -> UnitTags:
        hints_str = "\n".join(u.id() for u in hint)
        uses_dictionary_unit = hint and isinstance(hint[0], DictionaryUnit)
        equal_occurance_text = ""
        if language.code_name in ["simp_chinese", "trad_chinese"]:
            equal_occurance_text = "The occurance needs to exactly match the "
            if uses_dictionary_unit:
                equal_occurance_text += 'part of unit ID before " - ". '
            else:
                equal_occurance_text += "unit ID. "
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

        prompt = (
            f"Given is a sentence in {language.writing_system}: \n{sentence} \n"
            f"{only_missing_text}"
            "I want to tag all words in each sentence with vocabulary. \n"
            "For each unit suggested in the hints, find its occurrence in the sentence. \n"
            f"The tags are a list of occurrences and unit IDs. {equal_occurance_text}\n"
            "Output them in order of occurance without overlap. \n"
            "Unit IDs need to precisely match our stored IDs, so stick to the example format. "
            f"{unit_id_shape_text}"
            f"The following are example unit IDs, each line is exactly one unit ID:\n{hints_str}\n"
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
