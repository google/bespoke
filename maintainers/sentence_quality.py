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

"""Script to evaluate sentence generation quality."""

import argparse
import asyncio
import os
import types

from bespoke import Card
from bespoke import Difficulty
from bespoke import Language
from bespoke import builder
from bespoke import languages
from bespoke import llm

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
ELEVENLABS_KEY = os.environ.get("ELEVENLABS_API_KEY")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
if GEMINI_KEY is None:
    raise ValueError("GEMINI_API_KEY is not set")
if OPENROUTER_KEY is None:
    raise ValueError("OPENROUTER_API_KEY is not set")
if ELEVENLABS_KEY is None:
    raise ValueError("ELEVENLABS_API_KEY is not set")
if OPENAI_KEY is None:
    raise ValueError("OPENAI_API_KEY is not set")

LLM_CLIENTS = {
    "gemini": llm.GeminiLlmClient(GEMINI_KEY),
    "router": llm.OpenRouterElevenLabsLlmClient(OPENROUTER_KEY, ELEVENLABS_KEY),
    "openai": llm.OpenAiLlmClient(OPENAI_KEY),
}


async def produce(name: str, producer: builder.SentenceProducer) -> None:
    with open(f"output_{name}.txt", "a") as f:
        while not producer.done():
            builders, _ = await producer.create()
            for builder in builders:
                f.write(f"{builder.sentence}\n")
            fake_card = Card(
                id="",
                sentence="",
                native_sentence="",
                audio_filename="",
                slow_audio_filename="",
                native_audio_filename="",
                phonetic="",
                units=builders[0].hint,
                unit_tags={},
                notes=[],
            )
            producer.register_card(fake_card)


def isolate_difficulty(obj: Language, difficulty: Difficulty) -> Language:
    original_vocabulary = Language.vocabulary

    def patched_vocabulary(self, d: Difficulty) -> list[str]:
        if d == difficulty:
            return original_vocabulary(self, difficulty)
        return []

    def patched_full_vocabulary(self) -> list[str]:
        return self.vocabulary(difficulty)

    object.__setattr__(obj, "vocabulary", types.MethodType(patched_vocabulary, obj))
    object.__setattr__(
        obj, "full_vocabulary", types.MethodType(patched_full_vocabulary, obj)
    )
    return obj


async def start_experiment(
    language: Language, difficulty: Difficulty | None, cards_per_call: int
) -> None:
    if difficulty is not None:
        language = isolate_difficulty(language, difficulty)
    grammar = languages.load_grammar(language.code_name)
    async with asyncio.TaskGroup() as tg:
        for name, llm_client in LLM_CLIENTS.items():
            if difficulty is not None:
                name = f"{difficulty}_{name}"
            producer = builder.SentenceProducer(
                language,
                llm_client,
                grammar,
                cards_per_unit=1,
                cards_per_call=cards_per_call,
            )

            tg.create_task(produce(name, producer))


def main():
    parser = argparse.ArgumentParser(description="Sentence quality test.")
    target_choices = {}
    for code_name in languages.LANGUAGE_DATA:
        language = languages.LANGUAGES[code_name]
        target_choices[language.writing_system] = language
    difficulties = [str(d) for d in Difficulty]
    parser.add_argument(
        "--target",
        type=str,
        choices=list(target_choices),
        required=True,
        help="The language you are learning.",
    )
    parser.add_argument(
        "--difficulty",
        type=str,
        choices=list(difficulties),
        help="The level of cards you want to generate.",
    )
    parser.add_argument(
        "--cards_per_call", type=int, default=8, help="Number of cards per API call."
    )
    args = parser.parse_args()

    target = target_choices[args.target]
    if args.difficulty is None:
        difficulty = None
    else:
        difficulty = Difficulty(args.difficulty)
    asyncio.run(start_experiment(target, difficulty, args.cards_per_call))


if __name__ == "__main__":
    main()
