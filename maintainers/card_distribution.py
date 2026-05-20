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
from bespoke import Language
from bespoke import languages


def find_missing_units(card_index: CardIndex, language: Language) -> None:
    total = 0
    max_size = 0
    max_unit = None
    print("Units that don't appear in cards:")
    count = 0
    for unit in language.units():
        size = card_index.size(unit)
        total += size
        if not size:
            print(unit)
            count += 1
        if size > max_size:
            max_size = size
            max_unit = unit
    print(f"In total, {count} units are untagged on all cards.")
    print(f"Average number of cards per unit: {total / len(language.units())}")
    print(f"Highest number of cards is {max_size} for {max_unit}")


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
    args = parser.parse_args()

    target = target_choices[args.target]
    native = native_choices[args.native]
    card_index = CardIndex.load(target, native)
    asyncio.run(card_index.check())
    find_missing_units(card_index, target)


if __name__ == "__main__":
    main()
