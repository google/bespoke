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

"""Script to check sentence generation quality and tagging."""

import argparse
import asyncio
import random

from bespoke import Difficulty
from bespoke import Language
from bespoke import builder
from bespoke import languages
from bespoke import llm
from bespoke import tagger


async def main_async():
    parser = argparse.ArgumentParser(
        description="Check sentence quality and tagging."
    )
    target_choices = {}
    for language in languages.LANGUAGES.values():
        if language.has_data():
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
        required=True,
        help="Difficulty level of used vocabulary.",
    )
    parser.add_argument(
        "--cards_per_call",
        type=int,
        default=8,
        help="Number of cards per call",
    )
    args = parser.parse_args()

    difficulty = Difficulty(args.difficulty)
    real_language = target_choices[args.target]
    grammar = languages.load_grammar(real_language.code_name)

    all_units = real_language.units()
    filtered_units = [u for u in all_units if u.difficulty() == difficulty]
    if len(filtered_units) < args.cards_per_call:
        print(f"Found only {len(filtered_units)} units.")
        return
    sampled_units = random.sample(filtered_units, args.cards_per_call)

    small_language = Language(
        name=real_language.name,
        writing_system=real_language.writing_system,
        phonetic_system=real_language.phonetic_system,
        code_name=real_language.code_name,
    )
    small_language._units = sampled_units
    small_language._units_by_id = {u.id(): u for u in sampled_units}
    small_language._units_by_name = {}
    for u in sampled_units:
        small_language._units_by_name.setdefault(u.name(), []).append(u)
    small_language._initialized = True

    llm_client = llm.get_llm_client()
    producer = builder.SentenceProducer(
        small_language,
        llm_client,
        grammar,
        cards_per_unit=1,
        cards_per_call=args.cards_per_call,
    )
    print(f"Selected units: {[u.name() for u in sampled_units]}")
    sentences, units, grammar_used = await producer.create()
    print(f"Grammar used: {grammar_used}")
    print("--------------------------------------")

    for sentence in sentences:
        print(f"Sentence: {sentence}")
        unit_tags = await tagger.create_tags(
            sentence=sentence,
            hint=units,
            language=real_language,
            llm_client=llm_client,
        )
        print("Tags:")
        for tag in unit_tags:
            print(f"  {tag.occurance} -> {tag.unit_id}")
        print("--------------------------------------")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
