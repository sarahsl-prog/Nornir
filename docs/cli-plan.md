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

### Task 3.1: Create `src/nornir/cli/__init__.py` and `src/nornir/cli/commands.py`
- [ ] `commands.py` with typed argument parsers for all subcommands
- [ ] Commands delegate to existing repos (no new storage layer)
- [ ] Use `argparse` from stdlib, `tabulate` or plain text for list output
- [ ] Commit

### Task 3.2: Wire CLI into `app.py` entry point
- [ ] Modify `main()` to branch: if `--gui` or no subcommand → launch Qt; otherwise → run CLI
- [ ] Update `pyproject.toml` scripts entry point if needed
- [ ] Commit

## Phase 4: Write CLI tests

### Task 4.1: Add `tests/test_cli.py`
- [ ] Test `add-task` creates a task and it appears in the database
- [ ] Test `list-tasks` with various filters
- [ ] Test `complete-task` marks a task complete
- [ ] Test `archive-task` archives a task
- [ ] Test `daily-summary` returns text output
- [ ] Run full test suite
- [ ] Commit

## Phase 5: Update documentation

### Task 5.1: Update `README.md`
- [ ] Add "CLI usage" section with examples for each command
- [ ] Mention WAL mode and coexistence with the GUI
- [ ] Commit

### Task 5.2: Update `CLAUDE.md`
- [ ] Add CLI commands to the Coding Process / Build section
- [ ] Commit

## Phase 6: Final verification
- [ ] Run `pre-commit run --all-files`
- [ ] Run full test suite
- [ ] End-to-end manual test: GUI open → CLI creates task → GUI refreshes and sees it
- [ ] Commit any fixes
