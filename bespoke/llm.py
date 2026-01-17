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
import numpy as np
import os
import pydantic
import random
import tenacity

from bespoke.languages import Difficulty
from bespoke.languages import Language
from bespoke.languages import UnitTags
from bespoke.languages import DIFFICULTY_EXPLANATIONS

SPEAK_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
TEXT_MODEL = "gemini-2.0-flash"
VOICES = ["Aoede", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Zephyr"]

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

standard_retry = tenacity.retry(
  stop=tenacity.stop_after_attempt(3),
  wait=tenacity.wait_random_exponential(multiplier=4, min=5, max=300),
)


async def translate(sentence: str, target_language: Language) -> str:
  prompt = (
    "Translate the following sentence to "
    f"{target_language.writing_system}: \n{sentence} \n"
    "Only respond with the translation, no introduction or explanations."
  )
  config = types.GenerateContentConfig(
    response_modalities=["TEXT"],
    thinking_config=types.ThinkingConfig(thinking_budget=0),
  )
  response = await client.aio.models.generate_content(
    model=TEXT_MODEL,
    contents=[prompt],
    config=config,
  )
  return response.text.strip()


async def to_phonetic(sentence: str, language: Language) -> str | None:
  if not language.phonetic_system:
    return None
  prompt = (
    "Take the following sentence and convert it to "
    f"{language.phonetic_system}. "
    "Don't add any introduction or explanations, just the pure response. "
    f"The sentence is: \n{sentence}"
  )
  response = await client.aio.models.generate_content(
    model=TEXT_MODEL,
    contents=[prompt],
    config=types.GenerateContentConfig(
      response_modalities=["TEXT"],
      thinking_config=types.ThinkingConfig(thinking_budget=0),
    ),
  )
  return response.text.strip()


@standard_retry
async def create_sentences(
  language: Language,
  difficulty: Difficulty,
  grammar: str,
  units: list[str],
) -> list[str]:
  difficulty_explanation = DIFFICULTY_EXPLANATIONS[difficulty]
  prompt = (
    f"Create example sentences in the language {language.writing_system}. "
    f"The output should be exactly {len(units)} lines. "
    "Each line will be interpreted as a sentence. "
    "Don't add numbering. Don't mark words with spaces or ** etc. "
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
  config = types.GenerateContentConfig(
    response_modalities=["TEXT"],
    temperature=2.0,
    thinking_config=types.ThinkingConfig(thinking_budget=0),
  )
  response = await client.aio.models.generate_content(
    model=TEXT_MODEL,
    contents=[prompt],
    config=config,
  )
  sentences = [s.strip() for s in response.text.strip().split("\n")]
  return [s for s in sentences if s]


# This workarond is unfortunately necessary, see:
# https://github.com/googleapis/python-genai/issues/460
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
  unit_tags: UnitTags,
) -> list[str, str]:
  tags = " \n".join(f"{w}: {u}" for w, u in unit_tags.items())
  if tags:
    tags_prompt = f"Tags annotated so far are: \n{tags} \n"
  else:
    tags_prompt = ""
  prompt = (
    f"Given is a sentence in {language.writing_system}: \n{sentence} \n"
    "I want to tag words in each sentence with vocabulary. "
    "The tags are a map from the word as written, "
    f"to the vocabulary unit as in a dictionary. {tags_prompt}"
    "Add all missing occurances to the existing map and output it. "
    "For compound words, idioms or grammatical constructions, "
    "the dictionary may only contain individual parts. "
    "Add all alternative tags, both complex and in parts."
  )
  if language.phonetic_system is not None:
    prompt += (
      f" Write the tags in {language.writing_system}, not {language.writing_system}."
    )
  config = types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema=UnitTagsSchema,
    temperature=2.0,
    thinking_config=types.ThinkingConfig(thinking_budget=0),
  )
  response = await client.aio.models.generate_content(
    model=TEXT_MODEL,
    contents=[prompt],
    config=config,
  )
  # Return value allows duplicates, therefore not dictionary.
  return [
    (tag.occurance, tag.dictionary_entry)
    for tag in response.parsed.occurance_vocabulary_map
  ]


async def speak(
  sentence: str,
  language: Language,
  *,
  slowly: bool = False,
) -> np.ndarray:
  voice_name = random.choice(VOICES)
  voice_config = types.VoiceConfig(
    prebuilt_voice_config=types.PrebuiltVoiceConfig(
      voice_name=voice_name,
    )
  )
  if language.live_code == "cmn-CN":
    # The new model rejects the Chinese code, but the prompting is good enough.
    speech_config = types.SpeechConfig(
      voice_config=voice_config,
    )
  else:
    speech_config = types.SpeechConfig(
      voice_config=voice_config,
      language_code=language.live_code,
    )
  config = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    speech_config=speech_config,
  )
  async with client.aio.live.connect(
    model=SPEAK_MODEL,
    config=config,
  ) as session:
    if slowly:
      text_input = f"Speak slowly in {language.name}: \n{sentence}"
    else:
      text_input = (
        "You are a voice actor, and your output will be used directly. "
        f"Speak the following sentence in {language.name}: \n{sentence}"
      )
    await session.send_client_content(
      turns=types.Content(role="user", parts=[types.Part(text=text_input)])
    )

    audio_data = []
    async for message in session.receive():
      if message.server_content.model_turn and message.server_content.model_turn.parts:
        for part in message.server_content.model_turn.parts:
          if part.inline_data:
            audio_data.append(np.frombuffer(part.inline_data.data, dtype=np.int16))
    if not audio_data:
      return np.array([], dtype=np.int16)
    return np.concatenate(audio_data)
