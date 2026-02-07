#!/usr/bin/env python3
"""
D&D Beyond Character Scraper
Extracts all character data from your D&D Beyond account.
"""

import requests
import json
import re
from pathlib import Path
from typing import Dict, List, Any


STAT_NAMES = {
    1: "Strength",
    2: "Dexterity",
    3: "Constitution",
    4: "Intelligence",
    5: "Wisdom",
    6: "Charisma",
}


class DndBeyondScraper:
    def __init__(self, cobalt_session: str):
        """
        Initialize scraper with session cookie.

        Args:
            cobalt_session: Your CobaltSession cookie value from dndbeyond.com
        """
        self.session = requests.Session()
        self.session.cookies.set(
            "CobaltSession", cobalt_session, domain=".dndbeyond.com"
        )
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json",
            }
        )
        self.base_url = "https://www.dndbeyond.com"
        self.character_service_url = "https://character-service.dndbeyond.com"
        self._cobalt_token = None

    def _get_cobalt_token(self) -> str:
        """Get or refresh the cobalt token for API authentication."""
        if self._cobalt_token is None:
            response = self.session.post(
                "https://auth-service.dndbeyond.com/v1/cobalt-token"
            )
            response.raise_for_status()
            self._cobalt_token = response.json().get("token")
        return self._cobalt_token

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get headers with Bearer token for API calls."""
        return {"Authorization": f"Bearer {self._get_cobalt_token()}"}

    def get_character_list(self) -> List[Dict[str, Any]]:
        """Get list of all characters from all campaigns."""
        characters = []
        seen_ids = set()

        # Get characters from all campaigns
        campaigns = self.get_campaign_list()
        for campaign in campaigns:
            try:
                campaign_chars = self.get_campaign_characters(campaign["id"])
                for char in campaign_chars:
                    if char["id"] not in seen_ids:
                        seen_ids.add(char["id"])
                        characters.append(char)
            except Exception as e:
                print(f"  Warning: Could not get characters from campaign {campaign['name']}: {e}")

        return characters

    def _enrich_stat_names(self, char_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fill in stat names based on stat IDs."""
        for stat in char_data.get("stats", []):
            if stat.get("id") in STAT_NAMES:
                stat["name"] = STAT_NAMES[stat["id"]]

        for stat in char_data.get("bonusStats", []):
            if stat.get("id") in STAT_NAMES:
                stat["name"] = STAT_NAMES[stat["id"]]

        return char_data

    def get_character_data(self, character_id: int) -> Dict[str, Any]:
        """Get full character sheet data via the character service API."""
        url = f"{self.character_service_url}/character/v5/character/{character_id}"
        response = self.session.get(url, headers=self._get_auth_headers())
        response.raise_for_status()

        data = response.json()
        if not data.get("success"):
            raise ValueError(f"API error for character {character_id}: {data.get('message')}")

        char_data = data.get("data", {})
        return self._enrich_stat_names(char_data)

    def get_campaign_list(self) -> List[Dict[str, Any]]:
        """Get list of all campaigns via the API."""
        url = f"{self.base_url}/api/campaign/stt/active-campaigns"
        response = self.session.get(url, headers=self._get_auth_headers())
        response.raise_for_status()

        data = response.json()
        if data.get("status") != "success":
            raise ValueError(f"API error getting campaigns: {data}")

        campaigns = data.get("data", [])
        return [
            {
                "id": camp.get("id"),
                "name": camp.get("name"),
                "dm": camp.get("dmUsername"),
                "url": f"{self.base_url}/campaigns/{camp.get('id')}",
            }
            for camp in campaigns
            if camp.get("id")
        ]

    def get_campaign_characters(self, campaign_id: int) -> List[Dict[str, Any]]:
        """Get all characters in a campaign (including other players' characters)."""
        url = f"{self.base_url}/campaigns/{campaign_id}"
        response = self.session.get(url)
        response.raise_for_status()

        html = response.text
        characters = []

        # Find all character IDs from any /characters/{id} pattern
        char_ids = list(set(re.findall(r'/characters/(\d+)', html)))

        for char_id in char_ids:
            # Try to find character info in the HTML
            # Look for character card patterns
            name = "Unknown"
            player = "Unknown"

            # Find the character section - look backwards from the character ID
            idx = html.find(f"/characters/{char_id}")
            if idx > 0:
                # Get context around the ID (look back further to find the card start)
                start = max(0, idx - 1000)
                context = html[start:idx + 500]

                # Look for character name in character-info-primary
                name_match = re.search(
                    r'character-info-primary[^>]*>\s*([^<]+?)\s*<', context
                )
                if name_match:
                    name = name_match.group(1).strip()

                # Look for player name
                player_match = re.search(r'Player:\s*([^<]+)', context)
                if player_match:
                    player = player_match.group(1).strip()

            characters.append({
                "id": int(char_id),
                "name": name,
                "player": player,
                "url": f"{self.base_url}/characters/{char_id}",
            })

        return characters

    def scrape_campaign_characters(
        self, campaign_id: int, output_dir: str = "./characters"
    ) -> None:
        """Scrape all characters from a specific campaign."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        print(f"Fetching characters from campaign {campaign_id}...")
        characters = self.get_campaign_characters(campaign_id)
        print(f"Found {len(characters)} characters in campaign")

        all_data = []

        for char_info in characters:
            char_id = char_info["id"]
            player_name = char_info["player"]
            print(f"\nScraping character ID {char_id} (Player: {player_name})...")

            try:
                char_data = self.get_character_data(char_id)
                char_name = char_data.get("name", f"Character_{char_id}")
                char_data["_player"] = player_name  # Add player info to data
                all_data.append(char_data)

                # Save individual character file
                filename = (
                    f"{char_name.replace(' ', '_').replace('/', '_')}_{char_id}.json"
                )
                filepath = output_path / filename
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(char_data, f, indent=2, ensure_ascii=False)
                print(f"  ✓ {char_name} saved to {filepath}")

            except Exception as e:
                print(f"  ✗ Error scraping character {char_id}: {e}")

        # Save combined file
        combined_path = output_path / f"campaign_{campaign_id}_characters.json"
        with open(combined_path, "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Saved combined data to {combined_path}")
        print(f"\nTotal characters scraped: {len(all_data)}/{len(characters)}")

    def scrape_all_characters(self, output_dir: str = "./characters") -> None:
        """Scrape all characters and save to JSON files."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        print("Fetching character list...")
        characters = self.get_character_list()
        print(f"Found {len(characters)} characters")

        all_data = []

        for char_info in characters:
            char_id = char_info["id"]
            player_name = char_info.get("player", "")
            print(f"\nScraping character ID {char_id}...")

            try:
                char_data = self.get_character_data(char_id)
                char_name = char_data.get("name", f"Character_{char_id}")
                if player_name:
                    char_data["_player"] = player_name
                all_data.append(char_data)

                # Save individual character file
                filename = (
                    f"{char_name.replace(' ', '_').replace('/', '_')}_{char_id}.json"
                )
                filepath = output_path / filename
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(char_data, f, indent=2, ensure_ascii=False)
                print(f"  ✓ {char_name} saved to {filepath}")

            except Exception as e:
                print(f"  ✗ Error scraping character {char_id}: {e}")

        # Save combined file
        combined_path = output_path / "all_characters.json"
        with open(combined_path, "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Saved combined data to {combined_path}")
        print(f"\nTotal characters scraped: {len(all_data)}/{len(characters)}")


def main():
    import sys
    import os

    # Get session token from environment variable
    COBALT_SESSION = os.environ.get("DNDBEYOND_SESSION")

    if not COBALT_SESSION:
        print("ERROR: DNDBEYOND_SESSION environment variable not set")
        print("\nTo get your cookie:")
        print("1. Log in to dndbeyond.com")
        print("2. Open browser DevTools (F12)")
        print("3. Go to Application/Storage > Cookies > https://www.dndbeyond.com")
        print("4. Find 'CobaltSession' and copy its value")
        print("5. Set the environment variable:")
        print("   export DNDBEYOND_SESSION='your_session_cookie_here'")
        return

    scraper = DndBeyondScraper(COBALT_SESSION)

    # Check command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "campaigns":
            # List all campaigns
            print("Fetching your campaigns...")
            campaigns = scraper.get_campaign_list()
            print(f"\nFound {len(campaigns)} campaigns:\n")
            for camp in campaigns:
                print(f"  ID: {camp['id']}")
                print(f"  Name: {camp['name']}")
                print(f"  URL: {camp['url']}\n")
            print(
                "To scrape a campaign, run: python3 dndbeyond_scraper.py campaign <campaign_id>"
            )

        elif command == "campaign" and len(sys.argv) > 2:
            # Scrape specific campaign
            campaign_id = int(sys.argv[2])
            output_dir = sys.argv[3] if len(sys.argv) > 3 else "./characters"
            scraper.scrape_campaign_characters(campaign_id, output_dir)

        else:
            print("Usage:")
            print(
                "  python3 dndbeyond_scraper.py              - Scrape all your characters"
            )
            print(
                "  python3 dndbeyond_scraper.py campaigns    - List all your campaigns"
            )
            print(
                "  python3 dndbeyond_scraper.py campaign ID  - Scrape all characters in campaign"
            )
    else:
        # Default: scrape all your characters
        scraper.scrape_all_characters()


if __name__ == "__main__":
    main()
