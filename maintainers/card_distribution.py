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

from bespoke import Card
from bespoke import CardIndex
from bespoke import Difficulty
from bespoke import Language
from bespoke import Unit
from bespoke import languages
from bespoke import Deck
from bespoke.unit import DictionaryUnit


def find_missing_units(
    card_index: CardIndex,
    language: Language,
    max_difficulty: Difficulty = Difficulty.C2,
) -> None:
    total = 0
    max_size = 0
    max_unit = None
    untagged_units = []
    checked_units = [u for u in language.units() if u.difficulty() <= max_difficulty]
    if not checked_units:
        print("No units found.")
        return
    for unit in checked_units:
        size = card_index.size(unit)
        total += size
        if not size:
            untagged_units.append(unit)
        if size > max_size:
            max_size = size
            max_unit = unit

    print("Units that don't appear in cards:")
    if len(untagged_units) > 100:
        filename = "untagged.txt"
        with open(filename, "w", encoding="utf-8") as f:
            for u in untagged_units:
                f.write(f"{u}\n")
        print(f"More than 100 untagged units. Full list written to {filename}")
        print("Sample of 10 untagged units:")
        for u in untagged_units[:10]:
            print(u)
    else:
        for u in untagged_units:
            print(u)

    print(f"In total, {len(untagged_units)} units are untagged on all cards.")
    print(f"Average number of cards per unit: {total / len(checked_units)}")
    print(f"Highest number of cards is {max_size} for {max_unit}")


async def analyze_card_difficulty(
    card_index: CardIndex,
    language: Language,
) -> None:
    print("\nAnalyzing card difficulty distribution:")
    cards = await card_index.all_cards()

    units = language.units()
    unit_map = {u.id(): u for u in units}
    units_by_difficulty: dict[Difficulty, list[Unit]] = {d: [] for d in Difficulty}
    for u in units:
        units_by_difficulty[u.difficulty()].append(u)
    difficulty_order = {d: i for i, d in enumerate(Difficulty)}

    # Compute difficulty for each card
    cards_by_difficulty: dict[Difficulty, list[Card]] = {d: [] for d in Difficulty}
    for card in cards:
        card_unit_diffs = []
        for tag in card.unit_tags:
            unit = unit_map.get(tag.unit_id)
            if unit:
                card_unit_diffs.append(unit.difficulty())
        if card_unit_diffs:
            max_diff = max(card_unit_diffs, key=lambda d: difficulty_order[d])
            cards_by_difficulty[max_diff].append(card)

    # Analyze unit and card match in difficulty
    for d in Difficulty:
        difficulty_units = units_by_difficulty[d]
        difficulty_cards = cards_by_difficulty[d]
        unit_card_counts = {u.id(): 0 for u in difficulty_units}
        for card in difficulty_cards:
            for tag in card.unit_tags:
                if tag.unit_id in unit_card_counts:
                    unit_card_counts[tag.unit_id] += 1
        num_units = len(difficulty_units)
        num_cards = len(difficulty_cards)

        if num_units == 0:
            print(f"Difficulty {d.value}: 0 cards, 0 units.")
            continue

        units_with_card = sum(1 for count in unit_card_counts.values() if count > 0)
        total_correct_cards = sum(unit_card_counts.values())
        avg_cards = total_correct_cards / num_units

        print(f"Difficulty {d.value}:")
        print(f"  Units of this difficulty: {num_units}")
        print(f"  Cards of this difficulty: {num_cards}")
        print(
            f"  Units with at least one card of this difficulty: {units_with_card} ({units_with_card / num_units * 100:.2f}%)"
        )
        print(f"  Average cards of correct difficulty per unit: {avg_cards:.2f}")


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
    await analyze_card_difficulty(card_index, target)

    print("\nChecking translations:")
    deck = Deck(target, native, card_index)
    translations_present = False
    missing_count = 0
    for unit in target.units():
        translation = deck.translated_unit(unit.id())
        is_missing = False
        if isinstance(unit, DictionaryUnit) and unit.definition():
            if translation == unit.definition():
                is_missing = True
        elif not translation:
            is_missing = True

        if is_missing:
            missing_count += 1
        else:
            translations_present = True

    if not translations_present:
        print("Translations do not exist.")
    elif missing_count > 0:
        print(f"Missing translations: {missing_count}")
    else:
        print("All translations are present.")


def main():
    parser = argparse.ArgumentParser(description="Card statistics script.")
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
