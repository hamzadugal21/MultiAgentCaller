# Agent Operating Guide

This file applies to the entire repository. It is the permanent operating guide for every coding agent working on MultiAgent Recruitment Caller.

## Required context

Before beginning project work, read these files in order:

1. `AGENTS.md`
2. `docs/AI_HANDOFF.md`
3. `docs/ROADMAP.md`
4. `docs/DECISIONS.md`
5. `docs/ARCHITECTURE.md`

Read `docs/WORK_LOG.md` when reconstructing history or preparing a context update. Inspect the current Git branch, commit, status, and relevant source files before making changes. Git and the codebase take precedence if a context document is stale; correct the document as part of the task.

## Non-negotiable rules

- Never open, print, expose, copy, move, rename, or modify `.env`.
- Never place credentials, tokens, passwords, database secrets, candidate private data, resumes, recordings, or transcripts in documentation, logs, prompts, fixtures, or Git.
- Preserve existing PostgreSQL migration history and Django application labels. Create new migrations for schema changes; never rewrite an applied migration.
- Keep Django migrations inside `backend/<app>/migrations/`.
- Do not weaken authentication, authorization, upload validation, audit protection, consent controls, or secret-handling safeguards.
- Do not make final employment decisions automatically. AI output is advisory; an authorized human must review and approve consequential employment decisions.
- Inspect existing work before editing, avoid unrelated changes, and preserve user work.
- Validate changes in proportion to their risk before reporting completion.
- Do not claim planned or unfinished functionality is complete.
- Report exact test counts and command results, not only that tests passed.
- Record important errors, failed validation, warnings, and blockers.

## Context-document maintenance

After every meaningful completed task:

- Update `docs/AI_HANDOFF.md` and append to `docs/WORK_LOG.md`.
- Update `docs/ROADMAP.md` when progress or sequencing changes.
- Update `docs/DECISIONS.md` when an important technical, architectural, security, database, AI, or product decision is made.
- Update `docs/ARCHITECTURE.md` when the system architecture changes.

Keep all context documents concise, factual, synchronized with Git, and free of unsupported claims or private data. Future agents must append new work-log entries and must not rewrite historical entries.

Update context immediately, without waiting for the periodic checkpoint, when any of these occurs:

- A task is completed.
- A blocker or important error occurs.
- A migration is created or applied.
- Architecture changes.
- A security decision is made.
- A Git commit is created.
- Tests begin failing.
- A work session is about to end.

## Automatic four-prompt context checkpoint

The local counter is `var/agent-state/context-counter.json`. It is intentionally ignored by Git and must contain only a non-negative integer field named `prompts_since_checkpoint`. It must never contain secrets or project data.

For every project-related user message:

1. Read the counter without reading `.env`.
2. Increment `prompts_since_checkpoint` by one.
3. If the value is below four, save it and continue.
4. When the value reaches four, pause before continuing the requested project work and synchronize:
   - `docs/AI_HANDOFF.md`
   - `docs/WORK_LOG.md`
   - `docs/ROADMAP.md` if progress changed
   - `docs/DECISIONS.md` if a decision was made
   - `docs/ARCHITECTURE.md` if architecture changed
5. At the checkpoint, record the current branch, current commit, worktree status, completed work, current task, changed files, exact test results, errors and blockers, known warnings, Week completion percentage, overall project percentage, and exact next recommended task.
6. Reset `prompts_since_checkpoint` to `0` after synchronization.
7. Briefly report: “Automatic context checkpoint updated.”
8. Continue the requested work without asking the user to run commands.

Do not create a false work-log entry when nothing meaningful changed. Do not create a separate Git commit merely because four prompts elapsed. Include context-document updates in the next relevant validated task commit.

## Repository conventions

- `frontend/`: Django templates, shared static assets, design references, and frontend documentation.
- `backend/`: `manage.py`, Django configuration, applications, migrations, and application tests.
- `database/`: database documentation, diagrams, safe seed utilities, and maintenance material; never Django migrations, credentials, or real backups.
- `ai_system/`: planned orchestration, agents, prompts, tool interfaces, safety, evaluation, and human approval logic.
- `ml/`: planned processing, training, inference, evaluation, and ignored local datasets/model artifacts.
- `docs/`: project-wide architecture, development, security, API, decision, roadmap, and handoff documentation.
- `scripts/`: development, maintenance, setup, and validation utilities.
- `tests/`: future cross-application integration, system, and end-to-end tests.
- `var/`: ignored runtime media, collected static files, logs, and local agent state.

Use `backend/manage.py` for Django management commands. Keep `config.settings_development` as the pytest settings module. Preserve the `PROJECT_ROOT`, `BACKEND_ROOT`, `FRONTEND_ROOT`, and `BASE_DIR` path contract in Django settings.

## Standard validation

For ordinary backend or cross-project changes, run from the repository root:

```powershell
.\.venv\Scripts\python.exe backend\manage.py check
.\.venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check backend
git diff --check
```

Add focused tests, migration checks, security checks, static/template checks, or production-setting checks when the task requires them. Before committing, inspect the staged diff and confirm that only intended files are staged.
