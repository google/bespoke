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

"""Tool to translate unit definitions to a native language."""

import argparse
import asyncio
import csv
import io
from pathlib import Path

import aiofiles  # type: ignore

from bespoke import languages, llm
from bespoke.translation import translate_units


async def main_async() -> None:
    parser = argparse.ArgumentParser(
        description="Translate units to generate dictionary entries."
    )
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
        help="The language of the units to be translated.",
    )
    parser.add_argument(
        "--native",
        type=str,
        choices=list(native_choices),
        required=True,
        help="The native language to translate into.",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output path. Defaults to cards/translations_{target}_{native}.csv",
    )
    parser.add_argument(
        "--parallelism",
        type=int,
        default=16,
        help="Parallelism limit for LLM calls (default: 16).",
    )
    args = parser.parse_args()

    target_language = target_choices[args.target]
    native_language = native_choices[args.native]

    if not args.output:
        args.output = (
            f"cards/translations_{target_language.code_name}_"
            f"{native_language.code_name}.csv"
        )

    units = target_language.units()
    print(f"Found {len(units)} units in {target_language.writing_system}.")

    existing_results: dict[str, str] = {}
    output_path = Path(args.output)
    if output_path.exists():
        print(f"Loading existing translations from {output_path}...")
        try:
            async with aiofiles.open(output_path, "r", encoding="utf-8") as f:
                content = await f.read()
                reader = csv.DictReader(content.splitlines())
                for row in reader:
                    uid = row.get("unit_id")
                    trans = row.get("translation", "")
                    if uid:
                        existing_results[uid] = trans
            existing_count = sum(1 for t in existing_results.values() if t.strip())
            print(
                f"Loaded {len(existing_results)} entries, {existing_count} already translated."
            )
        except (OSError, csv.Error) as e:
            print(f"Warning: Failed to read existing translations: {e}")

    units_to_translate = [
        u for u in units if not existing_results.get(u.id(), "").strip()
    ]
    print(f"Need to translate {len(units_to_translate)} units.")

    llm_client = llm.get_llm_client()
    results = dict(existing_results)

    try:
        results = await translate_units(
            units=units,
            target_language=target_language,
            native_language=native_language,
            llm_client=llm_client,
            existing_translations=existing_results,
            parallelism=args.parallelism,
        )

    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\nTranslation run was interrupted/cancelled. Saving progress...")
    finally:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["unit_id", "translation"])
        for unit in units:
            writer.writerow([unit.id(), results.get(unit.id(), "")])

        async with aiofiles.open(output_path, "w", encoding="utf-8", newline="") as f:
            await f.write(buffer.getvalue())

        success_count = sum(1 for u in units if results.get(u.id(), "").strip())
        print(
            f"Progress saved to {output_path}. Total translated: "
            f"{success_count}/{len(units)}"
        )


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
