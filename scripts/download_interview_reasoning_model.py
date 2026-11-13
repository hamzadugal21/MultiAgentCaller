"""Explicitly download the pinned local model for bounded interview reasoning."""

import sys
from pathlib import Path

from huggingface_hub import snapshot_download

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    from ai_system.interview.reasoning_agent import (
        DEFAULT_MODEL_PATH,
        MODEL_ID,
        MODEL_REVISION,
    )

    snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=str(DEFAULT_MODEL_PATH),
        allow_patterns=[
            "*.json",
            "model.onnx",
            "model.onnx.data",
            "merges.txt",
            "vocab.json",
            "LICENSE*",
        ],
    )
    print("Local interview reasoning model download completed.")


if __name__ == "__main__":
    main()
