# Nornir — Project Implementation Plan

Derived from [`nornir-spec-v2.md`](nornir-spec-v2.md). Each task below is sized to be
implemented, tested, and committed independently ("one task at a time" per CLAUDE.md).
Tick the checkbox when a task meets the Definition of Done (code + tests + lint/type
checks + docs + clean commit).

---

## Locked Decisions (resolved with Sarah, 2026-07-27)

| Decision | Resolution |
|---|---|
| Package layout | `src/nornir/` (src-layout, package named after the project). CLAUDE.md quality commands updated to match. |
| Python version | **Pinned to 3.13** on both machines. The work WSL distro must have Python 3.13 installed before the offline wheelhouse is built (deadsnakes PPA or a distro that ships it). |
| Show Archived | **Included in v1** — a "Show Archived" checkbox in the Task List View filter bar, plus an Unarchive action, so archive mistakes are recoverable without touching SQLite. |

## Working Assumptions (small calls made while planning — veto any of these)

1. **Priority field** = three levels (`Low`, `Normal`, `High`), not a boolean flag. The
   spec says "flag" in one place but the Priority Widget's "at a given priority level"
   implies levels; three levels keeps the urgency score meaningful.
2. **Notes** = the task's `description` field **plus** a `task_notes` table of
   timestamped freeform notes. Timestamped rows suit voice dictation (P2) appending
   notes without clobbering the description.
3. **Archiving a category cascades** — archiving a category archives its whole subtree
   (sub-categories and tasks). Unarchiving restores the same set. A dangling
   sub-category under an archived parent has no sensible home otherwise.
4. **Due-soon window** defaults to 3 days before the due date (configurable in a
   settings table later; constant at first).
5. **Recurring task mechanics**: completing a recurring task marks *that row* Complete
   (history preserved) and inserts a fresh row with start/due dates advanced by the
   interval and the recurrence rule copied forward. Exactly one "live" instance exists
   at a time — matching the spec's "generates/reveals the next occurrence, not N
   pre-created copies."
6. **Timeline View v1** = a chronological list grouped by due date (headers per day),
   not a graphical Gantt-style canvas. Cheap, useful, and re-skinnable later.

---

## Phase Overview

| Phase | Theme | Spec items covered |
|---|---|---|
| 0 | Scaffolding, tooling, CI + CodeQL code scanning, test harness | infra for everything |
| 1 | Data layer: schema, migrations, repositories, domain logic | P0 #8, #13 (storage side), foundations of #12 |
| 2 | Qt application shell: models, event bus, docking, layout persistence | P0 #9 |
| 3 | Core windows: Tree, Task Detail/Edit, Task List, Timeline | P0 #1–#7, #10, Show Archived |
| 4 | Generators: recurring tasks, module series, template library, archive UX | P0 #11, #12, #13, #14 |
| 5 | P1 features: Priority Widget, sidebar mode, calendar form, daily summary, JSON | P1 #15–#19 |
| 6 | Packaging & deployment: wheelhouse, WSLg validation, backup docs | deployment constraints |
| 7 | P2 (outline only): voice, cross-referencing, agent API | P2 #20–#24 |

Phases 0→4 deliver every P0 requirement. Phase 5 delivers all of P1.

---

## Phase 0 — Scaffolding & Tooling

### 0.1 Repository skeleton and packaging config
- [x] Create `pyproject.toml`: project metadata, `requires-python = ">=3.13,<3.14"`,
  src-layout (`[tool.setuptools]` / hatchling `packages = ["src/nornir"]`), console
  entry point `nornir = nornir.app:main`. (Distribution named `nornir-tracker` to
  avoid clashing with the unrelated `nornir` package on PyPI; the import package is
  still `nornir`.)
- [x] Create `src/nornir/__init__.py` (holds `__version__`), `src/nornir/app.py` with a
  `main()` that opens an empty `QMainWindow` — proves the stack runs end to end.
- [x] Keep root `app.py` as a thin shim (`from nornir.app import main; main()`) so the
  README's `python3 app.py` invocation keeps working.
- [x] `requirements.txt` (runtime: `PySide6`, `loguru`, `platformdirs`) and
  `requirements-dev.txt` (`pytest`, `pytest-qt`, `mypy`, `ruff`, `black`, `bandit`,
  `pre-commit`).
- **Done when:** `pip install -e .` succeeds and `python3 app.py` opens a window.

### 0.2 Quality tooling
- [x] Configure in `pyproject.toml`: `ruff` (lint + import sorting), `black`, `mypy`
  strict (`strict = true`, `packages = ["nornir"]`), `bandit` target `src/nornir`.
- [x] `.pre-commit-config.yaml` running ruff, black, mypy, bandit — as `language:
  system` hooks against the venv tools, since the work machine can't build
  pre-commit's own isolated environments offline.
- [x] `pytest` config: `testpaths = ["tests"]`; `QT_QPA_PLATFORM=offscreen` set in
  `tests/conftest.py` so GUI tests run headless (works in WSL and CI alike).
- **Done when:** `pre-commit run --all-files` passes on the skeleton.

### 0.3 Logging and app-paths module
- [x] `src/nornir/infra/logging.py` — loguru setup: rotating file sink under the app
  data dir + stderr sink; a `session_id` bound at startup so every record carries it
  (per CLAUDE.md logging rule).
- [x] `src/nornir/infra/paths.py` — resolve data dir via `platformdirs`
  (`~/.local/share/nornir/` on Linux/WSL): DB file, log dir, layout/settings storage.
  Overridable via `NORNIR_DATA_DIR` env var (useful for tests and for pointing at a
  copied DB).
- [x] Tests: paths resolve, env override works, logging writes a record.
- **Done when:** unit tests pass; app startup logs a session line to the file sink.

### 0.4 CI workflow + CodeQL code scanning
- [x] `.github/workflows/ci.yml` — on push and pull request: set up Python 3.13,
  install `requirements.txt` + `requirements-dev.txt`, then run the same gates as
  local pre-commit — `ruff check`, `black --check`, `mypy src/nornir/`,
  `bandit -r src/nornir/`, and `pytest` with `QT_QPA_PLATFORM=offscreen` (Qt needs
  the `libegl1`/`libgl1` apt packages on the runner for import to succeed headless).
- [x] `.github/workflows/codeql.yml` — CodeQL "advanced setup" for Python: runs on
  push to `main`, pull requests, and a weekly `schedule`; results surface in the
  repo's Security → Code scanning tab and as PR checks.
- [ ] Manual (Sarah, repo Settings → Advanced Security): enable secret scanning +
  push protection — complements bandit, which doesn't cover pushed secrets.
- **Done when:** both workflows pass on a PR and a CodeQL analysis appears in the
  Security tab.

---

## Phase 1 — Data Layer

### 1.1 Domain model & enums
- [x] `src/nornir/domain/models.py` — frozen dataclasses: `Category`, `Task`,
  `TaskNote`, `Template`, `TemplateItem`. Enums: `TaskStatus` (OPEN, IN_PROGRESS,
  COMPLETE, DEFERRED, BLOCKED), `Priority` (LOW, NORMAL, HIGH), `RecurrenceUnit`
  (DAYS, WEEKS, MONTHS).
- [x] `Task` carries an optional `Recurrence(interval, unit)` value object — the
  both-or-neither rule is unrepresentable in the domain model; the schema enforces
  it on the paired DB columns.
- **Done when:** mypy strict passes; enums round-trip to/from their DB string values.

### 1.2 SQLite schema & migration runner
- [x] `src/nornir/db/schema.py` — append-only `MIGRATIONS` tuple applied by a tiny
  runner that tracks `PRAGMA user_version`. Foreign keys ON,
  WAL mode (better multi-window responsiveness on one file).
- [x] Schema v1:
  - `categories(id, parent_id → categories, name, color, position, created_at, archived_at)`
  - `tasks(id, category_id → categories, title, description, created_at, start_date, due_date, priority, status, recurrence_interval, recurrence_unit, archived_at)`
  - `task_notes(id, task_id → tasks, body, created_at)`
  - `templates(id, name, archived_at)` / `template_items(id, template_id → templates, title, description, position)`
  - `app_state(key, value)` — layout blobs, "daily summary last shown", due-soon window.
  - Indexes: `tasks(category_id)`, `tasks(due_date)`, `tasks(status)`, `categories(parent_id)`; partial indexes filtered on `archived_at IS NULL` where it pays.
  - Dates stored as ISO-8601 TEXT (`YYYY-MM-DD` for dates, full timestamp for `created_at`) — sortable, human-readable, JSON-friendly.
- [x] `src/nornir/db/connection.py` — open/create DB at the paths-module location,
  apply migrations on startup, expose one connection for the single-process app.
- [x] Tests: fresh DB creation, migration idempotency, FK enforcement.
- **Done when:** deleting the DB file and launching recreates a valid empty schema.

### 1.3 Category repository
- [x] `src/nornir/db/category_repo.py` — CRUD returning domain objects. Rules enforced
  here (not in the UI): **max depth 4** on create/move; archive cascades to the
  subtree (single UPDATE with a recursive CTE); unarchive restores the same set;
  reject un-archiving a node whose ancestor is still archived.
- [x] `get_tree()` returns the full active tree in one query, ordered
  by `position` — the Tree View model consumes this directly.
- [x] Tests: depth limit (create at depth 5 fails), cascade archive/unarchive, ordering,
  cycle-prevention on move, and a rows-never-deleted assertion.
- **Done when:** all repo tests pass; no SQL lives outside the `db` package.

### 1.4 Task repository
- [x] `src/nornir/db/task_repo.py` — CRUD; validation (title required, both-or-neither
  recurrence fields, due ≥ start when both set); archive/unarchive; notes
  (append/list); queries: by category (optionally including descendants), by status
  set, by due-date cutoff, active-only vs include-archived.
- [x] `complete_task(task_id)` implements the recurring roll-forward (Assumption 5)
  in one transaction: mark Complete, and if recurrence set, insert the successor with
  dates advanced via `nornir.domain.dates` (calendar-aware month arithmetic — e.g.
  Jan 31 + 1 month → Feb 28, day clamped to target month length).
- [x] Tests: recurrence roll-forward for days/weeks/months incl. month-end clamping;
  completion of a non-recurring task creates nothing; dateless recurring tasks.
- **Done when:** repo tests pass; recurring behavior matches spec exactly.

### 1.5 Template repository
- [x] `src/nornir/db/template_repo.py` — template CRUD (archive-not-delete applies to
  templates too), item CRUD with ordering, `apply(template_id, category_id, selected_item_ids, base_date)` creating only the selected tasks in one transaction.
- [x] Tests: partial selection creates only chosen tasks; applying twice creates
  independent copies (templates are stamps, not links); rollback when the selection
  includes a foreign item.
- **Done when:** repo tests pass.

### 1.6 Derived-state logic (pure functions)
- [x] `src/nornir/domain/urgency.py`:
  - `due_state(task, today, window) -> DueState` (NONE / DUE_SOON / OVERDUE) — derived,
    never stored, per spec.
  - `urgency_score(task, today) -> float` — proposed formula (tunable constant table,
    documented in the module docstring):
    `score = priority_weight[priority] + proximity`, where `priority_weight` = {HIGH: 100, NORMAL: 50, LOW: 0} and `proximity = clamp(14 - days_until_due, 0, 28)` (overdue tasks get `14 + min(days_overdue, 14)`). Result: within a priority band, closer/overdue sorts higher; a HIGH task always outranks a NORMAL one — matching "closer due date = higher score, at a given priority level."
  - Tasks with no due date get proximity 0; Complete/archived tasks are excluded by the caller.
- [x] Tests: table-driven cases across the boundary days; property: score monotonic in
  due-date proximity within a fixed priority.
- **Done when:** pure-function tests pass; formula documented for later tuning.

---

## Phase 2 — Application Shell

### 2.1 Event bus
- [x] `src/nornir/ui/events.py` — a `QObject` signal hub (`category_changed`,
  `task_changed`, `template_changed`, `layout_mode_changed`, each carrying ids, with
  an `ALL_CHANGED = 0` sentinel for bulk operations). Windows subscribe and
  refresh; repos never import UI. This is the one mechanism keeping five windows
  consistent — every later view task depends on it.
- [x] Tests: signal emission/reception with `pytest-qt`'s `qtbot`.
- **Done when:** two dummy widgets stay in sync through the bus in a test.

### 2.2 Qt item models
- [x] `src/nornir/ui/models/category_tree_model.py` — `QAbstractItemModel` over
  `CategoryRepo.get_tree()`; roles for name, color (as `QColor` decoration), and id.
  Refreshes on `category_changed`; `index_for_id` helper for selection restore.
- [x] `src/nornir/ui/models/task_table_model.py` — `QAbstractTableModel` over a task
  query; columns: title, category (color-swatched), start, due, priority, status;
  custom `DUE_STATE_ROLE` exposing the due-state (Phase 3.5 maps it to icons).
- [x] Tests: model row counts, role data, refresh on bus signal (headless).
- **Done when:** `QTreeView`/`QTableView` smoke tests render both models offscreen.

### 2.3 Main window, docking, layout persistence
- [x] `src/nornir/ui/main_window.py` — `QMainWindow` acting as dock host. Each view is
  a `QDockWidget` (dockable, floatable, closable) registered via `add_dock_view`.
  A `View` menu toggles each window. `src/nornir/db/app_state.py` provides the
  key-value storage.
- [x] Persist layout via `saveState()`/`saveGeometry()` into `app_state` on close and
  on layout change (debounced); restore on startup; versioned key so a future
  incompatible layout format can fall back to defaults cleanly.
- [x] Tests: save → restore round-trip preserves dock arrangement (offscreen).
- **Done when:** rearranged/floated windows come back identically after restart (P0 #9).

---

## Phase 3 — Core Windows (P0)

### 3.1 Tree View window + category CRUD
- [x] `src/nornir/ui/views/tree_view.py` — `QTreeView` on the category model.
- [x] Category dialogs: create/rename (name + `QColorDialog` color), reorder within
  siblings (drag or up/down actions), move to another parent (depth revalidated —
  repo error surfaces as a friendly message, never a raw exception).
- [x] Context menu: **New Task** (→ 3.2, category + dates prefilled), **New
  Sub-category**, **Apply Template…** (stub until 4.3), **New Module Series…** (stub
  until 4.2), **Archive**, and **Unarchive** when shown via the archived toggle.
- [x] Archive confirm dialog states the cascade ("archives N sub-categories and M
  tasks").
- [x] Tests: context-menu actions fire correct handlers; depth-violation path shows
  error and creates nothing.
- **Done when:** full category lifecycle is possible from the tree alone (P0 #1, #3, #6).

### 3.2 Task Detail/Edit window
- [x] `src/nornir/ui/views/task_detail.py` — form: title, description, category picker
  (tree combo), start/due `QDateEdit`s, priority, status, recurrence row ("every
  [N] [days/weeks/months]" — checkbox enables it), notes list (timestamped,
  append-only textbox below).
- [x] Creation flow per spec: creation date auto-fills; a single "use as start date?"
  pre-checked checkbox (one confirm, not two entries). When opened from tree
  right-click, category is pre-filed.
- [x] Opens populated on task selection signal from any other view; Save validates via
  repo and emits `task_changed`.
- [x] Tests: prefill correctness from right-click path; validation error display;
  save round-trip.
- **Done when:** a task can be created in <5s from the tree (P0 #2, #3, #5; goal 1).

### 3.3 Task List View
- [x] `src/nornir/ui/views/task_list.py` — `QTableView` on the task table model with a
  filter bar: category dropdown (with "include sub-categories" check), status
  multi-select (defaults to Open + In-Progress), **Show Archived** checkbox.
- [x] Row styling: category color swatch; due-state icon per task. Double-click →
  Task Detail. Context menu: status changes, archive, **unarchive** (visible when
  showing archived).
- [x] Filter selections persist in `app_state`.
- [x] Tests: each filter narrows correctly; archived rows appear only with toggle on.
- **Done when:** P0 #4 + locked Show Archived decision are demonstrable.

### 3.4 Timeline View
- [x] `src/nornir/ui/views/timeline.py` — chronological list grouped under date
  headers (by due date; undated tasks in a trailing "No date" bucket), "Today"
  divider, all-categories vs single-category toggle (combo box).
- [x] Reuses task model + due-state icons; single-category mode includes descendants.
- [x] Tests: grouping/order correctness; category toggle filters.
- **Done when:** P0 #10 demonstrable.

### 3.5 Visual state system
- [x] `src/nornir/ui/theming.py` — central place mapping `DueState` → icon/color
  (overdue and due-soon visually distinct, per spec) and category color → swatch/row
  accents. All views consume this module so the coding stays consistent (P0 #6, #7).
- [x] A minute-level `QTimer` re-emits a refresh at midnight rollover so due states
  stay correct in a long-running app (relevant to sidebar mode).
- [x] Tests: state→icon mapping; rollover triggers refresh signal.
- **Done when:** the same task shows identical state cues in list, tree badge (if any),
  and timeline.

---

## Phase 4 — Generators & Templates (P0)

### 4.1 Recurring tasks UI surface
- [ ] Recurrence editor already on the detail form (3.2); this task wires completion
  paths (list context menu, detail status change) through `TaskRepo.complete_task`
  so the roll-forward fires from anywhere; successor appears via `task_changed`.
- [ ] A subtle "↻ every N unit" badge in list/timeline rows.
- [ ] Tests (UI level): completing a recurring task from the list shows the successor
  with advanced dates.
- **Done when:** P0 #12 demonstrable end to end.

### 4.2 Module Series Generation
- [ ] `src/nornir/services/series_generator.py` — pure service:
  inputs `(parent_category_id, base_name, count, start_date, interval_n, interval_unit, template_id)`.
  In one transaction: create sub-categories "Base 1"…"Base N" (each slot's date =
  `start_date + (i-1) × interval`), then stamp **all** items of the chosen template
  into each module with start/due derived from that module's slot date. Depth
  validated up front (parent must be ≤ depth 3).
- [ ] `src/nornir/ui/dialogs/series_dialog.py` — launched from tree context menu:
  parent (prefilled), name stem, count, interval (N + unit), start date, template
  picker, and a preview pane ("will create 8 sub-categories × 4 tasks = 32 tasks")
  before OK.
- [ ] Tests: service-level — correct category count, per-module dates, template
  stamped fully on each, transaction rolls back wholly on failure; dialog-level —
  preview math.
- **Done when:** P0 #11 matches the spec's two-layer definition exactly.

### 4.3 Task Template Library
- [ ] `src/nornir/ui/dialogs/template_library.py` — manage templates: create/rename/
  archive templates, add/edit/reorder/remove items. Reachable from a main-window
  menu.
- [ ] `src/nornir/ui/dialogs/apply_template.py` — from tree context menu "Apply
  Template…": pick template → checklist of its items **with per-item checkboxes**
  (all pre-checked), base date field → creates only checked items via
  `TemplateRepo.apply`. This is the SR workflow from the spec.
- [ ] Tests: partial application; library edits don't affect previously created tasks.
- **Done when:** P0 #14 demonstrable ("Network SR" scenario from the spec works).

### 4.4 Archive UX pass
- [ ] Sweep: every "delete-like" affordance is labeled **Archive**; no code path issues
  a `DELETE` on categories/tasks/templates (enforced by a repo-layer test asserting
  row counts never drop).
- [ ] Unarchive available from Task List (toggle view) and tree archived view.
- [ ] Tests: archive → hidden from all four active views; unarchive → returns.
- **Done when:** P0 #13 holds app-wide.

---

## Phase 5 — P1 Features

### 5.1 Priority Widget
- [ ] `src/nornir/ui/views/priority_widget.py` — compact dock widget listing top 3
  active tasks by `urgency_score` (Phase 1.6); shows title, category color, due
  cue; click → Task Detail. Recomputes on `task_changed` and midnight rollover.
- [ ] Tests: top-3 ordering matches score function on fixture data.
- **Done when:** P1 #15 demonstrable.

### 5.2 Floating Sidebar mode
- [ ] A display **mode**, not a new window (per spec): `main_window` gains
  `enter_sidebar_mode()` — hides docks/menus, shrinks to a narrow always-on-top
  frameless-ish strip hosting the compact task list (and priority top-3), with a
  restore button. Normal layout snapshot saved before entering; restored on exit.
- [ ] Mode persisted so the app can *start* in sidebar mode if it was closed in it.
- [ ] Manual validation note: verify always-on-top behavior under WSLg specifically
  (Wayland window-manager quirks are the risk here — see 6.2).
- [ ] Tests: mode round-trip restores the prior dock layout.
- **Done when:** P1 #16 demonstrable.

### 5.3 Calendar-at-top of creation form
- [ ] Add `QCalendarWidget` (current month) to the top of the Task Detail window in
  *creation* mode; clicking a date sets due date (second click convention: first
  click = due; modifier-click = start). Collapsible so the edit form stays compact.
- [ ] Tests: calendar click updates the date fields.
- **Done when:** P1 #17 demonstrable.

### 5.4 Daily summary popup
- [ ] `src/nornir/services/daily_summary.py` — on a periodic timer (not just launch,
  per spec — the app may run for days in sidebar mode): if
  `app_state['summary_last_shown'] != today`, show popup (overdue list, due-today,
  due-soon counts) and stamp today. Fires at startup *and* on day rollover while
  running.
- [ ] Tests: shown once per calendar day across simulated restarts and rollovers.
- **Done when:** P1 #18, including the "already shown today" check, demonstrable.

### 5.5 JSON export/import
- [ ] `src/nornir/services/json_io.py` — export: nested structure (categories →
  sub-categories → tasks → notes) + templates + a `format_version`; stable key
  order for diff-ability (per spec: backup/diff/hand-edit, not migration).
- [ ] Import: validate against expected shape (reject unknown `format_version`,
  report per-record errors); import into an **empty** DB only in v1 (merge
  semantics are a can of worms — documented limitation).
- [ ] Round-trip property test: export → fresh DB → import → export produces
  identical JSON.
- **Done when:** P1 #19 demonstrable.

---

## Phase 6 — Packaging & Deployment

### 6.1 Offline wheelhouse tooling
- [ ] `scripts/build_wheelhouse.sh` — runs on the unrestricted machine:
  `pip download -d wheelhouse -r requirements.txt --python-version 3.13 --platform manylinux_2_28_x86_64 --only-binary=:all:` (exact tags verified against PySide6's published wheels at implementation time).
- [ ] `scripts/install_offline.sh` — the `--no-index --find-links` install, plus a
  post-install smoke check (`python -c "import PySide6; import nornir"`).
- [ ] README: replace `TBD` pin with 3.13; document the deadsnakes/install step for a
  work distro that lacks 3.13.
- **Done when:** wheelhouse built on one machine installs cleanly into a fresh 3.13
  venv with networking disabled.

### 6.2 WSLg validation checklist (manual, on the work laptop)
- [ ] Documented checklist in `docs/deployment.md`: window docking/floating behavior
  under WSLg, multi-window focus, always-on-top for sidebar mode, layout
  persistence across WSL restarts, DB file location inside the WSL filesystem (not
  `/mnt/c` — I/O performance), and the raw-`.db`-copy migration procedure
  (home ↔ work) with the "close the app first" warning (WAL files).
- **Done when:** checklist exists and has been run once on the work machine.

---

## Phase 7 — P2 Outline (not scheduled; captured for architecture only)

These are **not planned in detail** — listed so earlier phases don't paint us into a
corner:

- **Voice capture (#20, #21):** the clean seams already exist — task creation is
  "fill the detail form programmatically, user confirms" and notes are append-only
  rows. Whisper integration becomes a producer for those two entry points. Keep
  `services/` free of UI imports so a `voice/` package can call them.
- **Auto-archive to secondary store (#22):** archiving already goes through the repos;
  a future job can move `archived_at < cutoff` rows to a second SQLite file.
- **Cross-referencing (#23):** would be a `task_links` table — no v1 schema impact.
- **Agent/API task creation (#24):** repos + services are UI-free by construction, so
  a local socket/HTTP facade can reuse them; auth/trust model deliberately unresolved.

---

## Cross-Cutting Rules (apply to every task)

- Repos own all SQL; services own multi-step transactions; UI owns nothing but Qt.
  Dependency direction: `ui → services → db → domain`, never backwards.
- Every dialog surfaces validation failures as friendly messages — raw exceptions
  never reach the user (CLAUDE.md).
- Every phase-completing commit updates README's roadmap checkboxes and this plan's
  checkboxes.
- Test tiers: pure-function tests (domain), repo tests on a temp DB file, and
  `pytest-qt` offscreen tests for UI wiring. GUI pixel-perfection is manually
  verified; behavior is automated.
