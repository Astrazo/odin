"""Discovered Northgard zones arranged as a graph for a GNN."""

import hashlib
import json
import math
from pathlib import Path


ZONE_FEATURE_SCHEMA_PATH = Path(__file__).parents[1] / "data" / "zone_feature_schema.json"


BASE_FEATURE_NAMES = [
    "owned",
    "neutral",
    "allied_owned",
    "enemy_owned",
    "is_guarded",
    "building_slots_used",
    "building_slots_max",
    "is_coastal",
    "has_fish",
    "stone_remaining",
    "iron_remaining",
]


def load_zone_feature_schema() -> dict:
    """Load the fixed vocabulary of non-player-built zone features."""
    encoded = ZONE_FEATURE_SCHEMA_PATH.read_bytes()
    schema = json.loads(encoded)
    features = schema.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("Zone feature schema must contain features.")

    feature_ids = []
    feature_by_engine_id = {}
    for feature in features:
        identifier = feature.get("id")
        category = feature.get("category")
        engine_ids = feature.get("engine_ids")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("Zone feature has an invalid ID.")
        if not isinstance(category, str) or not category:
            raise ValueError(f"Zone feature {identifier!r} has an invalid category.")
        if not isinstance(engine_ids, list) or not engine_ids:
            raise ValueError(f"Zone feature {identifier!r} has no engine IDs.")
        if identifier in feature_ids:
            raise ValueError(f"Zone feature schema has duplicate ID {identifier!r}.")
        feature_ids.append(identifier)
        for engine_id in engine_ids:
            if not isinstance(engine_id, str) or not engine_id:
                raise ValueError(f"Zone feature {identifier!r} has an invalid engine ID.")
            if engine_id in feature_by_engine_id:
                raise ValueError(f"Engine feature {engine_id!r} is mapped twice.")
            feature_by_engine_id[engine_id] = identifier

    return {
        "feature_ids": feature_ids,
        "feature_by_engine_id": feature_by_engine_id,
        "schema_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _call_bool(runtime, expression: str) -> bool:
    result = runtime.call_native(expression)
    if result not in ("true", "false"):
        raise RuntimeError(f"Expected a Boolean from {expression}: {result!r}")
    return result == "true"


def _classify_owner(runtime, zone: str) -> dict[str, bool]:
    owned = _call_bool(runtime, f"{zone}.getOwner() == this.state.me")
    neutral = _call_bool(runtime, f"{zone}.getOwner() == null")
    allied = False

    if not owned and not neutral:
        allied = _call_bool(
            runtime,
            f"{zone}.getOwner().get_team() == this.state.me.get_team()",
        )

    return {
        "owned": owned,
        "neutral": neutral,
        "allied_owned": allied,
        "enemy_owned": not owned and not neutral and not allied,
    }


def _zone_features(runtime, zone: str, owner: dict[str, bool], resource_keys, catalogue) -> list:
    # These are map markers, rather than player-built infrastructure. The
    # native ID keeps the meaning stable even though the marker itself lives
    # in the zone's building collection.
    natural_markers = set()
    for index in range(runtime.array_length(f"{zone}.buildings")):
        building = f"{zone}.buildings[{index}]"
        identifier = json.loads(runtime.call_native(f"{building}.get_id()"))
        if identifier in catalogue["feature_by_engine_id"]:
            natural_markers.add(identifier)

    has_fish = _call_bool(runtime, f"{zone}.hasFish()")
    is_guarded = _call_bool(
        runtime,
        f"{zone}.hasHostility(this.state.me, null, null, null, null)",
    )
    slots_used = int(runtime.call_native(
        f'{zone}.getCurrentProduction({resource_keys["Building"]}, null, null, null, null)'
    ))
    slots_max = int(runtime.call_native(
        f'{zone}.getMaxProduction({resource_keys["Building"]}, null, null, null, null)'
    ))
    if slots_used < 0 or slots_max < 0 or slots_used > slots_max:
        raise RuntimeError("Invalid building-slot capacity.")
    is_coastal = _call_bool(runtime, f"{zone}.hasCoast()")
    stone = float(
        runtime.call_native(
            f'{zone}.getDepositResCount({resource_keys["Stone"]})'
        )
    )
    iron = float(
        runtime.call_native(
            f'{zone}.getDepositResCount({resource_keys["Iron"]})'
        )
    )
    if not math.isfinite(stone) or not math.isfinite(iron) or stone < 0 or iron < 0:
        raise RuntimeError("Invalid remaining mineral quantity.")

    return [
        1.0 if owner["owned"] else 0.0,
        1.0 if owner["neutral"] else 0.0,
        1.0 if owner["allied_owned"] else 0.0,
        1.0 if owner["enemy_owned"] else 0.0,
        1.0 if is_guarded else 0.0,
        slots_used,
        slots_max,
        1.0 if is_coastal else 0.0,
        1.0 if has_fish else 0.0,
        stone,
        iron,
    ] + [
        1.0 if feature_id in {
            catalogue["feature_by_engine_id"][marker]
            for marker in natural_markers
        } else 0.0
        for feature_id in catalogue["feature_ids"]
    ]


def discover_zone_graph(runtime) -> dict:
    """Locate every discovered zone and visible edge for this stopped frame."""
    nodes = {}
    queue = []

    # These expressions locate zone objects. The values exposed to the policy
    # come from the native discovery and ownership calls below.
    for index in range(runtime.array_length("this.state.me.zones")):
        zone = f"this.state.me.zones[{index}]"
        if not _call_bool(runtime, f"this.state.me.hasDiscovered({zone})"):
            raise RuntimeError("An owned zone is not discovered.")
        owner = _classify_owner(runtime, zone)
        if not owner["owned"]:
            raise RuntimeError("Player.zones contains a zone owned by someone else.")

        zone_id = int(runtime.evaluate(f"{zone}.id"))
        if zone_id not in nodes:
            nodes[zone_id] = {"expression": zone, "hops": 0, "owner": owner}
            queue.append(zone_id)

    adjacency = {}
    scout_sources = {}
    queue_index = 0
    while queue_index < len(queue):
        zone_id = queue[queue_index]
        queue_index += 1
        node = nodes[zone_id]
        zone = node["expression"]
        adjacency[zone_id] = set()

        for index in range(runtime.array_length(f"{zone}.next")):
            neighbour = f"{zone}.next[{index}]"
            if not _call_bool(runtime, f"this.state.me.hasDiscovered({neighbour})"):
                # An undiscovered neighbour is not a graph node. Its ID and
                # border relationship are enough to expose a scouting action.
                neighbour_id = int(runtime.evaluate(f"{neighbour}.id"))
                if _call_bool(runtime, f"{neighbour}.canBeScouted(this.state.me, null)"):
                    scout_sources.setdefault(neighbour_id, set()).add(zone_id)
                continue

            neighbour_id = int(runtime.evaluate(f"{neighbour}.id"))
            if neighbour_id == zone_id:
                continue
            adjacency[zone_id].add(neighbour_id)

            # Keep walking through discovered neighbours until the entire visible
            # map is represented. A distant zone can still affect expansion.
            if neighbour_id not in nodes:
                nodes[neighbour_id] = {
                    "expression": neighbour,
                    "owner": _classify_owner(runtime, neighbour),
                }
                queue.append(neighbour_id)

    zone_ids = sorted(nodes)
    row_by_zone = {zone_id: row for row, zone_id in enumerate(zone_ids)}
    edges = sorted(
        (source, target)
        for source, targets in adjacency.items()
        for target in targets
        if target in nodes
    )

    return {
        "nodes": nodes,
        "zone_ids": zone_ids,
        "edge_index": [
            [row_by_zone[source] for source, _ in edges],
            [row_by_zone[target] for _, target in edges],
        ],
        "scout_target_mask": [
            {
                "zone_id": target_id,
                "adjacent_to": sorted(source_ids),
            }
            for target_id, source_ids in sorted(scout_sources.items())
        ],
    }


def observe_zone_graph(runtime, resource_keys: dict[str, str], graph=None, catalogue=None) -> dict:
    """Return native zone features aligned with the discovered graph."""
    if graph is None:
        graph = discover_zone_graph(runtime)
    if catalogue is None:
        catalogue = load_zone_feature_schema()

    nodes = graph["nodes"]
    zone_ids = graph["zone_ids"]
    return {
        "feature_names": BASE_FEATURE_NAMES + catalogue["feature_ids"],
        "zone_ids": zone_ids,
        "x": [
            _zone_features(
                runtime,
                nodes[zone_id]["expression"],
                nodes[zone_id]["owner"],
                resource_keys,
                catalogue,
            )
            for zone_id in zone_ids
        ],
        "edge_index": graph["edge_index"],
        "scout_target_mask": graph["scout_target_mask"],
        "zone_feature_ids": catalogue["feature_ids"],
        "zone_feature_schema_sha256": catalogue["schema_sha256"],
    }


def summarize_zones(zones: dict) -> dict[str, dict]:
    """Return a sparse, human-readable view of an already-built zone tensor."""
    feature_names = zones["feature_names"]
    zone_ids = zones["zone_ids"]
    rows = zones["x"]
    build_masks = zones.get("build_action_mask", [])
    building_ids = zones.get("building_ids", [])

    if len(zone_ids) != len(rows):
        raise ValueError("Zone IDs and feature rows have different lengths.")
    if build_masks and len(build_masks) != len(zone_ids):
        raise ValueError("Zone IDs and build masks have different lengths.")

    summary = {}
    for row_index, (zone_id, row) in enumerate(zip(zone_ids, rows, strict=True)):
        if len(feature_names) != len(row):
            raise ValueError(f"Zone {zone_id} has an invalid feature row.")

        values = dict(zip(feature_names, row, strict=True))
        zone = {}
        for owner in ("owned", "neutral", "allied_owned", "enemy_owned"):
            if values[owner]:
                zone["owner"] = owner
                break

        flags = [
            name
            for name, value in values.items()
            if value and (name == "is_guarded" or name == "is_coastal" or name.startswith("has_"))
        ]
        if flags:
            zone["flags"] = flags

        zone["building_slots"] = {
            "used": values["building_slots_used"],
            "max": values["building_slots_max"],
        }
        resources = {
            name.removesuffix("_remaining"): value
            for name, value in values.items()
            if name.endswith("_remaining") and value
        }
        if resources:
            zone["resources"] = resources

        buildings = {
            name.removeprefix("building_"): value
            for name, value in values.items()
            if name.startswith("building_") and name not in {
                "building_slots_used",
                "building_slots_max",
            } and value
        }
        if buildings:
            zone["buildings"] = buildings
        construction = {
            name.removeprefix("construction_"): value
            for name, value in values.items()
            if name.startswith("construction_") and value
        }
        if construction:
            zone["construction"] = construction
        unassigned = {
            name.removeprefix("unassigned_construction_"): value
            for name, value in values.items()
            if name.startswith("unassigned_construction_") and value
        }
        if unassigned:
            zone["unassigned_construction"] = unassigned

        units = {}
        for side in ("friendly", "enemy", "neutral"):
            side_units = {
                name.removeprefix(f"{side}_"): value
                for name, value in values.items()
                if name.startswith(f"{side}_") and value
            }
            if side_units:
                units[side] = side_units
        if units:
            zone["units"] = units

        if build_masks:
            available = [
                building_id
                for building_id, allowed in zip(
                    building_ids,
                    build_masks[row_index],
                    strict=True,
                )
                if allowed
            ]
            if available:
                zone["buildable"] = available

        summary[str(zone_id)] = zone
    return summary
