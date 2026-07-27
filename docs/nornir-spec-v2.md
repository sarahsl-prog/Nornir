# Nornir — Spec v2 (Finalized)

## Problem Statement
Sarah runs multiple independent life domains simultaneously (church, household, homelab, classes, and an ever-growing stack of side projects) and no existing task tool combines: a category-first tree structure, multiple simultaneous purpose-built windows, voice-driven capture, and offline/local-only operation across two unlinked machines (home + work). Existing tools force a tradeoff between hierarchy, multi-window flexibility, and offline independence — none offer all three.

## Goals
- Capture a task in under 5 seconds from the tree view via right-click, with dates prefilled.
- See, at a glance, what's overdue or due soon without opening a task.
- Run identically (same feature set, independent data) on two machines with zero sync/networking dependency.
- Support voice as a first-class input method for both task creation and note-taking.
- Let the UI collapse to a minimal footprint (floating sidebar) for low-friction glancing during the day, and expand to a full multi-pane layout for planning sessions.

## Non-Goals (v1)
- **Sync between machines.** Explicitly independent instances by design — not a technical limitation, a stated requirement. Revisit only if priorities change.
- **Mobile app / mobile access.** Desktop-only for now.
- **Multi-user / sharing / collaboration.** Single-user tool.
- **Cloud backend of any kind.** Local storage only (see Data Model).

## Users
Single persona: Sarah, using the app on two independent desktop environments (home + work), each with its own local dataset.

---

## Core Concepts & Data Model

### Category
- Top-level categories (Church, Household, Homelab, Classes, etc.), user-defined and editable.
- Categories support sub-categories (tree structure, max depth 4 — e.g. Classes → Course → Module → Final Project Task).
- Each category has a user-assigned color, used for coding across all views.

### Task
- Belongs to exactly one category/sub-category node (strict — no multi-category membership in v1; cross-referencing between tasks is a separate future concept, not multi-categorization).
- Fields: title, description/notes, creation date (auto), start date (offered from creation date), due date, importance/priority flag, status, category reference.
- **Status values:** Open, In-Progress, Complete, Deferred, Blocked.
- Supports **module series generation** — a two-layer batch operation, not a flat task series:
  1. Generate a run of sub-categories under a parent (e.g., "Module 1"–"Module 8" under a course), spaced on a defined interval (e.g., weekly).
  2. Apply a fixed **task template** (e.g., "Required Reading," "Lab") to every generated sub-category, with dates derived from each module's slot in the sequence. Template is the same across all generated modules — one-off exceptions (e.g., a quiz only in Module 3) are added manually after generation, not part of the template itself.
- Overdue / due-soon states are derived (not stored) from due date vs. current date.

### Recurring Tasks
- Distinct from Module Series Generation: recurring tasks are ongoing, not tied to generating new categories — e.g., "take out trash every Tuesday," "pay a bill monthly," "check homelab backups every 6 days."
- **Recurrence rule: user-configurable interval** — an integer + unit (days/weeks/months), e.g. "every 6 days," "every 2 weeks," "every 1 month." Not full calendar-rule recurrence (no "2nd Tuesday of the month" style rules) — kept simple by design to avoid scope creep into iCal-style complexity.
- Completing an instance generates/reveals the next occurrence; the recurrence lives on the task definition, not as N pre-created copies.

### Archiving
- No hard delete. "Deleting" a task or category archives it — hidden from active views but retained in the database.
- Archived items excluded from Tree View, Task List, Timeline, and Priority Widget by default; a separate "Show Archived" toggle/view can surface them later if needed (not required for v1 unless you want it).
- Auto-archiving to a secondary location/store if the dataset grows large — explicitly deferred to P2/future, not designed for now.

### Data Portability
- **Raw file copy** (SQLite `.db` file) — the actual migration mechanism between home/work instances. Zero-effort, exact fidelity, no export step needed.
- **JSON export/import** — human-readable backup format, preserves the full category tree via nested structure (categories → sub-categories → tasks), used for manual backups, diffing, or hand-editing outside the app rather than machine-to-machine migration.

### Task Template Library
- Distinct from Module Series Generation: no new categories/sub-categories are created. A template applies into an **existing** category/sub-category the user has already navigated to.
- User maintains a library of named templates (e.g. "Network SR," "App SR"), each containing a checklist of candidate tasks (e.g. get-logs, download-logs, logs-to-logserver, log-analysis, troubleshooting-zoom).
- Applying a template to a category shows the checklist; user selects which tasks to actually create this time (not all-or-nothing) — supports different SR types needing overlapping-but-different task sets.
- Templates are user-created/edited/deleted, independent of any specific category — reusable across many instances (e.g. every new SR sub-category).

### Notes
- Freeform notes attachable to a task, voice-capturable.

---

## Views & Windows

The app is multi-window; each window type below is independently dockable/floatable and the overall layout is user-configurable and persists between sessions.

| Window | Purpose | Key behavior |
|---|---|---|
| **Tree View** | Full category/sub-category hierarchy | Right-click → "New Task" creates a task pre-filed under that node. Right-click → "New Module Series" generates sub-categories + task template (see Core Concepts). |
| **Task List View** | All open (or in-progress) tasks | Filter is user-configurable — by category, status, or both. |
| **Priority Widget** | Small always-visible panel | Shows top 3 tasks ranked by a **computed urgency score** — combining the task's priority field with proximity to due date (closer due date = higher score, at a given priority level). No manual "pin to top" flag needed. Exact scoring formula is an implementation detail, not a spec-level decision. |
| **Task Detail/Edit** | Full editing surface for one task | Opens on selection from any other view; shows/edits all fields including notes. |
| **Timeline View** | Chronological view of tasks by date | Toggle between "all categories" and single-category focus. |
| **Floating Sidebar Mode** | Collapsed single-pane task list | Alternate compact mode, not a separate window type — a display mode the app can drop into. |

**Task creation flow specifics:**
- A current-month calendar is shown at the top of the task creation form for fast date selection.
- Creation date auto-fills; app offers to also set it as the start date (single confirm, not two manual entries).
- Module series generation: define parent category, number of modules, interval (e.g. weekly), and the task template to stamp onto each generated module.

**Voice:**
- Voice-driven task creation (parse intent → pre-fill creation form, user confirms before save).
- Voice-driven note dictation attached to an existing task.

**Visual coding:**
- Category color applied consistently across tree, list, timeline, and priority widget.
- Task icons shift color/state when overdue or due-soon (two visually distinct states minimum: overdue vs. due-soon).

---

## Requirements

### Must-Have (P0)
1. Multi-level category tree with CRUD on categories/sub-categories.
2. Task CRUD with fields listed above (title, dates, category, priority, status, notes).
3. Tree View window with right-click task creation, date auto-fill.
4. Task List View with user-configurable open/in-progress filter.
5. Task Detail/Edit window.
6. Category color coding across all views.
7. Overdue/due-soon visual state on task icons.
8. Local-only storage (no network dependency), fully functional offline on both machines independently.
9. Configurable window layout that persists across restarts.
10. Timeline View (all-categories / single-category toggle).
11. Module series generation (sub-category batch generation + task template application, per Core Concepts).
12. Recurring tasks (user-configurable interval — N + days/weeks/months, per Core Concepts).
13. Archive-not-delete for tasks and categories (per Core Concepts).
14. Task Template Library — reusable named templates with a selectable task checklist, applied into an existing category (per Core Concepts).

### Nice-to-Have (P1)
15. Priority Widget (top-3 high-importance/near-due).
16. Floating Sidebar collapsed mode.
17. Calendar-at-top-of-creation-form UI.
18. Daily summary popup — shown once per calendar day (not on every launch, since the app may be left running via Floating Sidebar mode; needs a "already shown today" check rather than a pure on-launch trigger).
19. JSON export/import for backup and manual portability (per Core Concepts — file copy is the migration mechanism and needs no dedicated feature work).

### Future Considerations (P2)
20. Voice-driven task creation.
21. Voice-driven note dictation.
22. Auto-archive to secondary storage location if dataset grows large.
23. Cross-referencing between tasks (e.g., linking a related task in another category, without changing its home category).
24. API/programmatic interface allowing an external agent to create tasks on Sarah's behalf (e.g. Skadi-Agents or Augur filing a follow-up task from an alert). Raises its own open questions later — auth/trust model for local agent access, which fields an agent can set vs. leave to the user, whether agent-created tasks are visually distinguished from user-created ones.
25. (Candidates raised during brainstorm go here.)

---

## Open Questions
*(to resolve in the brainstorm pass)*
1. ~~**Status model**~~ — **RESOLVED:** Open, In-Progress, Complete, Deferred, Blocked.
2. ~~**Category depth**~~ — **RESOLVED:** max 4 levels (e.g. Classes → Course → Module → Final Project Task).
3. ~~**Series creation rule**~~ — **RESOLVED:** two-layer generator — batch-create sub-categories on an interval, then stamp a single fixed task template onto each. Per-module exceptions handled manually post-generation.
4. ~~**Recurring tasks**~~ — **RESOLVED:** yes, separate from module series — user-configurable interval (N + days/weeks/months), staying P0. No calendar-rule complexity (e.g. "2nd Tuesday") — scoped out intentionally.
5. ~~**Task deletion/archiving**~~ — **RESOLVED:** archive-and-hide, never hard delete. Auto-archive to secondary storage deferred to P2.
6. ~~**Cross-category tasks**~~ — **RESOLVED:** strictly single-category. Cross-referencing between tasks added as a P2 future consideration.
7. ~~**"High importance" for Priority Widget**~~ — **RESOLVED:** computed urgency score (priority field × due-date proximity), not a manual flag. Exact formula deferred to implementation.
8. ~~**Reminders/notifications**~~ — **RESOLVED:** daily summary popup, shown once per calendar day (not tied to launch, since the app may stay running). P1.
9. ~~**Data portability**~~ — **RESOLVED:** JSON export/import for human-facing backup (P1); raw SQLite file copy as the actual home/work migration mechanism (no feature work needed).
10. ~~**Platform parity**~~ — **RESOLVED:** both environments run via WSL2/Ubuntu. Home runs natively or via WSL (flexible); work runs via WSL2 + WSLg specifically to avoid Windows executable-allowlist restrictions — the app runs as a Linux process (`python3 app.py`), displayed on the Windows desktop via WSLg/RDP, never as an installed Windows binary. Audio/mic passthrough for voice input works via WSLg's PulseAudio routing (may require a one-time Windows privacy-settings mic grant).

---

## Technical Considerations (from earlier discussion)
- **GUI:** PySide6 (Qt) — native multi-window/dock-widget support, QTreeView fits the tree view directly.
- **Storage:** SQLite, local file per machine.
- **Voice:** local Whisper (small/base model) for offline speech-to-text, no cloud dependency.
- Stack choice enables strict independence between machines (no shared backend), matching the non-sync requirement.

### Deployment constraint: work environment
- Work laptop (Windows 11) blocks execution of non-allowlisted Windows executables via IT policy, but WSL2 usage itself is unrestricted.
- **Resolution:** run the app as a Linux process inside WSL2, displayed on the Windows desktop via **WSLg** (built into Windows 11 — no third-party X server needed). This is never an installed Windows binary, so it falls outside the executable-allowlist policy's scope.
- WSLg passes audio/mic through to Windows via PulseAudio, supporting the voice input feature — may need a one-time Windows privacy-settings grant for mic access to WSL apps.

### Deployment constraint: package installation (no direct pip/uv access)
- Work environment hits certificate errors reaching standard package indexes (PyPI etc.) — no direct `pip`/`uv` internet access.
- **Resolution:** offline wheelhouse pattern. On an unrestricted machine, run `pip download -d wheelhouse -r requirements.txt` (or `uv` equivalent) to fetch all packages + transitive dependencies as `.whl` files. Transfer the wheelhouse folder to the work machine; install via `pip install --no-index --find-links=./wheelhouse -r requirements.txt`.
- **Constraint:** PySide6 ships compiled binary wheels (not pure Python) — the wheelhouse must be built for the exact target platform/architecture (Linux x86_64) **and exact Python minor version** (e.g. 3.11 vs 3.12) as the work WSL distro. **Action item: pin and document the exact Python version used across both environments before building the wheelhouse**, to avoid rebuilding it after a version mismatch.
- Whisper model weights are not pip packages — they're separate downloaded files (hundreds of MB–GB depending on model size) and must be manually copied into the model cache directory on the work machine using the same offline-transfer approach.
