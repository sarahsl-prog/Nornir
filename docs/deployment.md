# Nornir — Deployment Guide

Covers getting Nornir running on both machines, the manual validation pass for
the work laptop (WSL2 + WSLg), and the home ↔ work database migration
procedure.

The two instances are **deliberately independent**: separate databases, no
sync, no shared backend. Nothing here connects them automatically — migration
is a manual file copy you perform when you want it.

---

## 1. Prerequisites

| Requirement | Home | Work |
|---|---|---|
| OS | Native Linux or WSL2 | Windows 11 + WSL2 |
| Display | Native X11/Wayland | **WSLg** (built into Windows 11 — no third-party X server) |
| Python | **3.13** (pinned) | **3.13** (pinned) |
| Network | Unrestricted | No PyPI access — offline wheelhouse required |

The Python pin is not cosmetic: PySide6 ships compiled binary wheels, so the
offline wheelhouse only installs on the exact minor version and platform it
was built for. Verify before building anything:

```bash
python3.13 --version    # must print 3.13.x on both machines
```

If the work WSL distro lacks 3.13 (Ubuntu 24.04 ships 3.12), install it first:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.13 python3.13-venv
```

Qt also needs a few system libraries that aren't Python packages:

```bash
sudo apt install libegl1 libgl1 libxkbcommon0
```

---

## 2. Install

### Home (online)

```bash
git clone <repo-url> && cd Nornir
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

### Work (offline wheelhouse)

On the **home/unrestricted** machine:

```bash
scripts/build_wheelhouse.sh          # ~250 MB of wheels into wheelhouse/
```

Transfer both the repo and the `wheelhouse/` folder to the work machine
(`wheelhouse/` is gitignored — copy it separately: USB, an approved file
share, whatever your IT policy permits). Then on the work machine:

```bash
cd Nornir
scripts/install_offline.sh           # installs with --no-index, then smoke-checks
.venv/bin/python app.py
```

The install script refuses to proceed if the wheelhouse is missing, and its
smoke check imports both `PySide6.QtWidgets` and `nornir.app` — so a
platform/version mismatch fails immediately with a clear message rather than
at first launch.

---

## 3. WSLg validation checklist (run once on the work laptop)

These are behaviors the automated suite cannot cover — they depend on the
Wayland compositor WSLg provides. Work through them after the first install
and note anything that misbehaves.

- [ ] **App launches and displays.** `.venv/bin/python app.py` opens the window
      on the Windows desktop. No `QT_QPA_PLATFORM` override should be needed;
      if the window never appears, check `echo $DISPLAY` and `$WAYLAND_DISPLAY`
      are set (WSLg populates both).
- [ ] **Docking works.** Drag each dock (Tree, Priority, Tasks, Timeline, Task
      Detail) to a different edge; they re-dock rather than detaching oddly.
- [ ] **Floating works.** Double-click a dock title bar to float it into its own
      window; it stays usable and can be re-docked.
- [ ] **Multi-window focus.** With a dock floated, clicking between it and the
      main window moves focus correctly (a known rough edge on some Wayland
      compositors).
- [ ] **Layout persists across restarts.** Rearrange, close the app, reopen —
      the arrangement returns. Then restart WSL entirely (`wsl --shutdown` from
      Windows) and reopen: it should still return.
- [ ] **Sidebar mode.** View → Enter Sidebar Mode collapses to the narrow strip;
      confirm it **stays on top** of Windows applications. Always-on-top is a
      window-manager hint — if WSLg ignores it, the mode still works but won't
      float above other windows; note that and we can add a fallback.
- [ ] **Restore from sidebar.** The Restore button brings back the exact
      pre-collapse layout, including any floated docks.
- [ ] **Sidebar mode survives restart.** Close while collapsed, reopen — it
      starts collapsed, and restoring still yields the full layout (not a
      default one).
- [ ] **Dialogs render.** Open the module series dialog and the template
      library; check the calendar popup in the task form draws correctly.
- [ ] **Daily summary.** Launch with at least one overdue task and confirm the
      popup appears — then relaunch and confirm it does *not* appear again the
      same day.
- [ ] **Database location is inside WSL.** Run the path check in §4 and confirm
      the path is under the Linux filesystem, **not** `/mnt/c/...` (see the
      warning there).
- [ ] **Logs are being written.** `ls ~/.local/share/nornir/logs/` shows
      `nornir.log` with a recent session line.

---

## 4. Where the data lives

Nornir stores everything under one per-user directory, resolved via
`platformdirs`:

```bash
.venv/bin/python -c "from nornir.infra import paths; print(paths.data_dir())"
# typically: /home/<user>/.local/share/nornir
```

Contents:

| Path | What |
|---|---|
| `nornir.db` | The entire dataset (categories, tasks, notes, templates, UI state) |
| `nornir.db-wal`, `nornir.db-shm` | SQLite write-ahead log — present while the app runs |
| `logs/nornir.log` | Rotating application log (10 MB, 10 files retained) |

**Keep the database on the Linux filesystem, not `/mnt/c`.** Windows-mounted
paths under WSL2 go through a translation layer that is dramatically slower
for the small random I/O SQLite does, and file-locking semantics there are not
reliable enough for a WAL-mode database. The default location is already
correct — this only matters if you deliberately override it.

To point the app at a different location (a copied dataset, or a test
database), set `NORNIR_DATA_DIR`:

```bash
NORNIR_DATA_DIR=~/nornir-test .venv/bin/python app.py
```

---

## 5. Migrating the database between machines

Per the spec, the migration mechanism is a **raw file copy** — zero effort,
exact fidelity, no export step. The JSON export (File → Export JSON Backup) is
for human-readable backups and diffing, not for moving data between machines.

### Procedure

1. **Close Nornir on both machines.** This is the important step. While the app
   is running, recent writes may live in the `-wal` sidecar file rather than
   the main `.db`. Closing cleanly checkpoints the WAL back into `nornir.db`.
2. Copy the whole data directory (or at minimum `nornir.db`):

   ```bash
   # from the source machine
   cp ~/.local/share/nornir/nornir.db /path/to/transfer/nornir.db
   ```

3. On the destination machine, back up the existing database first — this
   **replaces** the destination's data, it does not merge:

   ```bash
   mv ~/.local/share/nornir/nornir.db ~/.local/share/nornir/nornir.db.bak
   cp /path/to/transfer/nornir.db ~/.local/share/nornir/nornir.db
   ```

4. Launch the app. The schema migration runner brings an older database
   forward automatically if the destination is running a newer version.

### If you must copy while the app is running

Copy `nornir.db`, `nornir.db-wal`, and `nornir.db-shm` **together** — the
database is only consistent as that set. Copying the `.db` alone from a
running app silently loses recent changes.

### Restoring from a JSON backup

JSON import requires an **empty** database (v1 limitation — merge semantics
are out of scope). To restore:

```bash
mv ~/.local/share/nornir/nornir.db ~/.local/share/nornir/nornir.db.bak
.venv/bin/python app.py     # creates a fresh empty database
# then: File → Import JSON Backup…
```

---

## 6. Troubleshooting

**No window appears.** Confirm WSLg is active (`echo $WAYLAND_DISPLAY` should
print something like `wayland-0`). On older Windows 11 builds, `wsl --update`
from PowerShell installs/refreshes WSLg.

**`ImportError: libEGL.so.1: cannot open shared object file`.** The Qt system
libraries are missing: `sudo apt install libegl1 libgl1 libxkbcommon0`.

**`pip install` fails with certificate errors on the work machine.** Expected —
that machine has no PyPI access. Use the wheelhouse flow in §2; never work
around it by disabling certificate verification.

**The offline install fails with "no matching distribution".** The wheelhouse
was built for a different Python minor version or platform. Rebuild it on a
machine whose `python3.13 --version` matches the work machine exactly.

**Layout comes back wrong after an update.** Layout is stored under a versioned
key; if a future release changes the dock set incompatibly it falls back to
defaults rather than restoring a broken arrangement. Rearranging once and
restarting confirms the new layout persists.
