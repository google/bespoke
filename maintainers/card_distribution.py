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

"""Script to check cards per unit."""

import argparse
import asyncio

from bespoke import CardIndex
from bespoke import Difficulty
from bespoke import Language
from bespoke import languages


def find_missing_units(
    card_index: CardIndex,
    language: Language,
    max_difficulty: Difficulty = Difficulty.C2,
) -> None:
    total = 0
    max_size = 0
    max_unit = None
    count = 0
    checked_units = [u for u in language.units() if u.difficulty() <= max_difficulty]
    if not checked_units:
        print("No units found.")
        return
    print("Units that don't appear in cards:")
    for unit in checked_units:
        size = card_index.size(unit)
        total += size
        if not size:
            print(unit)
            count += 1
        if size > max_size:
            max_size = size
            max_unit = unit
    print(f"In total, {count} units are untagged on all cards.")
    print(f"Average number of cards per unit: {total / len(checked_units)}")
    print(f"Highest number of cards is {max_size} for {max_unit}")


async def check_distribution(
    target: Language,
    native: Language,
    max_difficulty: Difficulty = Difficulty.C2,
    rebuild_index: bool = False,
) -> None:
    card_index = CardIndex.load(target, native)
    if rebuild_index:
        await card_index.restart()
    await card_index.check()
    find_missing_units(card_index, target, max_difficulty)


def main():
    parser = argparse.ArgumentParser(description="Test script.")
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
        "--max_difficulty",
        type=str,
        choices=[d.value for d in Difficulty],
        default="C2",
        help="Maximum difficulty for units to check.",
    )
    parser.add_argument(
        "--rebuild_index",
        action="store_true",
        help="Rebuild the card index from the card files on disk.",
    )
    args = parser.parse_args()

    target = target_choices[args.target]
    native = native_choices[args.native]
    max_diff = Difficulty(args.max_difficulty)
    asyncio.run(check_distribution(target, native, max_diff, args.rebuild_index))


if __name__ == "__main__":
    main()
