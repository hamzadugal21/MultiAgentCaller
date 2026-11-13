# Final Release Readiness

Last updated: 2026-11-05 (Asia/Karachi)

## Status: PARTIAL

The smallest safe release implementation is present, but the corrected
three-turn Qwen-to-Django path has not completed a state-changing run. The
active sidebar process lost its private QA variables after a restart, so all QA
database writes are stopped until `scripts/verify_qa_database.py` succeeds
again. Real candidate-facing model actions remain disabled.

## 2026-11-06 stateless release verification

- The active process still has no private QA settings variables, so the
  database verifier and all state-changing QA work remain blocked fail-closed.
- A fresh sequential, database-free preflight passed using the ignored local
  Q3_K_S Qwen model: transient Piper/Silero/Faster-Whisper completed **3/3**
  synthetic turns with **3** VAD segments, then the released-memory Qwen worker
  produced an Interview `continue` proposal from one authorized MiniLM source.
  Observed Qwen load was **1,421 ms** and generation **3,125 ms**.
- `pip check`, project-wide Ruff, and `git diff --check` passed. The earlier
  47 focused AI/RAG/agent tests were not needlessly repeated. This evidence is
  not a persisted interview, browser microphone result, or production load
  result.
- Render remains a **simulated-AI-only** hosting configuration: its lightweight
  manifest excludes local ML packages, and no authenticated, encrypted bridge
  from Render to the laptop-local inference worker exists or has been tested.
  The local HTTPS-tunnel fallback remains the only feasible real-model demo
  path after QA database verification and manual microphone testing.

## Text-only deployment mode

`config.settings_production` unconditionally sets
`SPEECH_FEATURE_ENABLED=False`, including when a supplied environment value
attempts to enable it. Production candidate interview pages retain the typed
answer path but omit microphone, transcription, and Piper controls/scripts;
the corresponding endpoints return `speech_disabled` before any model adapter
is created. Local development keeps the default optional speech setting. No
model, audio, dump, or `.env` path is tracked by Git.

## Implemented

- QA-only exact database/role/settings/action gates with no `.env` loading.
- Three transient Piper → Silero VAD → Faster-Whisper turns, followed by model
  release, real MiniLM retrieval, real Qwen Interview proposals, strict
  `continue` allowlisting, deterministic coordinator persistence, real Qwen
  Evaluation advice, deterministic non-final scoring, and audit assertions.
- Candidate-authorized browser recording, stop, VAD/silence detection,
  Faster-Whisper transcription, editable review, and QA-only transient Piper
  playback. Audio is not recorded or persisted.
- Loopback-only Daphne launcher, optional exact HTTPS tunnel hostname, secure
  cookies for tunnel mode, in-memory email, hidden Django admin, and browser
  model actions disabled.

## Evidence and blockers

- 28 non-database release tests pass; project-wide Ruff and diff checks pass.
- Real voice smoke passes with one VAD segment and nonempty Whisper text.
- A fresh detached Qwen/MiniLM Interview case passed 1/1. This is not persisted
  end-to-end evidence.
- Three earlier verified QA attempts created only synthetic `QA_` fixtures and
  persisted zero answers. The corrected three-turn sequence still needs a new
  run after private QA variables are restored.
- Database-backed/full pytest cannot run from the current process because no
  development database variables are available. The least-privilege QA role
  correctly cannot create Django test databases.
- Manual microphone/listening, HTTPS tunnel, WebSocket-through-tunnel, and
  browser completion have not been confirmed by the user. `cloudflared` is not
  installed and no public service has been exposed.

## Exact local completion steps

In a private PowerShell session, restore the existing QA variables without
saving or printing them, then run:

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.settings_qa'
$env:DJANGO_READ_DOT_ENV = 'False'
$env:HIREFLOW_QA_MODEL_ACTIONS = '1'
$env:HIREFLOW_QA_BROWSER_VOICE = '1'
.\.venv\Scripts\python.exe scripts\verify_qa_database.py
.\.venv\Scripts\python.exe backend\manage.py run_qa_release_interview --prepare-manual
$env:HIREFLOW_QA_MODEL_ACTIONS = '0'
```

The command prints a synthetic candidate email and session path, never a
password. Set that synthetic account password interactively:

```powershell
.\.venv\Scripts\python.exe backend\manage.py changepassword <QA_candidate_email>
.\scripts\start_qa_demo.ps1
```

Open `http://127.0.0.1:8000` and sign in with the synthetic account, then open
the printed `/calling/sessions/<uuid>/` path. Play the approved question,
record, stop, transcribe, confirm a positive VAD segment count, edit the text,
and submit. Localhost is accepted as a browser secure context for microphone
testing. Manual QA is not passed until the operator confirms recording,
transcription, playback, and completion.

For a later approved HTTPS tunnel, install and authorize a tunnel tool outside
this repository, obtain one exact public hostname, and restart with:

```powershell
.\scripts\start_qa_demo.ps1 -TunnelHost '<exact-hostname>'
```

Route only that HTTPS hostname to `http://127.0.0.1:8000`. Do not expose Qwen,
PostgreSQL, a model port, or Django admin. Verify HTTPS cookies, CSRF, login,
microphone, static assets, and WebSockets before sharing the URL.

## Git and deployment

No stage, commit, push, tunnel, or deployment was performed. Tracked files do
not include model weights, audio, dumps, `.env`, or runtime QA media. The
fastest safe target remains the existing laptop with Django bound to loopback
behind an approved HTTPS tunnel. Render remains secondary because its lightweight
configuration deliberately excludes the local AI/ML stack.
