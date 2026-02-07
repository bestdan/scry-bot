# scry-bot

D&D Beyond character data scraper and query tools. Download character sheets from your campaigns and query them without loading 500KB+ JSON files into memory.

## Setup

```bash
pip install requests
```

### Authentication

Get your `CobaltSession` cookie from D&D Beyond:

1. Log in to [dndbeyond.com](https://dndbeyond.com)
2. Open browser DevTools (F12)
3. Go to Application > Cookies > dndbeyond.com
4. Copy the `CobaltSession` value
5. Set the environment variable:

```bash
export DNDBEYOND_SESSION='your_session_cookie_here'
```

Add to your shell profile (`~/.zshrc` or `~/.bashrc`) to persist.

## Scripts

### Character Scraper

Download character data from D&D Beyond campaigns.

```bash
# List your campaigns
python3 scripts/character_scraper.py campaigns

# Download all characters from a campaign
python3 scripts/character_scraper.py campaign <campaign_id> [output_dir]

# Examples
python3 scripts/character_scraper.py campaign 3471829 campaigns/my-campaign/characters
```

### Character Sheet Reader

Query character data without loading full JSON files.

```bash
python3 scripts/character_sheet.py [--dir DIR] <command> <character_name>
```

| Command | Description |
|---------|-------------|
| `sheet` | Full character sheet with all stats |
| `overview` | Brief stats overview (HP, AC, abilities) |
| `spells` | List all spells by level |
| `features` | Class/race features and feats |
| `inventory` | Equipment and currency |
| `summary` | One-line summary |
| `list` | List all available characters |

```bash
# Examples
python3 scripts/character_sheet.py overview Trigger
python3 scripts/character_sheet.py --dir campaigns/bkb-primary/characters spells Eldrin
python3 scripts/character_sheet.py list
```

## Project Structure

```
scry-bot/
├── scripts/
│   ├── character_scraper.py    # D&D Beyond API scraper
│   └── character_sheet.py      # Character data query tool
├── characters/                  # Default character storage
├── campaigns/
│   └── <campaign-name>/
│       ├── characters/          # Campaign character JSON files
│       └── party-overview.md    # Party summary
└── .claude/
    └── commands/
        └── character.md         # Claude Code skill for queries
```

## Claude Code Integration

The `/character` skill lets Claude query character data efficiently:

```
/character overview Trigger
/character spells Eldrin
```

This uses the Python scripts rather than loading raw JSON into context.
