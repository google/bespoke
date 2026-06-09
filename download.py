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

"""Script to download generated datasets from Kaggle."""

import argparse
import shutil
import sys
from pathlib import Path

import kagglehub  # type: ignore
from kagglehub.exceptions import KaggleApiHTTPError  # type: ignore

from bespoke import languages


def main():
    parser = argparse.ArgumentParser(description="Download card datasets from Kaggle.")
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

    target_name = target.code_name.replace("_", "")
    native_name = native.code_name.replace("_", "")

    if native_name == "german" and target_name == "simpchinese":
        # Temporary exception for misnamed Simplified Chinese dataset.
        dataset = "bespoke-cards-simpchinese-german"
    else:
        dataset = f"bespoke-cards-{native_name}-{target_name}"

    dataset_slug = f"google/{dataset}"

    print(f"Downloading dataset {dataset_slug} from Kaggle...")
    try:
        downloaded_path = kagglehub.dataset_download(dataset_slug)
    except KaggleApiHTTPError as e:
        if e.response is not None and e.response.status_code in (403, 404):
            print(
                f"Error: The dataset '{dataset_slug}' does not exist on Kaggle.",
            )
            sys.exit(1)
        raise

    downloaded_dir = Path(downloaded_path)
    cards_dir = Path("cards")
    cards_dir.mkdir(parents=True, exist_ok=True)

    for item in downloaded_dir.iterdir():
        dest = cards_dir / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)


if __name__ == "__main__":
    main()
