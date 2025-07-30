# PEM - Python Execution Manager 🚀

**A powerful, modern Python tool for managing, scheduling, and executing Python scripts and projects with ease.**

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Built with uv](https://img.shields.io/badge/built%20with-uv-blue)](https://github.com/astral-sh/uv)

## ✨ What is PEM?

PEM is your all-in-one solution for Python execution management. Whether you're running one-off scripts, managing complex projects, or scheduling automated tasks, PEM makes it simple and reliable.

### 🎯 Perfect for:
- **DevOps Engineers** managing deployment scripts and automation
- **Data Scientists** running scheduled data processing jobs
- **Python Developers** organizing and executing multiple projects
- **System Administrators** automating maintenance tasks
- **Anyone** who needs reliable Python script execution with logging

## 🌟 Key Features

### 📋 **Job Management**
- **Two Job Types**: Handle both standalone scripts and full Python projects
- **Dependency Management**: Automatically install and manage script dependencies using `uv`
- **Smart Execution**: Uses `uv run` for fast, isolated script execution
- **Project Support**: Full support for Python projects with virtual environments

### ⏰ **Flexible Scheduling**
- **Multiple Schedule Types**:
  - `once` - Run at a specific date/time
  - `interval` - Run every X seconds/minutes/hours/days
  - `cron` - Use cron expressions for complex schedules
  - `until_done` - Keep retrying until the job succeeds
- **Background Execution**: All scheduled jobs run in the background
- **Persistent Storage**: Schedules survive system restarts

### 📊 **Comprehensive Logging & Tracking**
- **Detailed Logs**: Every execution is logged with timestamps and output
- **Execution History**: Track all job runs with status, exit codes, and timing
- **SQLite Database**: Local storage for jobs, schedules, and execution history
- **Real-time Status**: See what's running, what succeeded, and what failed

### 🛠 **Developer-Friendly CLI**
- **Intuitive Commands**: Simple, memorable command structure
- **Rich Output**: Colored terminal output with emojis for better UX
- **Flexible Options**: Extensive command-line options for all use cases
- **Built with Typer**: Modern, type-safe CLI framework

## 🚀 Quick Start

### Installation

```bash
# Install PEM
pip install pem

# Or using uv (recommended)
uv add pem
```

### Basic Usage

```bash
# Run a Python script with dependencies
pem run my-data-script --script --path ./data_processor.py --with pandas --with requests

# Add a project job
pem run my-web-app --project --path ./my-flask-app --add-only

# Schedule a job to run every hour
pem schedule my-data-script --type interval --hours 1

# List all jobs
pem list

# View job execution history
pem history my-data-script

# Check scheduler status
pem status
```

## 📖 Detailed Usage

### Managing Jobs

#### Script Jobs
Perfect for standalone Python scripts with specific dependencies:

```bash
# Add and run a script with dependencies
pem run data-processor \
  --script \
  --path ./scripts/process_data.py \
  --with pandas \
  --with requests \
  --with beautifulsoup4

# Just add the job without running
pem run backup-script --script --path ./backup.py --add-only

# Run an existing job
pem run backup-script --run-only
```

#### Project Jobs
For full Python projects with their own environments:

```bash
# Add a Python project
pem run my-api --project --path ./my-fastapi-project --add-only

# Run the project (will use project's own dependencies)
pem run my-api --run-only
```

### Scheduling Jobs

#### One-time Execution
```bash
# Run once at a specific time
pem schedule backup-job --type once --date "2025-12-31 23:59:59"
```

#### Interval-based Scheduling
```bash
# Every 30 minutes
pem schedule data-sync --type interval --minutes 30

# Every 2 hours
pem schedule hourly-report --type interval --hours 2

# Every day
pem schedule daily-backup --type interval --days 1
```

#### Cron-style Scheduling
```bash
# Every weekday at 9 AM
pem schedule morning-report --type cron --cron-hour 9 --cron-dow 1-5

# Every Monday at midnight
pem schedule weekly-cleanup --type cron --cron-hour 0 --cron-dow 1
```

#### Retry Until Success
```bash
# Keep trying every 5 minutes until it succeeds (max 20 attempts)
pem schedule critical-task --type until_done --retry-interval 300 --max-retries 20
```

### Monitoring & Management

```bash
# List all jobs
pem list

# Show job details
pem show my-job

# View execution history
pem history my-job

# Check what's scheduled and running
pem status

# Enable/disable jobs
pem enable my-job
pem disable my-job

# Remove jobs
pem remove my-job
```

## 🏗 Architecture

PEM is built with modern Python best practices:

- **SQLAlchemy**: Robust database ORM for job and execution tracking
- **APScheduler**: Reliable job scheduling with multiple backends
- **Typer**: Type-safe, intuitive CLI framework
- **uv**: Fast Python package management and script execution
- **AsyncIO**: Efficient asynchronous execution

## 📁 Project Structure

```
pem/
├── pem/
│   ├── cli.py          # Command-line interface
│   ├── main.py         # Application entry point
│   ├── settings.py     # Configuration
│   ├── core/
│   │   ├── executor.py # Job execution engine
│   │   └── scheduler.py # Background scheduling
│   └── db/
│       ├── database.py # Database configuration
│       └── models.py   # SQLAlchemy models
├── logs/               # Execution logs
├── pem.db             # SQLite database
└── pyproject.toml     # Project configuration
```

## 🔧 Configuration

PEM works out of the box with sensible defaults:

- **Database**: SQLite (`pem.db`) in the current directory
- **Logs**: Stored in `./logs/` directory
- **Virtual Environments**: Created in project directories as `.pem_venv`

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. Fork the repository
2. Create a feature branch: `git checkout -b my-new-feature`
3. Make your changes and add tests
4. Run the test suite: `pytest`
5. Submit a pull request

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙋‍♀️ Support

- **Issues**: [GitHub Issues](https://github.com/arian24b/pem/issues)
- **Discussions**: [GitHub Discussions](https://github.com/arian24b/pem/discussions)

## 🚀 Why Choose PEM?

### vs. Cron
- ✅ Cross-platform (works on Windows, macOS, Linux)
- ✅ Dependency management built-in
- ✅ Detailed logging and execution history
- ✅ Easy job management with CLI
- ✅ Python-native (no shell scripting needed)

### vs. Other Task Runners
- ✅ Specifically designed for Python
- ✅ No complex configuration files
- ✅ Built-in dependency isolation
- ✅ Simple CLI interface
- ✅ Local database storage (no external dependencies)

### vs. Manual Script Running
- ✅ Automated scheduling
- ✅ Execution history and monitoring
- ✅ Dependency management
- ✅ Error handling and retries
- ✅ Centralized job management

---

**Made with ❤️ by [Arian Omrani](https://github.com/arian24b)**

*PEM - Making Python execution management simple, reliable, and powerful.*
