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
from bespoke.languages import Difficulty
from bespoke.languages import Language
from bespoke.unit import Unit


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


# Inner helper class for structured LLM output
class UnitTagSchema(pydantic.BaseModel):
    occurance: str
    dictionary_entry: str


# Helper class for structured LLM output
class UnitTagsSchema(pydantic.BaseModel):
    occurance_vocabulary_map: list[UnitTagSchema]


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
    async def tag_sentence(
        self,
        sentence: str,
        language: Language,
        hint: list[str],
    ) -> list[tuple[str, str]]:
        """Tags words in a sentence with their dictionary form."""

    @abc.abstractmethod
    async def tag_sentence_disambiguated(
        self,
        sentence: str,
        language: Language,
        hints: str,
    ) -> list[tuple[str, str, int]]:
        """Tags sentence with disambiguation."""

    @abc.abstractmethod
    async def speak(
        self,
        sentence: str,
        *,
        slowly: bool = False,
    ) -> np.ndarray:
        """Converts text to speech."""


class GeminiLlmClient(LlmClient):
    TEXT_MODEL = "gemini-3.1-flash-lite-preview"
    SPEAK_MODEL = "gemini-2.5-flash-preview-tts"
    VOICES = [
        "Aoede",
        "Puck",
        "Charon",
        "Kore",
        "Fenrir",
        "Leda",
        "Orus",
        "Zephyr",
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
    async def tag_sentence(
        self,
        sentence: str,
        language: Language,
        hint: list[str],
    ) -> list[tuple[str, str]]:
        if hint:
            hint_prompt = (
                f" Some examples of dictionary words are: \n{' \n'.join(hint)} \n"
                "Use these words if appropriate, but ignore them if they are "
                "incorrect tags, even if they appear in the sentence."
            )
        else:
            hint_prompt = ""
        if language.phonetic_system is not None:
            phonetic_prompt = (
                f" Write the tags in {language.writing_system}, "
                f"not {language.phonetic_system}."
            )
        else:
            phonetic_prompt = ""
        prompt = (
            f"Given is a sentence in {language.writing_system}: \n{sentence} \n"
            "I want to tag words in each sentence with vocabulary. "
            "The tags are a map from the word as written, "
            f"to the vocabulary unit as in a dictionary. "
            "Add all missing occurances to the existing map and output it. "
            "For compound words, idioms or grammatical constructions, "
            "the dictionary may only contain individual parts. "
            "Add all alternative tags, both complex and in parts."
            f"{hint_prompt}{phonetic_prompt}"
        )

        response = await self._client.aio.models.generate_content(
            model=self.TEXT_MODEL,
            contents=[prompt],
            config=self._genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=UnitTagsSchema,
            ),
        )
        if response.parsed is None:
            raise ValueError("Missing content")
        parsed = typing.cast(UnitTagsSchema, response.parsed)
        return [
            (tag.occurance, tag.dictionary_entry)
            for tag in parsed.occurance_vocabulary_map
        ]

    @standard_retry
    async def tag_sentence_disambiguated(
        self,
        sentence: str,
        language: Language,
        hints: str,
    ) -> list[tuple[str, str, int]]:
        if language.phonetic_system is not None:
            phonetic_prompt = (
                f" Write the tags in {language.writing_system}, "
                f"not {language.phonetic_system}."
            )
        else:
            phonetic_prompt = ""

        prompt = (
            f"Given is a sentence in {language.writing_system}: \n{sentence} \n"
            "Segment it into non-overlapping consecutive words such that each word exists as a key in the provided dictionary hints. \n"
            "For each word, identify the correct `index` of the definition that matches its meaning in the context of the sentence. \n"
            "The concatenation of all `occurance` strings MUST NOT exceed the length of the original sentence, and there must be NO overlapping parts. \n"
            "Exclude punctuation unless it's part of the dictionary word itself. \n"
            f"Dictionary hints:\n{hints}\n"
            f"{phonetic_prompt}"
        )

        response = await self._client.aio.models.generate_content(
            model=self.TEXT_MODEL,
            contents=[prompt],
            config=self._genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DisambiguatedTagsSchema,
            ),
        )
        if response.parsed is None:
            raise ValueError("Missing content")
        parsed = typing.cast(DisambiguatedTagsSchema, response.parsed)
        return [(tag.occurance, tag.word, tag.index) for tag in parsed.tags]

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
    async def tag_sentence(
        self,
        sentence: str,
        language: Language,
        hint: list[str],
    ) -> list[tuple[str, str]]:
        if hint:
            hint_prompt = (
                f" Some examples of dictionary words are: \n{' \n'.join(hint)} \n"
                "Use these words if appropriate, but ignore them if they are "
                "incorrect tags, even if they appear in the sentence."
            )
        else:
            hint_prompt = ""
        if language.phonetic_system is not None:
            phonetic_prompt = (
                f" Write the tags in {language.writing_system}, "
                f"not {language.phonetic_system}."
            )
        else:
            phonetic_prompt = ""
        prompt = (
            f"Given is a sentence in {language.writing_system}: \n{sentence} \n"
            "I want to tag words in each sentence with vocabulary. "
            "The tags are a map from the word as written, "
            f"to the vocabulary unit as in a dictionary. "
            "Add all missing occurances to the existing map and output it. "
            "For compound words, idioms or grammatical constructions, "
            "the dictionary may only contain individual parts. "
            "Add all alternative tags, both complex and in parts."
            f"{hint_prompt}{phonetic_prompt}"
        )

        response = await self._litellm.acompletion(
            model=self.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format=UnitTagsSchema,
            api_key=self.openrouter_api_key,
        )
        content = response.choices[0].message.content
        parsed = UnitTagsSchema.model_validate_json(content)
        return [
            (tag.occurance, tag.dictionary_entry)
            for tag in parsed.occurance_vocabulary_map
        ]

    async def tag_sentence_disambiguated(
        self,
        sentence: str,
        language: Language,
        hints: str,
    ) -> list[tuple[str, str, int]]:
        if language.phonetic_system is not None:
            phonetic_prompt = (
                f" Write the tags in {language.writing_system}, "
                f"not {language.phonetic_system}."
            )
        else:
            phonetic_prompt = ""

        prompt = (
            f"Given is a sentence in {language.writing_system}: \n{sentence} \n"
            "Segment it into non-overlapping consecutive words such that each word exists as a key in the provided dictionary hints. \n"
            "For each word, identify the correct `index` of the definition that matches its meaning in the context of the sentence. \n"
            "The concatenation of all `occurance` strings MUST NOT exceed the length of the original sentence, and there must be NO overlapping parts. \n"
            "Exclude punctuation unless it's part of the dictionary word itself. \n"
            f"Dictionary hints:\n{hints}\n"
            f"{phonetic_prompt}"
        )

        import litellm

        response = await litellm.acompletion(
            model=self.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format=DisambiguatedTagsSchema,
            api_key=self.openrouter_api_key,
        )
        content = response.choices[0].message.content
        parsed = DisambiguatedTagsSchema.model_validate_json(content)
        return [(tag.occurance, tag.word, tag.index) for tag in parsed.tags]

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
    async def tag_sentence(
        self,
        sentence: str,
        language: Language,
        hint: list[str],
    ) -> list[tuple[str, str]]:
        if hint:
            hint_prompt = (
                f" Some examples of dictionary words are: \n{' \n'.join(hint)} \n"
                "Use these words if appropriate, but ignore them if they are "
                "incorrect tags, even if they appear in the sentence."
            )
        else:
            hint_prompt = ""
        if language.phonetic_system is not None:
            phonetic_prompt = (
                f" Write the tags in {language.writing_system}, "
                f"not {language.phonetic_system}."
            )
        else:
            phonetic_prompt = ""
        prompt = (
            f"Given is a sentence in {language.writing_system}: \n{sentence} \n"
            "I want to tag words in each sentence with vocabulary. "
            "The tags are a map from the word as written, "
            f"to the vocabulary unit as in a dictionary. "
            "Add all missing occurances to the existing map and output it. "
            "For compound words, idioms or grammatical constructions, "
            "the dictionary may only contain individual parts. "
            "Add all alternative tags, both complex and in parts."
            f"{hint_prompt}{phonetic_prompt}"
        )

        response = await self._litellm.acompletion(
            model=self.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format=UnitTagsSchema,
            api_key=self._api_key,
        )
        content = response.choices[0].message.content
        parsed = UnitTagsSchema.model_validate_json(content)
        return [
            (tag.occurance, tag.dictionary_entry)
            for tag in parsed.occurance_vocabulary_map
        ]

    async def tag_sentence_disambiguated(
        self,
        sentence: str,
        language: Language,
        hints: str,
    ) -> list[tuple[str, str, int]]:
        if language.phonetic_system is not None:
            phonetic_prompt = (
                f" Write the tags in {language.writing_system}, "
                f"not {language.phonetic_system}."
            )
        else:
            phonetic_prompt = ""

        prompt = (
            f"Given is a sentence in {language.writing_system}: \n{sentence} \n"
            "Segment it into non-overlapping consecutive words such that each word exists as a key in the provided dictionary hints. \n"
            "For each word, identify the correct `index` of the definition that matches its meaning in the context of the sentence. \n"
            "The concatenation of all `occurance` strings MUST NOT exceed the length of the original sentence, and there must be NO overlapping parts. \n"
            "Exclude punctuation unless it's part of the dictionary word itself. \n"
            f"Dictionary hints:\n{hints}\n"
            f"{phonetic_prompt}"
        )

        import litellm

        response = await litellm.acompletion(
            model=self.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format=DisambiguatedTagsSchema,
            api_key=self._api_key,
        )
        content = response.choices[0].message.content
        parsed = DisambiguatedTagsSchema.model_validate_json(content)
        return [(tag.occurance, tag.word, tag.index) for tag in parsed.tags]

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
