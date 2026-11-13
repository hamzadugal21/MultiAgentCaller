# Machine Learning

Data-processing pipelines, training utilities, inference code, and model evaluation live here. Local datasets, checkpoints, and generated model artifacts are excluded from Git.

`voice/local_adapters.py` contains optional, lazy local adapters for Silero VAD, Faster Whisper, and piper-plus. They use transient in-memory audio, require local model availability, return structured safe failure codes, and do not download models or persist recordings. The deterministic text simulation remains usable when an adapter, model, microphone, or platform capability is unavailable.

Explicit setup scripts download the reviewed local Faster-Whisper base model and
the native Piper Plus English-capable voice into ignored `var/models/` paths.
Piper Plus voice artifacts can carry corpus-derived use conditions; read the
downloaded `NOTICE.md` before redistribution or deployment. Neither adapter
downloads a model while the Django server handles a request.
