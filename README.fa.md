# PEM: مدیر اجرای پایتون

[English](README.md)

PEM فهرستی از اسکریپت‌ها و پروژه‌های پایتون را نگه می‌دارد، آن‌ها را بنا به درخواست یا طبق زمان‌بندی اجرا می‌کند و برای هر اجرا لاگ می‌نویسد. هر کار (job) در محیط خودش با `uv` اجرا می‌شود، پس هر اسکریپت می‌تواند وابستگی‌های خودش را اعلام کند. وضعیت در یک پایگاه‌داده SQLite محلی ذخیره می‌شود.

## نصب

پایتون ۳٫۱۲ تا ۳٫۱۵ و [uv](https://docs.astral.sh/uv/).

```bash
uv tool install pemexe        # یا: pipx install pemexe
pem install                   # از وجود pem و uv مطمئن می‌شود، سرویس پس‌زمینه را نصب و راه‌اندازی می‌کند
pem service status
```

بستهٔ PyPI نامش `pemexe` است و دستور آن `pem`. از روی کلون: `uv sync && uv run pem --help`.

## شروع سریع

```bash
pem add --path ./my_script.py --script --name data-processor      # کار را می‌سازد و یک بار اجرا می‌کند
pem add --path ./my_project --name web-app --no-auto-run          # می‌سازد، اجرا نمی‌کند
pem run --name data-processor                                     # همین حالا اجرا کن
pem run --name data-processor --schedule --type interval --minutes 60
pem show                                                          # همهٔ کارها
pem status                                                        # شمارش‌ها و اجراهای بعدی
```

## دستورها

| دستور | کار |
|---|---|
| `add -p PATH [-n NAME] [-s] [-w DEP]... [-v PY] [--disabled] [--no-auto-run]` | ساخت کار از یک اسکریپت (`-s`) یا پوشهٔ پروژه |
| `show [-n NAME] [-i ID]` (مترادف `jobs`) | فهرست کارها یا یک کار |
| `edit [-n NAME] [-i ID] [-p PATH] [-s/--project] [-w DEP]... [-v PY] [-e/--disabled]` | تغییر یک کار |
| `delete [-n NAME] [-i ID]` | حذف یک کار |
| `run [-n NAME] [-i ID] [-s] [-t TYPE] [-m MINUTES]` | اجرای فوری، و در صورت نیاز زمان‌بندی |
| `cron [-n NAME] [-i ID] [-t TYPE] ...` (مترادف `schedule`) | زمان‌بندی یک کار |
| `crons` (مترادف `schedules`) | فهرست زمان‌بندی‌ها |
| `cancel -s SCHEDULER_ID` | لغو یک زمان‌بندی (شناسه را `crons` نشان می‌دهد) |
| `status` | تعداد کارها، زمان‌بندی‌ها و اجراهای بعدی |
| `daemon` | اجرای زمان‌بند در پیش‌زمینه |
| `install` | pem و uv را در صورت نبودن نصب می‌کند، سپس سرویس را برپا و روشن می‌کند |
| `update-uv` | به‌روزرسانی ابزار `uv` |
| `service install\|uninstall\|start\|stop\|restart\|status` | مدیریت سرویس پس‌زمینه |
| `config show\|get\|set\|reset\|path\|validate\|edit` | مدیریت تنظیمات |

دستورهای مربوط به کار، `--name` یا `--id` می‌گیرند. اگر هیچ‌کدام را ندهید، pem نام را می‌پرسد. اگر `--path` در `add` جا افتاده باشد هم می‌پرسد. برای چند وابستگی `-w` را تکرار کنید: `-w pandas -w requests`.

> ویرایش کار قبلاً `pem update` بود، اما پشت دستور به‌روزرسانی خود ابزار پنهان شده بود. اکنون `pem edit` است و `pem update` خود pem را به‌روز می‌کند.

### انواع زمان‌بندی در `cron`

| `--type` | گزینه‌ها |
|---|---|
| `once` (پیش‌فرض) | `--date 2026-01-01T10:00:00` |
| `interval` | `--seconds`، `--minutes`، `--hours`، `--days` |
| `cron` | `--cron-minute`، `--cron-hour`، `--cron-day`، `--cron-month`، `--cron-dow` |
| `until_done` | `--max-retries N`، `--retry-interval SECONDS` |

```bash
pem cron --name monitor --type interval --minutes 30
pem cron --name report  --type cron --cron-hour 9 --cron-minute 0
pem cron --name backup  --type once --date 2026-12-31T23:59:59
pem cron --name flaky   --type until_done --max-retries 5 --retry-interval 300
pem crons
pem cancel --scheduler-id pem_job_interval_1_20261201_120000
```

## تنظیمات و فایل‌ها

- تنظیمات: `pem config show` و `pem config set KEY VALUE` (مقدارهایی مثل `true`، `5`، `a,b` و `none` به نوع درست تبدیل می‌شوند) و `pem config path`. `pem config reset` تأیید می‌گیرد؛ در اسکریپت از `--yes` استفاده کنید.
- پایگاه‌داده: SQLite (`pem.db`). جدول‌ها در اولین استفاده ساخته می‌شوند.
- لاگ: برای هر اجرا یک فایل در پوشهٔ لاگ سیستم‌عامل، با چرخش بر اساس اندازه.

## دستورهای مشترک

این ابزار روی [cfuicli](https://github.com/arian24b/cfui) ساخته شده و ظاهر و رفتارش با بقیهٔ ابزارهای این مجموعه یکی است.

```bash
pem help [command]     # راهنما؛ -h روی هر دستور کار می‌کند
pem version            # نسخه و مخزن گیت (همچنین: -v)
pem update [--check]   # به‌روزرسانی خود ابزار؛ --check فقط نسخه‌ها را مقایسه می‌کند
pem -q ...             # حالت آرام: بدون بنر و یادداشت (یا PEM_QUIET=1)
```

- اگر گزینهٔ اجباری جا افتاده باشد و ابزار را در ترمینال اجرا کرده باشید، مقدارش را می‌پرسد. در pipe یا CI با پیام `--flag is required. Pass --flag <value> or run interactively.` متوقف می‌شود (کد خروج ۲).
- خطاها در یک کادر قرمز روی stderr و با کد خروج غیرصفر نمایش داده می‌شوند. با Ctrl-C کد خروج ۱۳۰ است.
- رنگ فقط در ترمینال استفاده می‌شود. با `NO_COLOR=1` خاموش می‌شود.
- `pem update` خود pem را به‌روز می‌کند و `pem update-uv` ابزار uv را.

## توسعه

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv build
```

پیام کامیت‌ها از Conventional Commits پیروی می‌کنند. میان‌برها در `Makefile` و ساخت release و باینری در `scripts/` است.

## مجوز

MIT
