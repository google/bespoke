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

"""Main file to create cards."""

import argparse
import asyncio
import os

from bespoke import CardIndex
from bespoke import DeckBuilder
from bespoke import languages


async def create(
    target: languages.Language,
    native: languages.Language,
    cards_per_unit: int,
    cards_per_call: int,
) -> None:
  deck_builder = DeckBuilder(target, native)
  await deck_builder.create_cards(
      cards_per_unit=cards_per_unit,
      cards_per_call=cards_per_call,
  )
  card_index = CardIndex.load(target, native)
  await card_index.check()


def main():
  parser = argparse.ArgumentParser(description="Create language cards.")
  target_choices = {l.writing_system: l for l in languages.SUPPORTED_LANGUAGES}
  native_choices = {l.writing_system: l for l in languages.LANGUAGES.values()}
  parser.add_argument(
      "--target", 
      type=str, 
      choices=list(target_choices),
      help="The language you are learning."
  )
  parser.add_argument(
      "--native", 
      type=str, 
      choices=list(native_choices),
      help="A language that you know."
  )
  parser.add_argument(
      "--cards_per_unit", 
      type=int, 
      default=16, 
      help="Number of cards in a single unit."
  )
  parser.add_argument(
      "--cards_per_call", 
      type=int, 
      default=8, 
      help="Number of cards per API call."
  )
  args = parser.parse_args()

  target = target_choices[args.target]
  native = native_choices[args.native]
  asyncio.run(create(target, native, args.cards_per_unit, args.cards_per_call))


if __name__ == "__main__":
    main()
