# Nornir

A personal, offline-first, multi-window task tracker built around a category tree, module/series generation, recurring tasks, and reusable task templates — because nothing on the market combines hierarchy, multi-window layout, and true offline independence.

> Status: **Pre-implementation.** Spec finalized, scaffolding not yet started.
> Full spec: [`docs/nornir-spec-v2.md`](docs/nornir-spec-v2.md) *(move the spec file into the repo under this path, or update this link)*

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

### Offline package installation (work environment)

The work environment can't reach PyPI directly (certificate errors). Packages are installed from a pre-built offline wheelhouse instead:

```bash
# On an unrestricted machine — build the wheelhouse
pip download -d wheelhouse -r requirements.txt

# Transfer the wheelhouse/ folder to the work machine, then:
pip install --no-index --find-links=./wheelhouse -r requirements.txt
```

**Important:** PySide6 ships compiled binary wheels, not pure Python — the wheelhouse must be built for the exact same platform/architecture (Linux x86_64) **and the same Python minor version** as the work WSL distro. Pin and document the Python version below before building the wheelhouse, to avoid rebuilding it after a version mismatch.

- Python version (pin this): `TBD`

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

# Run
python3 app.py
```

## Project Structure

*(to be filled in as scaffolding takes shape)*

```
nornir/
├── app.py
├── requirements.txt
├── docs/
│   └── nornir-spec-v2.md
└── src/
    └── ...
```

## Roadmap

- [ ] Data model + SQLite schema
- [ ] Tree View + category CRUD
- [ ] Task CRUD + Task Detail/Edit window
- [ ] Task List View
- [ ] Timeline View
- [ ] Module Series Generation
- [ ] Recurring tasks
- [ ] Archive (not delete)
- [ ] Task Template Library
- [ ] Priority Widget
- [ ] Floating Sidebar mode
- [ ] Daily summary popup
- [ ] JSON export/import
- [ ] Voice input (task creation + notes)
- [ ] Agent/API task creation (external agents like Skadi-Agents/Augur filing tasks programmatically)

## License

Personal project — no license specified yet.
