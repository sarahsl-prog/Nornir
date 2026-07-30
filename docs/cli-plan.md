# CLI Implementation Plan — Agent-accessible task management

## Goal
Add a command-line interface to Nornir so an agent (or any shell script) can create, list, complete, and archive tasks without running the Qt GUI. The CLI and the GUI must be able to coexist — SQLite WAL mode makes this safe.

## Scope
- `nornir add-task` — create a task under a category (by name or by id)
- `nornir list-tasks` — list tasks with optional filters
- `nornir complete-task` — mark a task complete (triggering recurrence roll-forward)
- `nornir archive-task` — archive a task
- `nornir daily-summary` — text output of today's summary for agent consumption

## Phase 1: Enable WAL mode for safe concurrent access

### Task 1.1: Add `PRAGMA journal_mode=WAL` in `db/connection.py`
- [x] Add WAL pragma immediately after opening the connection
- [x] Verify existing tests still pass
- [x] Commit

## Phase 2: Add category lookup by name

### Task 2.1: Add `get_by_name()` to `CategoryRepo`
- [x] Implement `get_by_name(name: str) -> Category | None`
- [x] Write unit test
- [x] Run tests, verify pass
- [x] Commit

## Phase 3: Build the CLI module

### Task 3.1: Create `src/nornir/cli/commands.py` and `__init__.py`
- [x] `commands.py` with typed argument parsers for all subcommands
- [x] Commands delegate to existing repos (no new storage layer)
- [x] Use `argparse` from stdlib, plain text for list output
- [x] Commit

### Task 3.2: Wire CLI into `app.py` entry point
- [x] Modify `main()` to branch: if a CLI subcommand is detected → run CLI; otherwise → launch Qt
- [x] Update `pyproject.toml` scripts entry point if needed
- [x] Commit

## Phase 4: Write CLI tests

### Task 4.1: Add `tests/test_cli.py`
- [x] Test `add-task` creates a task and it appears in the database
- [x] Test `list-tasks` with various filters
- [x] Test `complete-task` marks a task complete
- [x] Test `archive-task` archives a task
- [x] Test `daily-summary` returns text output
- [x] Run full test suite
- [x] Commit

## Phase 5: Update documentation

### Task 5.1: Update `README.md`
- [x] Add "CLI usage" section with examples for each command
- [x] Mention WAL mode and coexistence with the GUI
- [x] Commit

### Task 5.2: Update `CLAUDE.md`
- [x] Add CLI commands to the Coding Process / Build section
- [x] Commit

## Phase 6: Final verification
- [x] Run `pre-commit run --all-files`
- [x] Run full test suite
- [x] End-to-end manual test: CLI commands work independently
- [x] Commit any fixes
