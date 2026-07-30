# Nornir

A personal, offline-first, multi-window task tracker built around a category tree, module/series generation, recurring tasks, and reusable task templates — because nothing on the market combines hierarchy, multi-window layout, and true offline independence.

> Status: **In development — all P0 and P1 features implemented.** Remaining: deployment tooling (wheelhouse/WSLg validation) and the P2 candidates (voice, agent API). See the [roadmap](#roadmap) and [`docs/implementation-plan.md`](docs/implementation-plan.md).
> Full spec: [`docs/nornir-spec-v2.md`](docs/nornir-spec-v2.md)

## What This Is

Two independent instances of the same app — one at home, one at work — each with its own local SQLite database. No sync, no cloud, no accounts. Categories (Church, Household, Homelab, Classes, work SRs, etc.) organize tasks in a tree up to 4 levels deep, with dedicated windows for tree navigation, active tasks, priority triage, task detail, and a timeline.

## Core Features

- **Category tree** — up to 4 levels deep, color-coded, right-click task creation with date auto-fill
- **Multi-window layout** — tree, task list, priority widget, detail/edit, and timeline views, independently dockable/floatable, layout persists across restarts
- **Module Series Generation** — batch-generate a run of sub-categories (e.g. class modules) with a task template stamped onto each
- **Recurring tasks** — user-configurable interval (N + days/weeks/months), not fixed presets
- **Task Template Library** — reusable, named checklists of tasks (e.g. "Network SR") applied selectively into an existing category
- **Archive, never delete** — nothing is ever hard-deleted
- **Floating sidebar mode** — collapse to a minimal always-visible task list
- **Voice input** *(P2)* — task creation and note dictation via local Whisper

See the spec for the full P0/P1/P2 breakdown and the data model.

## Tech Stack

- **GUI:** PySide6 (Qt) — multi-window/dock-widget support, `QTreeView` for the category tree
- **Storage:** SQLite, local file per machine
- **Voice:** local Whisper (small/base model), offline, no cloud dependency

## Environments

This app is built and run identically in two places:

| Environment | Notes |
|---|---|
| **Home** | Native Linux or WSL — flexible |
| **Work** | Windows 11 laptop, runs via **WSL2 + WSLg**. IT blocks non-allowlisted Windows executables, so the app runs as a Linux process (`python3 app.py`) and is displayed on the Windows desktop via WSLg — never as an installed Windows binary. |

Full setup, the WSLg validation checklist, and the home ↔ work database
migration procedure live in [`docs/deployment.md`](docs/deployment.md).

### Offline package installation (work environment)

The work environment can't reach PyPI directly (certificate errors). Packages are installed from a pre-built offline wheelhouse instead — two scripts wrap the whole flow, including Python-version/platform guards and a post-install smoke check:

```bash
# On an unrestricted machine — build the wheelhouse (~250 MB, wheels only)
scripts/build_wheelhouse.sh           # add --dev to include the test toolchain

# Transfer the wheelhouse/ folder to the work machine, then:
scripts/install_offline.sh            # creates .venv, installs with --no-index, smoke-checks
```

**Important:** PySide6 ships compiled binary wheels, not pure Python — the wheelhouse must be built for the exact same platform/architecture (Linux x86_64) **and the same Python minor version** as the work WSL distro. Pin and document the Python version below before building the wheelhouse, to avoid rebuilding it after a version mismatch.

- Python version (pin this): **3.13** — install via deadsnakes PPA (or equivalent) if the work WSL distro doesn't ship it

Whisper model weights aren't pip packages — they're separate downloaded files. Copy them into the model cache directory on the work machine using the same offline-transfer approach.

## Setup

```bash
# Clone
git clone <repo-url>
cd nornir

# Create venv
python3 -m venv .venv
source .venv/bin/activate

# Install (online)
pip install -r requirements.txt

# Install (offline — work environment)
pip install --no-index --find-links=./wheelhouse -r requirements.txt

# Run (GUI)
python3 app.py
```

## CLI usage

The same entry point supports subcommands for agent/script access.  The CLI
and the GUI share the same SQLite database (WAL mode allows safe concurrency).

```bash
# Create a task (category name or id)
nornir add-task --title "Call dentist" --category "Personal" --due 2026-08-05

# List tasks (filtered)
nornir list-tasks --category "Work" --status open in_progress

# Complete a task (triggers recurrence roll-forward if applicable)
nornir complete-task 42

# Archive a task
nornir archive-task 42

# Daily summary (text output for agent consumption)
nornir daily-summary
```

## Project Structure

*(planned — see [`docs/implementation-plan.md`](docs/implementation-plan.md))*

```
nornir/
├── app.py                  # thin shim → nornir.app:main
├── requirements.txt
├── scripts/                # wheelhouse build + offline install
├── docs/
│   ├── nornir-spec-v2.md
│   ├── implementation-plan.md
│   └── deployment.md       # WSLg checklist + DB migration procedure
└── src/
    └── nornir/             # application package (src-layout)
```

## Roadmap

- [x] Data model + SQLite schema
- [x] Tree View + category CRUD
- [x] Task CRUD + Task Detail/Edit window
- [x] Task List View
- [x] Timeline View
- [x] Module Series Generation
- [x] Recurring tasks
- [x] Archive (not delete)
- [x] Task Template Library
- [x] Priority Widget
- [x] Floating Sidebar mode
- [x] Daily summary popup
- [x] JSON export/import
- [x] CLI commands (agent-accessible task creation)
- [ ] Voice input (task creation + notes)
- [ ] Agent/API task creation (external agents like Skadi-Agents/Augur filing tasks programmatically)

## License

Personal project — no license specified yet.
