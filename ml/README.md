# Machine Learning

Data-processing pipelines, training utilities, inference code, and model evaluation live here. Local datasets, checkpoints, and generated model artifacts are excluded from Git.

`voice/local_adapters.py` contains optional, lazy local adapters for Silero VAD, Faster Whisper, and piper-plus. They use transient in-memory audio, require local model availability, return structured safe failure codes, and do not download models or persist recordings. The deterministic text simulation remains usable when an adapter, model, microphone, or platform capability is unavailable.
