"""Discovered Northgard zones arranged as a graph for a GNN."""

import math


FEATURE_NAMES = [
    "owned",
    "neutral",
    "allied_owned",
    "enemy_owned",
    "has_fields",
    "has_deer",
    "has_fish",
    "stone_remaining",
    "iron_remaining",
]


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


def _zone_features(runtime, zone: str, owner: dict[str, bool], resource_keys) -> list:
    # These are map markers, rather than player-built infrastructure. The
    # native ID keeps the meaning stable even though the marker itself lives
    # in the zone's building collection.
    natural_markers = set()
    for index in range(runtime.array_length(f"{zone}.buildings")):
        building = f"{zone}.buildings[{index}]"
        identifier = runtime.call_native(f"{building}.get_id()")
        if identifier in ('\"Fertility\"', '\"DeerSpawner\"'):
            natural_markers.add(identifier)

    has_fish = _call_bool(runtime, f"{zone}.hasFish()")
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
        1.0 if '\"Fertility\"' in natural_markers else 0.0,
        1.0 if '\"DeerSpawner\"' in natural_markers else 0.0,
        1.0 if has_fish else 0.0,
        stone,
        iron,
    ]


def discover_zone_graph(runtime, max_hops: int = 1) -> dict:
    """Locate discovered zones and their edges for this stopped frame."""
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
                continue

            neighbour_id = int(runtime.evaluate(f"{neighbour}.id"))
            if neighbour_id == zone_id:
                continue
            adjacency[zone_id].add(neighbour_id)

            if neighbour_id not in nodes and node["hops"] < max_hops:
                nodes[neighbour_id] = {
                    "expression": neighbour,
                    "hops": node["hops"] + 1,
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
    }


def observe_zone_graph(runtime, resource_keys: dict[str, str], graph=None) -> dict:
    """Return native zone features aligned with the discovered graph."""
    if graph is None:
        graph = discover_zone_graph(runtime)

    nodes = graph["nodes"]
    zone_ids = graph["zone_ids"]
    return {
        "feature_names": list(FEATURE_NAMES),
        "zone_ids": zone_ids,
        "x": [
            _zone_features(
                runtime,
                nodes[zone_id]["expression"],
                nodes[zone_id]["owner"],
                resource_keys,
            )
            for zone_id in zone_ids
        ],
        "edge_index": graph["edge_index"],
    }
