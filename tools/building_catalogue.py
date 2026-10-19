"""Read clan building candidates from Northgard's resource archive offline."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from .list_pak import read_pak_file
except ImportError:  # The file can also run directly as a small CLI tool.
    from list_pak import read_pak_file


DATABASE_PATH = "data.cdb"
ORDINARY_BUILD_CATEGORIES = {1, 2, 3}


def _clan_ids(entries) -> set[str]:
    return {
        entry["clan"]
        for entry in entries or []
        if isinstance(entry, dict) and isinstance(entry.get("clan"), str)
    }


def _sheet(database: dict, name: str) -> dict:
    for sheet in database["sheets"]:
        if sheet.get("name") == name:
            return sheet
    raise ValueError(f"Missing CDB sheet: {name}")


def read_building_candidates(
    archive: Path,
    clans: set[str] | None = None,
    *,
    include_special: bool = False,
) -> dict:
    """Return build-menu candidate IDs, grouped by their allowed clans.

    This is a catalogue source only. It deliberately does not answer whether a
    building is legal in a particular live zone.
    """
    database_bytes = read_pak_file(archive, DATABASE_PATH)
    database = json.loads(database_bytes)
    buildings = _sheet(database, "building")["lines"]
    clan_records = {
        line["id"]: line
        for line in _sheet(database, "clan")["lines"]
        if isinstance(line.get("id"), str)
    }
    known_clans = set(clan_records)
    selected_clans = known_clans if clans is None else clans
    unknown_clans = selected_clans - known_clans
    if unknown_clans:
        raise ValueError(f"Unknown clan IDs: {sorted(unknown_clans)}")

    categories = None if include_special else ORDINARY_BUILD_CATEGORIES
    candidates = {clan: [] for clan in sorted(selected_clans)}
    for building in buildings:
        identifier = building.get("id")
        ui = building.get("ui")
        if (
            not isinstance(identifier, str)
            or not isinstance(ui, dict)
            or ui.get("buildCategory") is None
            or (categories is not None and ui["buildCategory"] not in categories)
        ):
            continue

        props = building.get("props") or {}
        only_for = _clan_ids(props.get("onlyForClans"))
        not_for = _clan_ids(props.get("notForClans"))
        disabled_for = _clan_ids(props.get("disabledForClans"))
        for clan in candidates:
            clan_type = (clan_records[clan].get("props") or {}).get("type")
            building_type = props.get("clanType")
            if building_type is not None and building_type != clan_type:
                continue
            if only_for and clan not in only_for:
                continue
            if clan in not_for or clan in disabled_for:
                continue
            candidates[clan].append({
                "id": identifier,
                "name": (building.get("texts") or {}).get("name"),
                "build_category": ui.get("buildCategory"),
                "build_position": ui.get("buildPosition"),
                "clan_type": building_type,
                "only_for_clans": sorted(only_for),
                "not_for_clans": sorted(not_for),
                "disabled_for_clans": sorted(disabled_for),
            })

    for entries in candidates.values():
        entries.sort(key=lambda entry: entry["id"])

    return {
        "source": DATABASE_PATH,
        "source_sha256": hashlib.sha256(database_bytes).hexdigest(),
        "clans": candidates,
        "limits": [
            "The default includes only ordinary build-tab categories 1, 2 and 3.",
            "It applies the database's clan type and declared clan exclusions.",
            "Does not apply terrain, prerequisites, resources, slots, game mode, or placement checks.",
            "It is a review list, not a reproduction of getAvailableBuildings().",
            "Review and author the policy vocabulary from this output.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--clan", action="append", help="CDB clan ID; repeat for more clans")
    parser.add_argument(
        "--include-special",
        action="store_true",
        help="Include relic, wonder and Bifrost categories as review candidates.",
    )
    args = parser.parse_args()

    clans = set(args.clan) if args.clan else None
    print(json.dumps(
        read_building_candidates(args.archive, clans, include_special=args.include_special),
        indent=2,
    ))


if __name__ == "__main__":
    main()
