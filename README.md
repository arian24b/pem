# PEM - Python Execution Manager 🚀

**A powerful, modern CLI tool for managing, scheduling, and executing Python scripts and projects with ease.**

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Built with uv](https://img.shields.io/badge/built%20with-uv-blue)](https://github.com/astral-sh/uv)

## ✨ What is PEM?

PEM (Python Execution Manager) is your comprehensive solution for managing Python script and project execution. Whether you need to run scripts on-demand, schedule automated tasks, or manage complex Python workflows, PEM provides an intuitive CLI interface with powerful scheduling capabilities.

### 🎯 Perfect for:
- **Data Scientists** scheduling ETL pipelines and analysis scripts
- **DevOps Engineers** automating deployment and maintenance tasks
- **Python Developers** managing multiple projects and scripts
- **System Administrators** running scheduled monitoring and backup tasks
- **Anyone** who needs reliable Python execution with proper logging and scheduling

## 🌟 Key Features

### 📋 **Unified Job Management**
- **Two Job Types**: Handle both standalone Python scripts and full projects
- **Smart Auto-execution**: Automatically run jobs after creation (configurable)
- **Dependency Management**: Specify Python dependencies for script-type jobs
- **Enable/Disable Control**: Easy job activation and deactivation

### ⏰ **Flexible Scheduling System**
- **Multiple Schedule Types**:
  - `once` - Execute at a specific date/time
  - `interval` - Run every X seconds/minutes/hours/days
  - `cron` - Use cron-style expressions for complex schedules
  - `until_done` - Retry until successful execution
- **Unified Execution**: Single `run` command for immediate + optional scheduling
- **Background Processing**: All scheduled jobs run automatically in the background

### 📊 **Comprehensive Monitoring & Logging**
- **Detailed Execution Logs**: Every run logged with timestamps, status, and output
- **Real-time Status**: View system overview with job counts and schedules
- **SQLite Database**: Persistent local storage for all jobs and execution history
- **Rich CLI Output**: Color-coded feedback with emojis for better UX

### 🛠 **Developer-Friendly Interface**
- **Intuitive Commands**: Simple, memorable command structure
- **Type-safe CLI**: Built with modern Typer framework
- **Clean Help Output**: No clutter - only essential information shown
- **Actionable Error Messages**: Clear guidance when things go wrong

## 🚀 Quick Start

### Installation Options

#### Option 1: Using UV (Recommended)
```bash
# Install UV if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install PEM from PyPI
uv tool install pemexe

# Or install from source
git clone https://github.com/yourusername/pem.git
cd pem
uv sync
uv run pem --help
```

#### Option 2: Using pip
```bash
pip install pemexe
```

#### Option 3: Download Binary
```bash
# Download the latest binary from releases
wget https://github.com/yourusername/pem/releases/latest/download/pem
chmod +x pem
sudo mv pem /usr/local/bin/
```

### Development Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/pem.git
cd pem

# Install development dependencies
make dev-install
# or manually:
uv sync --group dev --group build --group release

# Run tests
make test

# Build the project
make build

# Build standalone binary
make binary
```

### Installation
```bash
# If using in your project
uv add pemexe
# OR
pip install pemexe

# If using as tool
uvx --from pemexe pem
```


```bash
# Clone and install locally
git clone https://github.com/arian24b/pem.git
cd pem
uv sync

# Or install from source
pip install -e .
```

### Basic Usage

```bash
# Add and run a Python script immediately
pem add --path ./my_script.py --script --name "data-processor"

# Add a project without auto-execution
pem add --path ./my_project --name "web-app" --no-auto-run

# Execute an existing job
pem run --name "data-processor"

# Execute and schedule for hourly runs
pem run --name "data-processor" --schedule --type interval --minutes 60

# View all jobs
pem show

# Check system status
pem status
```

## 📖 Command Reference

### Job Management Commands

#### `pem add` - Create New Jobs
Create a new job to execute Python scripts or projects.

```bash
# Add a simple script with dependencies
pem add --path ./script.py --script --name "analyzer" --with pandas requests

# Add a project (uses existing environment)
pem add --path ./my_project --name "web-server"

# Add disabled job (no auto-execution)
pem add --path ./script.py --script --disabled --no-auto-run

# Add with specific Python version
pem add --path ./script.py --script --python 3.11 --with numpy
```

**Key Options:**
- `--path`, `-p`: Path to Python script or project directory *(required)*
- `--name`, `-n`: Unique job name (auto-generated if not provided)
- `--script`, `-s`: Treat as single Python script (vs. project)
- `--with`, `-w`: Python dependencies to install (scripts only)
- `--python`, `-v`: Required Python version (scripts only)
- `--enabled/--disabled`, `-e`: Enable/disable job execution
- `--auto-run/--no-auto-run`: Execute immediately after creation

#### `pem show` - Display Job Information
Display details of jobs (all jobs if no filter specified).

```bash
# Show all jobs
pem show

# Show specific job by name
pem show --name "data-processor"

# Show specific job by ID
pem show --id 1
```

#### `pem update` - Modify Existing Jobs
Update properties of an existing job.

```bash
# Enable a disabled job
pem update --name "data-processor" --enabled

# Update job path
pem update --id 1 --path ./new_script.py

# Change job type and dependencies
pem update --name "analyzer" --script --with pandas numpy matplotlib
```

#### `pem delete` - Remove Jobs
Remove a job permanently from the system.

```bash
# Delete by name
pem delete --name "old-job"

# Delete by ID
pem delete --id 1
```

### Execution Commands

#### `pem run` - Execute Jobs (Immediate + Optional Scheduling)
Execute a job immediately, with optional recurring schedule setup.

```bash
# Execute job immediately
pem run --name "data-processor"

# Execute and set up hourly schedule
pem run --name "monitor" --schedule --type interval --minutes 60

# Execute by ID with daily schedule
pem run --id 1 --schedule --type interval --minutes 1440
```

**Key Options:**
- `--id`, `-i`: ID of job to execute
- `--name`, `-n`: Name of job to execute
- `--schedule/--no-schedule`, `-s`: Set up recurring schedule
- `--type`, `-t`: Schedule type (interval, once, cron, until_done)
- `--minutes`, `-m`: Interval in minutes (for interval scheduling)

### Scheduling Commands

#### `pem cron` - Advanced Job Scheduling
Schedule a job for automatic execution using various timing options.

```bash
# Schedule every 30 minutes
pem cron --name "monitor" --type interval --minutes 30

# Schedule daily at 9 AM using cron
pem cron --name "report" --type cron --cron-hour 9 --cron-minute 0

# Schedule one-time execution
pem cron --name "backup" --type once --date "2024-12-31T23:59:59"

# Retry until success
pem cron --name "flaky-job" --type until_done --max-retries 5 --retry-interval 300
```

**Schedule Types:**
- **interval**: `--seconds`, `--minutes`, `--hours`, `--days`
- **once**: `--date` (ISO format: 2024-01-01T10:00:00)
- **cron**: `--cron-minute`, `--cron-hour`, `--cron-day`, `--cron-month`, `--cron-dow`
- **until_done**: `--max-retries`, `--retry-interval`

#### `pem crons` - List Scheduled Jobs
List all jobs currently scheduled for automatic execution.

```bash
pem crons
```

#### `pem cancel` - Cancel Scheduled Jobs
Cancel a scheduled job by its scheduler ID.

```bash
# Cancel specific scheduled job (use ID from 'pem crons')
pem cancel --scheduler-id "pem_job_interval_1_20241201_120000"
```

### System Commands

#### `pem status` - System Overview
Display system overview with job counts and scheduling statistics.

```bash
pem status
```

Shows:
- Total jobs (enabled/disabled, scripts/projects)
- Active scheduled jobs with next run times
- System health at a glance

## 🏗 Architecture & Design

PEM is built with modern Python technologies:

- **AsyncTyper**: Custom async CLI framework extending Typer
- **SQLAlchemy**: Robust async database ORM for data persistence
- **APScheduler**: Reliable background job scheduling
- **Faker**: Automatic job name generation
- **AsyncIO**: Efficient asynchronous execution throughout

### Database Schema
- **Jobs Table**: Stores job definitions, paths, dependencies, and settings
- **Execution History**: Tracks all job runs with status, logs, and timing
- **Schedule Tracking**: Manages active schedules and their configurations

## 🔧 Configuration & Setup

PEM works out of the box with minimal configuration:

- **Database**: SQLite (`pem.db`) in working directory
- **Logs**: Stored in `./logs/` with timestamped filenames
- **Auto-initialization**: Database and tables created automatically
- **Environment Isolation**: Uses proper Python environment handling

## 📁 Project Structure

```
pem/
├── pem/
│   ├── cli.py              # Main CLI interface with all commands
│   ├── settings.py         # Configuration and settings
│   ├── core/
│   │   ├── executor.py     # Job execution engine
│   │   └── scheduler.py    # Background scheduling manager
│   └── db/
│       ├── database.py     # Database configuration & sessions
│       └── models.py       # SQLAlchemy data models
├── logs/                   # Execution logs directory
├── pem.db                 # SQLite database file
└── pyproject.toml         # Project configuration with uv
```

## � Common Workflows

### 1. Quick Script Development & Testing
```bash
# Add and test a script immediately
pem add --path ./analysis.py --script --name "analysis" --with pandas

# Iterate and re-run during development
pem run --name "analysis"
```

### 2. Production Data Pipeline Setup
```bash
# Add ETL script
pem add --path ./etl_pipeline.py --script --name "daily-etl" --no-auto-run

# Schedule for daily execution at 2 AM
pem cron --name "daily-etl" --type cron --cron-hour 2 --cron-minute 0

# Monitor scheduled jobs
pem crons
pem status
```

### 3. System Monitoring Setup
```bash
# Add monitoring script
pem add --path ./health_check.py --script --name "health-monitor" --no-auto-run

# Set up 5-minute monitoring
pem cron --name "health-monitor" --type interval --minutes 5

# Check system status
pem status
```

### 4. Project Management
```bash
# Add a Python project
pem add --path ./my_fastapi_app --name "api-server" --no-auto-run

# Run when needed
pem run --name "api-server"

# Update project path as it evolves
pem update --name "api-server" --path ./updated_fastapi_app
```

## 🛠 Development & Contributing

### Development Workflow

This project uses **UV** for modern Python package management and follows best practices for professional Python development.

#### Quick Development Commands
```bash
# Install all dependencies (dev, build, release)
make dev-install

# Run code quality checks
make lint

# Format code
make format

# Run tests with coverage
make test

# Build Python package
make build

# Build standalone binary
make binary

# Full release process
make release
```

#### Manual UV Commands
```bash
# Install project and dependencies
uv sync

# Install specific dependency groups
uv sync --group dev          # Development tools
uv sync --group build        # Build tools
uv sync --group release      # Release tools

# Run commands in the UV environment
uv run pem --help           # Run PEM
uv run pytest              # Run tests
uv run ruff check pem/      # Lint code
uv run mypy pem/            # Type check

# Build and publish
uv build                    # Build wheel and source dist
uv publish --token $TOKEN   # Publish to PyPI
```

#### Project Structure
```
pem/
├── pem/                    # Main package
│   ├── cli.py             # CLI interface
│   ├── settings.py        # Configuration
│   ├── core/              # Core scheduling logic
│   └── db/                # Database models
├── scripts/               # Build and release scripts
│   ├── build_binary.py    # PyInstaller automation
│   └── release.py         # Release automation
├── pyproject.toml         # Project configuration
├── uv.toml                # UV configuration
├── uv.lock                # Dependency lock file
└── Makefile               # Development shortcuts
```

#### Release Process

```bash
# Option 1: Automated release
python scripts/release.py

# Option 2: Manual steps
make lint test              # Quality checks
make build                  # Build package
make binary                 # Build binary
uv publish --token $TOKEN   # Publish to PyPI
```

#### Configuration Files

- **pyproject.toml**: Main project configuration with modern PEP 518/621 standards
- **uv.toml**: UV-specific settings for dependency resolution and publishing
- **uv.lock**: Reproducible dependency versions
- **Makefile**: Development shortcuts and common commands

## 🆚 Why Choose PEM?

### vs. Cron/Task Scheduler
- ✅ **Cross-platform**: Works identically on Windows, macOS, and Linux
- ✅ **Python-native**: No shell scripting required
- ✅ **Dependency management**: Built-in package handling
- ✅ **Rich logging**: Detailed execution history and status tracking
- ✅ **User-friendly**: Modern CLI with helpful error messages

### vs. Other Python Task Runners
- ✅ **Zero configuration**: Works immediately without complex setup files
- ✅ **Local storage**: No external databases or services required
- ✅ **Unified interface**: Single tool for all execution needs
- ✅ **Flexible scheduling**: Multiple timing patterns in one tool
- ✅ **Developer UX**: Intuitive commands with excellent error handling

### vs. Manual Script Management
- ✅ **Automated scheduling**: Set-and-forget execution
- ✅ **Centralized management**: All scripts in one place
- ✅ **Execution tracking**: History, logs, and status monitoring
- ✅ **Error handling**: Retry mechanisms and failure notifications
- ✅ **Environment isolation**: Proper dependency and version management

## 🤝 Contributing

We welcome contributions! To get started:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes** with tests
4. **Run the test suite**: `pytest`
5. **Submit a pull request**

### Development Setup
```bash
git clone https://github.com/arian24b/pem.git
cd pem
uv sync
```

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙋‍♀️ Support & Community

- **Issues**: [GitHub Issues](https://github.com/arian24b/pem/issues)
- **Feature Requests**: [GitHub Discussions](https://github.com/arian24b/pem/discussions)
- **Documentation**: See the comprehensive [Tool Overview](PEM_TOOL_OVERVIEW.md)

---

**Made with ❤️ by [Arian Omrani](https://github.com/arian24b)**

*PEM - Schedule and execute Python scripts and projects with ease* 🐍✨
