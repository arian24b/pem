# PEM: Python Execution Manager

[English](README.md) | [فارسی](README.fa.md)

[![PyPI](https://img.shields.io/pypi/v/pemexe)](https://pypi.org/project/pemexe/) [![CI](https://github.com/arian24b/pem/actions/workflows/ci.yml/badge.svg)](https://github.com/arian24b/pem/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

PEM keeps a list of Python scripts and projects, runs them on demand or on a schedule, and writes a log for every run. Each job runs in its own `uv`-managed environment, so a script can list its own dependencies. State lives in a local SQLite database.

## Features

- Jobs are single scripts or project directories, stored by name in a SQLite database.
- Each run goes through `uv`, so dependencies (`-w pandas`) and the Python version (`-v 3.13`) are per job.
- Four schedule types: `once`, `interval`, `cron`, `until_done` (retry until the job succeeds).
- One log file per run, with size-based rotation.
- A background service (systemd user unit on Linux, launchd agent on macOS) keeps the scheduler running.

## How it works

`pem add` writes a row to the SQLite database (`pem.db`). `pem run` loads the job and starts a subprocess with output redirected to a new log file. Scripts run as `uv run --no-project [--python V] [--with DEP]... script.py`. A project directory is prepared with `uv sync` (if it has a `pyproject.toml`) or `uv venv` plus `uv pip install -r requirements.txt` (if it has `requirements.txt`), then runs `main.py`, `app.py` or `python -m <dir name>`, in that order. A run fails with exit code `-1` if it exceeds `process_timeout` (1800 s by default); the number of parallel runs is capped by `max_concurrent_processes`.

Schedules are handled by APScheduler with a SQLAlchemy job store in the same database. They only fire while a scheduler process is alive: either the background service (`pem install` / `pem service start`) or `pem daemon` in a terminal.

## Install

Python 3.12 to 3.15 and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install pemexe        # or: pipx install pemexe
pem install                   # make sure pem and uv are present, install and start the background service
pem service status
```

The PyPI package is `pemexe`; the command is `pem`. From a clone: `uv sync && uv run pem --help`.

## Quick start

```bash
pem add --path ./my_script.py --script --name data-processor      # create the job and run it once
pem add --path ./my_project --name web-app --no-auto-run          # create without running
pem run --name data-processor                                     # run now
pem run --name data-processor --schedule --type interval --minutes 60
pem show                                                          # all jobs
pem status                                                        # counts and next runs
```

Sample session (output from a real run):

```text
$ pem add --path hello.py --script --name hello
ℹ Job is enabled. Executing immediately...
status:    SUCCESS
exit code: 0
log file:  ~/.local/state/pem/log/hello_20261012_050534.log

$ pem show
ID  Name   Type    Status   Path      Dependencies  Python
1   hello  script  enabled  hello.py

$ pem cron --name hello --type interval --minutes 30
Scheduler ID   pem_job_interval_1_20261012_050536
Schedule type  interval
Details        {'seconds': 0, 'minutes': 30, 'hours': 0, 'days': 0}
```

## Commands

| Command | What it does |
|---|---|
| `add -p PATH [-n NAME] [-s] [-w DEP]... [-v PY] [--disabled] [--no-auto-run]` | create a job from a script (`-s`) or a project directory |
| `show [-n NAME] [-i ID]` (alias `jobs`) | list jobs, or one job |
| `edit [-n NAME] [-i ID] [-p PATH] [-s/--project] [-w DEP]... [-v PY] [-e/--disabled]` | change a job |
| `delete [-n NAME] [-i ID]` | remove a job |
| `run [-n NAME] [-i ID] [-s] [-t TYPE] [-m MINUTES]` | run now, optionally schedule it too |
| `cron [-n NAME] [-i ID] [-t TYPE] ...` (alias `schedule`) | schedule a job |
| `crons` (alias `schedules`) | list scheduled jobs |
| `cancel -s SCHEDULER_ID` | cancel a schedule (the ID comes from `crons`) |
| `status` | job counts, schedules and next runs |
| `daemon` | run the scheduler in the foreground |
| `install` | install pem and uv if missing, then set up and start the service |
| `update-uv` | update the `uv` tool |
| `service install\|uninstall\|start\|stop\|restart\|status` | manage the background service |
| `config show\|get\|set\|reset\|path\|validate\|edit` | manage settings |

Job commands take `--name` or `--id`. If you give neither, pem asks for the name. `add` asks for `--path` when it is missing. Repeat `-w` for several dependencies: `-w pandas -w requests`.

> The job editor used to be `pem update`, which was hidden behind the self-update command. It is now `pem edit`, and `pem update` updates pem itself.

### Schedule types for `cron`

| `--type` | Options |
|---|---|
| `once` (default) | `--date 2026-01-01T10:00:00` |
| `interval` | `--seconds`, `--minutes`, `--hours`, `--days` |
| `cron` | `--cron-minute`, `--cron-hour`, `--cron-day`, `--cron-month`, `--cron-dow` |
| `until_done` | `--max-retries N`, `--retry-interval SECONDS` |

```bash
pem cron --name monitor --type interval --minutes 30
pem cron --name report  --type cron --cron-hour 9 --cron-minute 0
pem cron --name backup  --type once --date 2026-12-31T23:59:59
pem cron --name flaky   --type until_done --max-retries 5 --retry-interval 300
pem crons
pem cancel --scheduler-id pem_job_interval_1_20261201_120000
```

## Configuration and files

- Settings: `pem config show`, `pem config set KEY VALUE` (values like `true`, `5`, `a,b`, `none` are converted), `pem config path`. `pem config reset` asks for confirmation; in scripts pass `--yes`.
- Database: SQLite. By default it is `pem.db` in the directory you run `pem` from (see Troubleshooting); set `database_path` to use a fixed location. Tables are created on first use. Settings are stored in `config.json`; `pem config path` prints its location.
- Logs: one file per run, rotated by size (10 MB, 5 backups by default; change them with `pem config set`). macOS: `~/Library/Logs/pem/`. Linux: `~/.local/state/pem/log/`.

## Common commands

Built on [cfuicli](https://github.com/arian24b/cfui), so it looks and behaves like the other tools in this family.

```bash
pem help [command]     # help; -h works on any command
pem version            # version and git repository (also: -v)
pem update [--check]   # update the tool itself; --check only compares versions
pem -q ...             # quiet: no banner or notes (or PEM_QUIET=1)
```

- A missing required option is asked for when you run the tool in a terminal. In a pipe or in CI it stops with `--flag is required. Pass --flag <value> or run interactively.` (exit code 2).
- Errors appear in a red box on stderr with a non-zero exit code. Ctrl-C exits with 130.
- Color is used only on a terminal. `NO_COLOR=1` turns it off.
- `pem update` updates pem itself; `pem update-uv` updates uv.

## Troubleshooting

**`pem show` is empty or my schedules are gone.** The default database path is relative, so every working directory gets its own `pem.db`. Run `pem` from the same directory each time, or set an absolute path once: `pem config set database_path /home/me/.local/share/pem/pem.db` (the directory must exist). The `PEM_DATABASE_URL` environment variable overrides both.

**A schedule never fires.** Schedules run only while the scheduler is alive. Check `pem service status`, or run `pem daemon`.

**Where is the output of a run?** The log path is printed after `pem run`. Logs are in the directory shown under "Configuration and files".

**Python 3.15.** 3.15 is a pre-release. In testing with 3.15.0b3, importing `sqlalchemy.ext.asyncio` crashes the interpreter (segmentation fault inside `greenlet` 3.5.6), so pem does not start there yet. 3.12, 3.13 and 3.14 work.

## Development

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv build
```

Commits follow Conventional Commits. See the `Makefile` for shortcuts and `scripts/` for the release and binary builds.

## License

MIT
