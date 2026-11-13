"""Explicitly download the local multilingual Faster-Whisper base model."""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("var/models/whisper/base"),
    )
    args = parser.parse_args()
    from huggingface_hub import snapshot_download

    args.model_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id="Systran/faster-whisper-base",
        local_dir=str(args.model_dir),
    )
    print("Local Faster-Whisper base model download completed.")


if __name__ == "__main__":
    main()
