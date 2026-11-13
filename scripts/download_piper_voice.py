"""Explicitly download the reviewed local Piper Plus English-capable voice."""

import argparse
from pathlib import Path

from huggingface_hub import hf_hub_download

# This is a native Piper Plus model with a multilingual phoneme configuration,
# unlike legacy Piper voices that use the unsupported ``espeak`` phoneme type.
# The corpus-derived license has additional voice-use conditions; review its
# bundled NOTICE.md before redistribution or deployment.
REPOSITORY_ID = "ayousanz/piper-plus-tsukuyomi-chan"
REVISION = "93c1fb6d67c29accc9ddf52326bb4582b1b52a3d"
VOICE_ROOT = "releases/zs-v1/tsukuyomi.onnx"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("var/models/piper/tsukuyomi-zs-v1"),
    )
    args = parser.parse_args()
    args.model_dir.mkdir(parents=True, exist_ok=True)
    for filename in (VOICE_ROOT, f"{VOICE_ROOT}.json"):
        hf_hub_download(
            repo_id=REPOSITORY_ID,
            revision=REVISION,
            filename=filename,
            local_dir=args.model_dir,
        )
    hf_hub_download(
        repo_id=REPOSITORY_ID,
        revision=REVISION,
        filename="releases/zs-v1/NOTICE.md",
        local_dir=args.model_dir,
    )
    print("Local Piper Plus voice download completed; review the bundled NOTICE.md.")


if __name__ == "__main__":
    main()
