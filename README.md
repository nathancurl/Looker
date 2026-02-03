# Job Notification Discord Bot

A job alert system that continuously polls career sites and sends notifications to Discord webhooks when new relevant jobs are posted.

## Features

- **Multi-source polling**: Scrapes 100+ companies across MAANG, YC startups, and major ATS platforms
- **Smart filtering**: Keyword matching for entry-level software engineering roles
- **Deduplication**: SQLite-backed state to avoid repeat notifications
- **Webhook routing**: Different Discord channels for different job sources
- **Resilient**: Graceful error handling, automatic retries

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                               │
│                    (Polling Loop)                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Fetchers                                │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ Google  │ │ Amazon  │ │ Netflix │ │  Apple  │  ...      │
│  │  (XML)  │ │ (JSON)  │ │(Eightfold)│ │ (HTML)  │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │  Meta   │ │   YC    │ │Wellfound│ │Greenhouse│  ...      │
│  │(GraphQL)│ │(HN Jobs)│ │(Selenium)│ │  (API)  │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Filtering                                │
│         (Keywords, Exclude patterns, Level gate)            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   State Store                                │
│              (SQLite deduplication)                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                Discord Notifier                              │
│         (Webhook POST with rich embeds)                      │
└─────────────────────────────────────────────────────────────┘
```

## Supported Sources

### MAANG (Custom Career Portals)
| Company | Method | Jobs |
|---------|--------|------|
| Google | XML feed | ~4,500 |
| Amazon | JSON API | 10,000+ |
| Microsoft | JSON API | (when available) |
| Netflix | Eightfold API | 600+ |
| Apple | HTML scraping | ~4,500 |
| Meta | GraphQL | 1,000+ |

### Startup Boards
| Source | Method |
|--------|--------|
| YC Jobs | HN page scraping |
| Wellfound | Selenium (headless Chrome) |
| HN Who is Hiring | RSS feed |

### ATS Platforms (100+ companies)
| Platform | Companies |
|----------|-----------|
| Greenhouse | 54 |
| Ashby | 29 |
| Workday | 19 |
| Workable | 7 |
| Lever | 5 |
| Jobvite, iCIMS, Taleo | Various |

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/YOUR_USERNAME/job-notification-discord.git
cd job-notification-discord

# Install Poetry (if not installed)
pip install poetry

# Install dependencies
poetry install
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your Discord webhook URLs:

```env
DISCORD_WEBHOOK_MAANG=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_YC=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_HN=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_GREENHOUSE=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_LEVER=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_ASHBY=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_WORKABLE=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_WORKDAY=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_WELLFOUND=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_JOBVITE=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_ICIMS=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_TALEO=https://discord.com/api/webhooks/...
```

### 3. Run

```bash
# Normal mode
poetry run python main.py

# Dry run (no Discord posts)
DRY_RUN=true poetry run python main.py
```

## Configuration

### config.json

```json
{
  "poll_interval_seconds": 600,
  "filtering": {
    "include_keywords": ["software engineer", "backend", "frontend", ...],
    "exclude_keywords": ["senior", "staff", "principal", "manager", ...],
    "level_gate": {
      "enabled": true,
      "allowed_levels": ["entry", "junior", "new grad", "associate"]
    }
  },
  "routing": {
    "maang": "DISCORD_WEBHOOK_MAANG",
    "yc": "DISCORD_WEBHOOK_YC",
    ...
  },
  "sources": {
    "google": { "name": "Google", ... },
    "greenhouse": [ { "name": "Stripe", "company_id": "stripe" }, ... ],
    ...
  }
}
```

### Adding New Companies

**For ATS-based companies** (Greenhouse, Lever, etc.), add to the appropriate array in `config.json`:

```json
"greenhouse": [
  { "name": "New Company", "company_id": "new-company-slug" }
]
```

Find the company_id from their careers URL:
- Greenhouse: `boards.greenhouse.io/{company_id}`
- Lever: `jobs.lever.co/{company_id}`
- Ashby: `jobs.ashbyhq.com/{company_id}`

## Deployment

### Google Cloud (Free Tier)

```bash
# On your GCP VM
sudo apt update && sudo apt install -y python3-pip git chromium-browser
git clone https://github.com/YOUR_USERNAME/job-notification-discord.git
cd job-notification-discord
pip3 install poetry
poetry install
cp .env.example .env && nano .env  # Add webhooks

# Run in background
nohup poetry run python main.py > output.log 2>&1 &

# View logs
tail -f output.log
```

### Docker

```bash
docker build -t job-alerts .
docker run -d --env-file .env --name job-alerts job-alerts
```

### Systemd Service (Production)

Create `/etc/systemd/system/job-alerts.service`:

```ini
[Unit]
Description=Job Notification Discord Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/job-notification-discord
ExecStart=/home/ubuntu/.local/bin/poetry run python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable job-alerts
sudo systemctl start job-alerts
```

## Development

### Run Tests

```bash
poetry run pytest tests/ -v
```

### Validate Sources

```bash
# Test MAANG endpoints
poetry run python scripts/validate_maang.py

# Test all configured sources
poetry run python scripts/validate_sources.py
```

## Maintenance Notice

> **This project requires ongoing maintenance.** Many fetchers rely on web scraping, unofficial APIs, or browser automation which are inherently fragile. Sources like Apple (HTML scraping), Wellfound (Selenium), and Meta (GraphQL) may break when websites update their structure. Expect to periodically fix broken fetchers.

## How It Works

1. **Polling Loop**: `main.py` runs continuously, checking each source at its configured interval

2. **Fetching**: Each fetcher scrapes its source (API, HTML, RSS, GraphQL, or Selenium)

3. **Filtering**: Jobs are filtered by:
   - Include keywords (must match title, company, or description)
   - Exclude keywords (blocked if match)
   - Level gate (optional, filters for entry-level)

4. **Deduplication**: Each job gets a unique ID (UID). Seen UIDs are stored in SQLite.

5. **Notification**: New jobs that pass filtering are posted to Discord via webhooks

6. **Resilience**: Failed fetches return empty lists (no crash). Failed notifications retry next cycle.

## License

MIT
