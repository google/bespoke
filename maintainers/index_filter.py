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

"""Script to filter sentences out of the card index."""

import argparse
import asyncio

from bespoke import CardIndex
from bespoke import Language
from bespoke import languages


async def filter_index(target: Language, native: Language, input_file: str) -> None:
    with open(input_file, "r", encoding="utf-8") as f:
        sentences_to_filter = {line.strip() for line in f if line.strip()}

    card_index = CardIndex.load(target, native)
    all_cards = await card_index.all_cards()
    cards_to_remove = [
        card for card in all_cards if card.sentence in sentences_to_filter
    ]
    print(f"Found {len(cards_to_remove)} cards to filter.")

    for card in cards_to_remove:
        await card_index.remove(card.id)
    card_index.save()
    print("Filtered cards successfully removed and index saved.")


def main():
    parser = argparse.ArgumentParser(description="Filter cards by sentence.")

    target_choices = {}
    for language in languages.LANGUAGES.values():
        if language.has_data():
            target_choices[language.writing_system] = language
    native_choices = {
        lang.writing_system: lang for lang in languages.LANGUAGES.values()
    }

    parser.add_argument(
        "--target",
        type=str,
        choices=list(target_choices),
        required=True,
        help="The language you are learning.",
    )
    parser.add_argument(
        "--native",
        type=str,
        choices=list(native_choices),
        required=True,
        help="A language that you know.",
    )
    parser.add_argument(
        "--sentences",
        type=str,
        required=True,
        help="Path to the txt file containing sentences to filter.",
    )

    args = parser.parse_args()

    target = target_choices[args.target]
    native = native_choices[args.native]

    asyncio.run(filter_index(target, native, args.sentences))


if __name__ == "__main__":
    main()
