# Character Sheet Reader

Read D&D character data from JSON files organized under `campaigns/`.

Characters are stored per-campaign in subdirectories (e.g. `campaigns/<campaign>/characters/`). The script searches all campaign subdirectories recursively.

## IMPORTANT: Always Use Python Scripts

**NEVER read character JSON files directly into context.** They are 300-800KB each and will slow down responses significantly.

**ALWAYS use the helper script** to extract information:

```bash
python3 scripts/character_sheet.py <command> <character_name>
```

Use `--dir <path>` to override the default `campaigns/` base directory. Use the `list` command to discover available characters and campaigns.

## Commands

| Command     | Description          | Example                                                |
| ----------- | -------------------- | ------------------------------------------------------ |
| `sheet`     | Full character sheet | `python3 scripts/character_sheet.py sheet torgana`     |
| `overview`  | Brief stats overview | `python3 scripts/character_sheet.py overview torgana`  |
| `spells`    | List all spells      | `python3 scripts/character_sheet.py spells torgana`    |
| `features`  | Class/race features  | `python3 scripts/character_sheet.py features torgana`  |
| `inventory` | Equipment & currency | `python3 scripts/character_sheet.py inventory torgana` |
| `summary`   | One-line summary     | `python3 scripts/character_sheet.py summary torgana`   |
| `list`      | List all characters  | `python3 scripts/character_sheet.py list`              |

## Usage Examples

**User asks: "Give me an overview of Torgana"**
```bash
python3 scripts/character_sheet.py overview torgana
```

**User asks: "What spells does Trigger have?"**
```bash
python3 scripts/character_sheet.py spells trigger
```

**User asks: "Show me Imsaho's full character sheet"**
```bash
python3 scripts/character_sheet.py sheet imsaho
```

**User asks: "What's in Ash's inventory?"**
```bash
python3 scripts/character_sheet.py inventory ash
```

**User asks: "List all characters"**
```bash
python3 scripts/character_sheet.py list
```

## Argument

$ARGUMENTS - The character name (partial match supported) and optionally a command
