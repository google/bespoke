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

from google import genai
from google.genai import types
import httpx
import litellm
import numpy as np
import os
import pydantic
import random
import tenacity

from bespoke.languages import Difficulty
from bespoke.languages import Language

litellm.suppress_debug_info = True

GEMINI_TEXT_MODEL = "gemini/gemini-2.5-flash-lite"
GEMINI_SPEAK_MODEL = "gemini-2.5-flash-preview-tts"
GEMINI_VOICES = ["Aoede", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Zephyr"]

OPENROUTER_TEXT_MODEL = "openrouter/google/gemma-2-9b-it"

OPENAI_TEXT_MODEL = "gpt-4o-mini"
OPENAI_SPEAK_MODEL = "tts-1"
OPENAI_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

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

DIFFICULTY_EXPLANATIONS = {
    Difficulty.A1: "Beginner, understands and uses simple phrases and sentences.",
    Difficulty.A2: "Basic knowledge of frequently used expressions in areas of immediate relevance.",
    Difficulty.B1: "Intermediate, understands main points of clear standard language.",
    Difficulty.B2: "Independent, can interact with native speakers without strain.",
    Difficulty.C1: "Proficient, can understand demanding, longer clauses and recognise implicit meaning.",
    Difficulty.C2: "Near native, understands virtually everything heard or read with ease.",
}

standard_retry = tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_random_exponential(multiplier=4, min=5, max=300),
)


def _get_provider_config() -> dict:
    """Returns provider configuration based on environment variables."""
    if os.environ.get("GEMINI_API_KEY"):
        return {
            "provider": "gemini",
            "text_model": GEMINI_TEXT_MODEL,
        }
    elif os.environ.get("OPENROUTER_API_KEY"):
        return {
            "provider": "openrouter",
            "text_model": OPENROUTER_TEXT_MODEL,
        }
    elif os.environ.get("OPENAI_API_KEY"):
        return {
            "provider": "openai",
            "text_model": OPENAI_TEXT_MODEL,
        }
    else:
        raise ValueError(
            "No API key found. Please set GEMINI_API_KEY, OPENROUTER_API_KEY or OPENAI_API_KEY."
        )


@standard_retry
async def translate(sentence: str, target_language: Language) -> str:
    config = _get_provider_config()
    prompt = (
        "Translate the following sentence to "
        f"{target_language.writing_system}: \n{sentence} \n"
        "Only respond with the translation, no introduction or explanations."
    )

    response = await litellm.acompletion(
        model=config["text_model"],
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


@standard_retry
async def to_phonetic(sentence: str, language: Language) -> str | None:
    if not language.phonetic_system:
        return None

    config = _get_provider_config()
    prompt = (
        "Take the following sentence and convert it to "
        f"{language.phonetic_system}. "
        "Don't add any introduction or explanations, just the pure response. "
        f"The sentence is: \n{sentence}"
    )

    response = await litellm.acompletion(
        model=config["text_model"],
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


@standard_retry
async def create_sentences(
    language: Language,
    difficulty: Difficulty,
    grammar: str,
    units: list[str],
) -> list[str]:
    config = _get_provider_config()
    difficulty_explanation = DIFFICULTY_EXPLANATIONS[difficulty]
    if language.name in ["Chinese", "Japanese"]:
        spaces = "spaces or "
    else:
        spaces = ""
    prompt = (
        f"Create example sentences in the language {language.writing_system}. "
        f"The output should be exactly {len(units)} lines. "
        "Each line will be interpreted as a sentence. "
        f"Don't add numbering. Don't mark words with {spaces}** etc. "
        "Only respond with the sentences, no introduction or explanations. "
        "The sentences should represent how native speakers naturally talk. \n"
        f"All sentences together should use the following words: \n{units} \n"
        "All words should occur. "
        "If the word is part of a longer compound word, don't use the compound. "
        "Make the sentences unique and different. "
        f"All sentences should use this grammar concept: \n{grammar} \n"
        f"The target difficulty of the sentence is {difficulty}. "
        f"This difficulty level is defined as: \n{difficulty_explanation}"
    )

    if config["provider"] == "openrouter":
        temperature = 1.0
    else:
        temperature = 2.0
    response = await litellm.acompletion(
        model=config["text_model"],
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    sentences = [
        s.strip() for s in response.choices[0].message.content.strip().split("\n")
    ]
    return [s for s in sentences if s]


# Inner helper class for structured LLM output
class UnitTagSchema(pydantic.BaseModel):
    occurance: str
    dictionary_entry: str


# Helper class for structured LLM output
class UnitTagsSchema(pydantic.BaseModel):
    occurance_vocabulary_map: list[UnitTagSchema]


@standard_retry
async def tag_sentence(
    sentence: str,
    language: Language,
    hint: list[str],
) -> list[tuple[str, str]]:
    config = _get_provider_config()
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

    if config["provider"] == "openrouter":
        temperature = 1.0
    else:
        temperature = 2.0
    response = await litellm.acompletion(
        model=config["text_model"],
        messages=[{"role": "user", "content": prompt}],
        response_format=UnitTagsSchema,
        temperature=temperature,
    )
    content = response.choices[0].message.content
    parsed = UnitTagsSchema.model_validate_json(content)
    return [
        (tag.occurance, tag.dictionary_entry) for tag in parsed.occurance_vocabulary_map
    ]


@standard_retry
async def speak(
    sentence: str,
    *,
    slowly: bool = False,
) -> np.ndarray:
    config = _get_provider_config()

    if config["provider"] == "gemini":
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        voice_name = random.choice(GEMINI_VOICES)
        if slowly:
            instruction = "Speak slowly: "
        else:
            instruction = "Speak like a voice actor: "
        text = f"{instruction}{sentence}"
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=text),
                    ],
                ),
            ],
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_name,
                        )
                    )
                ),
            ),
        )
        audio_data = []
        if response.candidates[0] is None:
            raise ValueError("Missing content")
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                audio_data.append(np.frombuffer(part.inline_data.data, dtype=np.int16))
        if not audio_data:
            raise ValueError("Empty response")
        return np.concatenate(audio_data)

    elif config["provider"] in ["openrouter", "openai"]:
        if api_key := os.environ.get("ELEVENLABS_API_KEY"):
            voice_id = random.choice(ELEVENLABS_VOICES)
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=pcm_16000"
            headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
            data = {"text": sentence, "model_id": ELEVENLABS_MODEL}
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                return np.frombuffer(response.content, dtype=np.int16)

        if api_key := os.environ.get("OPENAI_API_KEY"):
            voice_name = random.choice(OPENAI_VOICES)
            response = await litellm.aspeech(
                model=OPENAI_SPEAK_MODEL,
                voice=voice_name,
                input=sentence,
                api_key=api_key,
            )
            return np.frombuffer(response.content, dtype=np.int16)

        print("No audio provider available")
        return np.array([], dtype=np.int16)

    print("No provider found")
    return np.array([], dtype=np.int16)
