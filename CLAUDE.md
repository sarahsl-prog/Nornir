# Nornir - Claude Code Guide

A personal, offline-first, multi-window task tracker built around a category tree, module/series generation, recurring tasks, and reusable task templates 

---

## Tech Stack
- **Language** - Python 3.13 
- **GUI** - PySide6(Qt) - multi-window/dock-widget support, QTreeView for the category tree
- **Storage** - SQLite, local file per machine
- **Voice** - local Whisper (small/base model) offline, no cloud dependency

---

## Code Standards

- **Modular** — each feature lives in its own sub-package; avoid god modules
- **Well commented** — explain the *why*, not the *what*; complex logic needs docstrings
- **Type-checked** — full `mypy` strict compliance; annotate all function signatures
- **Logging** — use `loguru` on all major features; include context (user_id, session_id) in log records
- **Error handling** — vigorous validation on all user input and all external API responses; never surface raw exceptions to the user or to the model
- **Tests** — write `pytest` tests as features are implemented, not after

---

## Coding Process

- **Planning & Discovery** - Read the task, scan the codebase, and build an initial plan based on the task specification and how to verify the solution.
- **Build** - Implement the plan with verification in mind. Build tests, if they don’t exist and test both happy paths and edge cases.
- **CLI commands** — The same entry point supports subcommands for agent/script access:
  ```bash
  nornir add-task --title "T" --category "C" [--due YYYY-MM-DD]
  nornir list-tasks [--category "C"] [--status open in_progress]
  nornir complete-task <id>
  nornir archive-task <id>
  nornir daily-summary
  ```
- **Verify** - Run tests, read the full output, compare against what was asked (not against your own code).
- **Fix** - Analyze any errors, revisit the original spec, and fix issues.

---


## Code Quality

```bash
pre-commit run --all-files    # Run all checks (ruff, black, mypy, bandit)
ruff check --fix .            # Lint and auto-fix
black .                       # Format
mypy src/nornir/              # Type check
bandit -r src/nornir/         # Security static analysis
```

---

## Environment Variables
All secrets go in `.env` (never committed). 

---

## Implementation Rules ##
- **One task at a time.** Implement, test, commit, then move to the next.
- **Validate before proceeding.** Run the narrowest relevant test subset after each change.
- **Check for callers** before changing signatures or data shapes.
- **Update docs alongside code** — README, config examples, API docs.
- **Commit messages**: imperative, one-line, no trailing period.
- **Never batch multiple fixes into a single commit.**

---

## Definition of Done ##
- Code written and tested.
- Lint / type checks pass.
- Documentation updated.
- Commit made with a clean, imperative message.
- Checkbox ticked in the plan doc (if using one).

---

## Communication Rules ## 
- **When to ask**: ambiguous requirements, security-sensitive changes, breaking API changes
- **When to proceed**: routine implementation within stated scope
- **Budget awareness**: warn when tool-call limits might truncate work; summarize progress clearly

