#!/usr/bin/env python3
"""
D&D Character Sheet Reader
Reads character data from JSON files and displays formatted character sheets.
"""

import json
import glob
import sys
from pathlib import Path


STAT_NAMES = {1: 'STR', 2: 'DEX', 3: 'CON', 4: 'INT', 5: 'WIS', 6: 'CHA'}
STAT_ID_MAP = {
    'strength-score': 1, 'dexterity-score': 2, 'constitution-score': 3,
    'intelligence-score': 4, 'wisdom-score': 5, 'charisma-score': 6
}
SAVE_MAP = {
    'strength-saving-throws': 'STR', 'dexterity-saving-throws': 'DEX',
    'constitution-saving-throws': 'CON', 'intelligence-saving-throws': 'INT',
    'wisdom-saving-throws': 'WIS', 'charisma-saving-throws': 'CHA'
}
SKILLS = {
    'acrobatics': 'DEX', 'animal-handling': 'WIS', 'arcana': 'INT',
    'athletics': 'STR', 'deception': 'CHA', 'history': 'INT',
    'insight': 'WIS', 'intimidation': 'CHA', 'investigation': 'INT',
    'medicine': 'WIS', 'nature': 'INT', 'perception': 'WIS',
    'performance': 'CHA', 'persuasion': 'CHA', 'religion': 'INT',
    'sleight-of-hand': 'DEX', 'stealth': 'DEX', 'survival': 'WIS'
}
SPELLCASTING_ABILITIES = {
    'Wizard': 'INT', 'Artificer': 'INT',
    'Cleric': 'WIS', 'Druid': 'WIS', 'Ranger': 'WIS',
    'Bard': 'CHA', 'Paladin': 'CHA', 'Sorcerer': 'CHA', 'Warlock': 'CHA'
}


class CharacterSheet:
    def __init__(self, data: dict):
        self.data = data
        self._calculate_all()

    def _calculate_all(self):
        """Calculate all derived statistics."""
        self._calculate_ability_scores()
        self._calculate_proficiency_bonus()
        self._calculate_saving_throws()
        self._calculate_skills()
        self._calculate_combat_stats()
        self._calculate_spellcasting()

    def _calculate_ability_scores(self):
        """Calculate final ability scores with all bonuses."""
        base_stats = {s['id']: s['value'] for s in self.data.get('stats', [])}
        stat_bonuses = {i: 0 for i in range(1, 7)}

        for category, mods in self.data.get('modifiers', {}).items():
            for mod in mods:
                subtype = mod.get('subType', '')
                if subtype in STAT_ID_MAP and mod.get('type') == 'bonus':
                    stat_bonuses[STAT_ID_MAP[subtype]] += mod.get('value', 0) or 0

        self.abilities = {}
        for stat_id in range(1, 7):
            base = base_stats.get(stat_id, 10)
            bonus = stat_bonuses.get(stat_id, 0)
            total = base + bonus
            modifier = (total - 10) // 2
            self.abilities[STAT_NAMES[stat_id]] = {
                'base': base,
                'bonus': bonus,
                'total': total,
                'mod': modifier
            }

    def _calculate_proficiency_bonus(self):
        """Calculate proficiency bonus from total level."""
        self.total_level = sum(c.get('level', 0) for c in self.data.get('classes', []))
        self.proficiency_bonus = 2 + (self.total_level - 1) // 4

    def _calculate_saving_throws(self):
        """Calculate saving throw bonuses."""
        proficient = set()
        for category, mods in self.data.get('modifiers', {}).items():
            for mod in mods:
                subtype = mod.get('subType', '')
                if subtype in SAVE_MAP and mod.get('type') == 'proficiency':
                    proficient.add(SAVE_MAP[subtype])

        self.saves = {}
        for stat in STAT_NAMES.values():
            val = self.abilities[stat]['mod']
            is_prof = stat in proficient
            if is_prof:
                val += self.proficiency_bonus
            self.saves[stat] = {'value': val, 'proficient': is_prof}

    def _calculate_skills(self):
        """Calculate skill bonuses with proficiency."""
        skill_profs = {skill: 0 for skill in SKILLS}

        for category, mods in self.data.get('modifiers', {}).items():
            for mod in mods:
                subtype = mod.get('subType', '')
                mod_type = mod.get('type', '')
                if subtype in skill_profs:
                    if mod_type == 'proficiency':
                        skill_profs[subtype] = max(skill_profs[subtype], 1)
                    elif mod_type == 'expertise':
                        skill_profs[subtype] = 2
                    elif mod_type == 'half-proficiency':
                        skill_profs[subtype] = max(skill_profs[subtype], 0.5)

        self.skills = {}
        for skill, ability in SKILLS.items():
            base_mod = self.abilities[ability]['mod']
            prof_level = skill_profs[skill]
            if prof_level >= 1:
                bonus = base_mod + int(self.proficiency_bonus * prof_level)
            elif prof_level == 0.5:
                bonus = base_mod + self.proficiency_bonus // 2
            else:
                bonus = base_mod
            self.skills[skill] = {
                'ability': ability,
                'value': bonus,
                'proficiency': prof_level
            }

    def _calculate_combat_stats(self):
        """Calculate combat-related statistics."""
        # HP
        base_hp = self.data.get('baseHitPoints', 0)
        bonus_hp = self.data.get('bonusHitPoints', 0) or 0
        con_hp = self.abilities['CON']['mod'] * self.total_level
        self.max_hp = base_hp + bonus_hp + con_hp
        self.current_hp = self.max_hp - (self.data.get('removedHitPoints', 0) or 0)

        # AC - calculate from armor, shield, DEX, and bonuses
        self.ac = self._calculate_ac()

        # Speed
        try:
            self.speed = self.data.get('race', {}).get('weightSpeeds', {}).get('normal', {}).get('walk', 30)
        except:
            self.speed = 30

        # Initiative
        self.initiative = self.abilities['DEX']['mod']

    def _calculate_ac(self) -> int:
        """Calculate Armor Class from equipment and modifiers."""
        base_ac = 10
        dex_mod = self.abilities['DEX']['mod']
        dex_cap = None  # Max DEX bonus from armor
        shield_bonus = 0
        other_bonuses = 0

        # Check equipped items for armor and shield
        for item in self.data.get('inventory', []):
            if not item.get('equipped'):
                continue

            item_def = item.get('definition', {})
            armor_type_id = item_def.get('armorTypeId')
            item_ac = item_def.get('armorClass', 0)

            if armor_type_id == 4:  # Shield
                shield_bonus = item_ac
                # Add magic bonuses from shield
                for mod in item_def.get('grantedModifiers', []):
                    if mod.get('subType') == 'armor-class' and mod.get('type') == 'bonus':
                        shield_bonus += mod.get('value', 0) or mod.get('fixedValue', 0) or 0
            elif armor_type_id in [1, 2, 3]:  # Light, Medium, Heavy armor
                base_ac = item_ac
                # Set DEX cap based on armor type
                if armor_type_id == 2:  # Medium armor - max +2 DEX
                    dex_cap = 2
                elif armor_type_id == 3:  # Heavy armor - no DEX
                    dex_cap = 0
                # Light armor (1) has no cap

                # Add magic bonuses from armor
                for mod in item_def.get('grantedModifiers', []):
                    if mod.get('subType') == 'armor-class' and mod.get('type') == 'bonus':
                        other_bonuses += mod.get('value', 0) or mod.get('fixedValue', 0) or 0

        # Apply DEX cap
        effective_dex = dex_mod if dex_cap is None else min(dex_mod, dex_cap)

        # Check for other AC bonuses from modifiers (feats, class features, etc.)
        for category, mods in self.data.get('modifiers', {}).items():
            if category == 'item':  # Already handled above
                continue
            for mod in mods:
                if mod.get('subType') == 'armor-class' and mod.get('type') == 'bonus':
                    other_bonuses += mod.get('value', 0) or 0

        return base_ac + effective_dex + shield_bonus + other_bonuses

    def _calculate_spellcasting(self):
        """Calculate spellcasting stats if applicable."""
        self.spell_ability = None
        for c in self.data.get('classes', []):
            class_name = c.get('definition', {}).get('name', '')
            if class_name in SPELLCASTING_ABILITIES:
                self.spell_ability = SPELLCASTING_ABILITIES[class_name]
                break

        if self.spell_ability:
            spell_mod = self.abilities[self.spell_ability]['mod']
            self.spell_attack = spell_mod + self.proficiency_bonus
            self.spell_dc = 8 + spell_mod + self.proficiency_bonus
        else:
            self.spell_attack = None
            self.spell_dc = None

    def display(self):
        """Display formatted character sheet."""
        name = self.data.get('name', 'Unknown')
        race = self.data.get('race', {}).get('fullName', 'Unknown')
        classes = ', '.join([
            f"{c['definition']['name']} {c['level']}"
            for c in self.data.get('classes', [])
        ])

        print("═" * 55)
        print(f"  {name.upper()}")
        print(f"  {race} | {classes}")
        print("═" * 55)

        # Ability Scores
        print("\nABILITY SCORES")
        print("─" * 55)
        stats_line = "  "
        scores_line = "  "
        mods_line = "  "
        for stat in ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA']:
            stats_line += f"{stat:^7} "
            scores_line += f"{self.abilities[stat]['total']:^7} "
            mods_line += f"({self.abilities[stat]['mod']:+d})".center(7) + " "
        print(stats_line)
        print(scores_line)
        print(mods_line)

        # Combat
        print("\nCOMBAT")
        print("─" * 55)
        print(f"  AC: {self.ac}    HP: {self.current_hp}/{self.max_hp}    Speed: {self.speed} ft")
        print(f"  Initiative: {self.initiative:+d}    Proficiency Bonus: +{self.proficiency_bonus}")

        # Saving Throws
        print("\nSAVING THROWS")
        print("─" * 55)
        saves = []
        for stat in ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA']:
            val = self.saves[stat]['value']
            marker = '*' if self.saves[stat]['proficient'] else ''
            saves.append(f"{stat}: {val:+d}{marker}")
        print(f"  {saves[0]:12} {saves[1]:12} {saves[2]:12}")
        print(f"  {saves[3]:12} {saves[4]:12} {saves[5]:12}")
        print("  (* = proficient)")

        # Skills
        print("\nSKILLS")
        print("─" * 55)
        skill_display = []
        for skill in sorted(self.skills.keys()):
            info = self.skills[skill]
            val = info['value']
            if info['proficiency'] >= 2:
                marker = '**'
            elif info['proficiency'] >= 1:
                marker = '*'
            elif info['proficiency'] == 0.5:
                marker = '½'
            else:
                marker = ''
            display_name = skill.replace('-', ' ').title()
            skill_display.append(f"{display_name}: {val:+d}{marker}")

        mid = (len(skill_display) + 1) // 2
        for i in range(mid):
            left = skill_display[i] if i < len(skill_display) else ''
            right = skill_display[i + mid] if i + mid < len(skill_display) else ''
            print(f"  {left:26} {right}")
        print("  (* = proficient, ** = expertise)")

        # Spellcasting
        if self.spell_ability:
            spell_mod = self.abilities[self.spell_ability]['mod']
            print("\nSPELLCASTING")
            print("─" * 55)
            print(f"  Spellcasting Ability: {self.spell_ability} ({spell_mod:+d})")
            print(f"  Spell Attack: +{self.spell_attack}")
            print(f"  Spell Save DC: {self.spell_dc}")

        print("\n" + "═" * 55)


def find_character(name_query: str, campaigns_dir: str = "campaigns") -> str | None:
    """Find a character file by partial name match across all campaigns."""
    # Search all campaign subdirectories
    pattern = str(Path(campaigns_dir) / "**" / "*.json")
    files = glob.glob(pattern, recursive=True)
    # Exclude combined campaign files
    files = [f for f in files if 'campaign_' not in Path(f).name]

    matches = [f for f in files if name_query.lower() in f.lower()]

    if not matches:
        print(f"No character found matching '{name_query}'")
        print("\nAvailable characters:")
        for f in sorted(files):
            print(f"  - {Path(f).stem}")
        return None

    if len(matches) > 1:
        print(f"Multiple matches for '{name_query}':")
        for f in matches:
            print(f"  - {Path(f).stem}")
        return None

    return matches[0]


def show_overview(data: dict):
    """Show a brief overview of the character."""
    sheet = CharacterSheet(data)
    name = data.get('name', 'Unknown')
    race = data.get('race', {}).get('fullName', 'Unknown')
    classes = ', '.join([
        f"{c['definition']['name']} {c['level']}"
        for c in data.get('classes', [])
    ])

    print(f"{name} - {race} {classes}")
    print(f"Level {sheet.total_level} | HP: {sheet.current_hp}/{sheet.max_hp} | AC: {sheet.ac}")
    print()
    print("Abilities:", end=" ")
    for stat in ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA']:
        print(f"{stat} {sheet.abilities[stat]['total']}({sheet.abilities[stat]['mod']:+d})", end="  ")
    print()

    if sheet.spell_ability:
        print(f"Spellcasting: {sheet.spell_ability} | Attack +{sheet.spell_attack} | DC {sheet.spell_dc}")


def show_spells(data: dict):
    """Show character's spells."""
    sheet = CharacterSheet(data)
    name = data.get('name', 'Unknown')

    # Get spells from classSpells
    all_spells = []
    for class_spells in data.get('classSpells', []):
        for spell in class_spells.get('spells', []):
            spell_def = spell.get('definition', {})
            all_spells.append({
                'name': spell_def.get('name', 'Unknown'),
                'level': spell_def.get('level', 0),
                'school': spell_def.get('school', 'Unknown'),
                'prepared': spell.get('prepared', False),
                'alwaysPrepared': spell.get('alwaysPrepared', False),
            })

    # Also check spells array
    for spell in data.get('spells', {}).get('class', []):
        spell_def = spell.get('definition', {})
        all_spells.append({
            'name': spell_def.get('name', 'Unknown'),
            'level': spell_def.get('level', 0),
            'school': spell_def.get('school', 'Unknown'),
            'prepared': spell.get('prepared', False),
            'alwaysPrepared': spell.get('alwaysPrepared', False),
        })

    # Dedupe by name
    seen = set()
    unique_spells = []
    for s in all_spells:
        if s['name'] not in seen:
            seen.add(s['name'])
            unique_spells.append(s)

    # Sort by level then name
    unique_spells.sort(key=lambda s: (s['level'], s['name']))

    print(f"{name}'s Spells")
    if sheet.spell_ability:
        print(f"Spellcasting: {sheet.spell_ability} | Attack +{sheet.spell_attack} | DC {sheet.spell_dc}")
    print()

    current_level = -1
    for spell in unique_spells:
        if spell['level'] != current_level:
            current_level = spell['level']
            level_name = "Cantrips" if current_level == 0 else f"Level {current_level}"
            print(f"\n{level_name}:")

        markers = []
        if spell['alwaysPrepared']:
            markers.append('always')
        elif spell['prepared']:
            markers.append('prepared')
        marker_str = f" ({', '.join(markers)})" if markers else ""
        print(f"  - {spell['name']}{marker_str}")


def show_features(data: dict):
    """Show character's class and race features."""
    name = data.get('name', 'Unknown')
    print(f"{name}'s Features\n")

    # Race features
    race_mods = data.get('modifiers', {}).get('race', [])
    race_features = set()
    for mod in race_mods:
        if mod.get('friendlyTypeName'):
            race_features.add(mod.get('friendlyTypeName'))

    if race_features:
        print("Race Features:")
        for feat in sorted(race_features):
            print(f"  - {feat}")
        print()

    # Class features
    for cls in data.get('classes', []):
        class_name = cls.get('definition', {}).get('name', 'Unknown')
        level = cls.get('level', 0)
        subclass = cls.get('subclassDefinition', {})
        subclass_name = subclass.get('name', '') if subclass else ''

        print(f"{class_name} {level}" + (f" ({subclass_name})" if subclass_name else "") + ":")

        # Get class features
        class_features = set()
        for mod in data.get('modifiers', {}).get('class', []):
            if mod.get('friendlyTypeName'):
                class_features.add(mod.get('friendlyTypeName'))

        for feat in sorted(class_features):
            print(f"  - {feat}")
        print()

    # Feats
    feat_mods = data.get('modifiers', {}).get('feat', [])
    feats = set()
    for mod in feat_mods:
        if mod.get('friendlyTypeName'):
            feats.add(mod.get('friendlyTypeName'))

    if feats:
        print("Feats:")
        for feat in sorted(feats):
            print(f"  - {feat}")


def show_inventory(data: dict):
    """Show character's inventory."""
    name = data.get('name', 'Unknown')
    print(f"{name}'s Inventory\n")

    inventory = data.get('inventory', [])

    # Categorize items
    equipped = []
    carried = []

    for item in inventory:
        item_def = item.get('definition', {})
        item_name = item_def.get('name', 'Unknown')
        quantity = item.get('quantity', 1)
        is_equipped = item.get('equipped', False)

        entry = f"{item_name}" + (f" (x{quantity})" if quantity > 1 else "")

        if is_equipped:
            equipped.append(entry)
        else:
            carried.append(entry)

    if equipped:
        print("Equipped:")
        for item in sorted(equipped):
            print(f"  - {item}")
        print()

    if carried:
        print("Carried:")
        for item in sorted(carried):
            print(f"  - {item}")

    # Currency
    currencies = data.get('currencies', {})
    currency_str = []
    for curr in ['pp', 'gp', 'ep', 'sp', 'cp']:
        val = currencies.get(curr, 0)
        if val > 0:
            currency_str.append(f"{val} {curr}")

    if currency_str:
        print(f"\nCurrency: {', '.join(currency_str)}")


def show_summary(data: dict):
    """Show one-line summary."""
    sheet = CharacterSheet(data)
    name = data.get('name', 'Unknown')
    race = data.get('race', {}).get('baseName', 'Unknown')
    classes = '/'.join([c['definition']['name'] for c in data.get('classes', [])])
    print(f"{name}: Level {sheet.total_level} {race} {classes} | HP {sheet.current_hp}/{sheet.max_hp} | AC {sheet.ac}")


def list_characters(campaigns_dir: str = "campaigns"):
    """List all available characters across all campaigns."""
    pattern = str(Path(campaigns_dir) / "**" / "*.json")
    files = glob.glob(pattern, recursive=True)
    files = [f for f in files if 'campaign_' not in Path(f).name]

    print("Available characters:\n")
    for f in sorted(files):
        with open(f) as fp:
            data = json.load(fp)
        show_summary(data)


COMMANDS = {
    'sheet': lambda d: CharacterSheet(d).display(),
    'overview': show_overview,
    'spells': show_spells,
    'features': show_features,
    'inventory': show_inventory,
    'summary': show_summary,
}


def main():
    # Parse --dir option
    args = sys.argv[1:]
    campaigns_dir = "campaigns"

    if '--dir' in args:
        idx = args.index('--dir')
        if idx + 1 < len(args):
            campaigns_dir = args[idx + 1]
            args = args[:idx] + args[idx + 2:]
        else:
            args = args[:idx]

    if len(args) < 1:
        print("Usage: python3 character_sheet.py [--dir DIR] <command> <character_name>")
        print("       python3 character_sheet.py [--dir DIR] <character_name>  (defaults to 'sheet')")
        print("\nCommands:")
        print("  sheet     - Full character sheet with all stats")
        print("  overview  - Brief overview (stats, HP, AC, spellcasting)")
        print("  spells    - List all spells")
        print("  features  - List class/race features and feats")
        print("  inventory - List equipment and currency")
        print("  summary   - One-line summary")
        print("  list      - List all available characters")
        print()
        list_characters(campaigns_dir)
        return

    # Check if first arg is a command
    if args[0] == 'list':
        list_characters(campaigns_dir)
        return

    if args[0] in COMMANDS:
        command = args[0]
        if len(args) < 2:
            print(f"Usage: python3 character_sheet.py {command} <character_name>")
            return
        name_query = " ".join(args[1:])
    else:
        command = 'sheet'
        name_query = " ".join(args)

    filepath = find_character(name_query, campaigns_dir)

    if filepath:
        with open(filepath) as f:
            data = json.load(f)
        COMMANDS[command](data)


if __name__ == "__main__":
    main()
