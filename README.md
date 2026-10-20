# Odin

This is an experimental project. The default development loop is to change the
code, check behaviour in Northgard, inspect the logs and iterate. Add automated
tests only when explicitly requested; existing tests cover selected behaviours
and are not a substitute for observing the game.

Loop

1. Open one debugger connection
2. Set breakpoint at Game.onUpdate
3. Northgard reaches it and stops
4. Save the current Game.onUpdate frame
5. Remove the breakpoint
6. Observe and act using that saved frame
7. Continue Northgard
8. Let it run for 0.5 seconds
9. Set the Game.onUpdate breakpoint again
10. Northgard stops and provides a new frame
11. Repeat from step 4


Python action or observation
        ↓
Our JavaScript native-call fix
        ↓
Existing HashLink adapter machinery
        ↓
Northgard debug connection
        ↓
Native function executes inside Northgard


Current observation

- pause state
- food, wood, Krowns, stone, iron and lore stocks
- net flow for each resource
- happiness, population, population cap and food cap
- villager growth active, progress and time remaining
- current game time and time until the next winter and summer
- discovered one-hop zone graph with ownership, natural-food, fish and remaining
  stone/iron features per node

Resource catalogue IDs are found once when the environment opens. Every value
placed in the economy tensor comes from an inspected native getter. The migrated
economy tensor has also completed one live 19-value read on the recorded build.
The temporal tensor has completed one live summer read with internally consistent
winter and summer boundaries. Winter-state and UI comparisons still remain.

`odin run` extracts every tensor by default. Repeat `--tensor` to request only
the groups needed for a test:

```powershell
uv run odin run --tensor zones
uv run odin run --tensor economy --tensor temporal
```

Every `odin run` also writes the full observation sequence as a timestamped JSON
array in `artifacts/runs/`. The CLI prints the exact path when the run starts.

Available names are `pause`, `economy`, `temporal` and `zones`.

## Scoutable zones

List the local player's currently scoutable undiscovered neighbours:

```powershell
uv run odin tools scout-zones
```

The read-only tool returns `scout_ids` for living, owned units whose native
`get_canScout()` predicate is true, plus `scoutable_zones`, with each target's `zone_id` and
`adjacent_to` IDs of discovered zones bordering it. It uses the same engine
legality checks as the observation's `scout_target_mask`, without extracting
the full tensors or reading hidden zone contents. An empty list means no
currently legal targets were found.

Use a returned scout ID and zone ID with `uv run odin scout --unit SCOUT_UID --zone ZONE_ID`.
The scout action rechecks eligibility when dispatched. Listing targets does
not send a scout order; the action's reveal behavior still needs a live test.

## Colonisation

List discovered, unowned zones bordering your territory, including native
resource costs and blocked-zone reasons:

```powershell
uv run odin tools colonise-zones
uv run odin tools colonise-preview --zone ZONE_ID
uv run odin colonise --zone ZONE_ID
```

The first two commands are read-only. `colonise` sends one normal paid request
through `Player.world.startColonize`, then confirms either the immediate
`colonizeBy` link or ownership. `requested: true` means the start was observed;
the territory may still need game time to finish colonising.

The engine's `ColonizeTestType.CurrentRes` check covers its current resource
mode, affordability, adjacency, occupation, hostilities, clan requirements and
cooldowns. Costs are read from the game; Odin does not assume Food or a fixed
price. Alternative resource-mode selection is not exposed yet. Hidden zones
and already-owned zones are excluded before reading their costs or contents.

All three commands accept `--player PLAYER_UID`. Bot dispatch follows the same
paused/offline/authoritative and stopped-AI requirements as assignment.
`NorthgardEnv.colonise(zone_id, player_id=...)` exposes the same action.

The read-only listing and cost/reason bindings were tested live on 20 October:
zones85/92 were eligible for Food20, while zone89 was `Occupied`. No live paid
request was sent during implementation. See [native path and validation notes](docs/colonisation.md).

## Worker assignment and bot players

Build and assign are separate policy actions. Build places the site and leaves
normal local auto-assignment to Northgard. After advancing the simulation, the
policy observes construction staffing and can choose to assign a worker if a
site is still unstaffed. Odin does not schedule a fallback assignment itself.

```powershell
uv run odin build --zone 35 --building house
# After simulation advances, inspect the current site's staffing.
uv run odin tools assign-preview --building house --zone 35 --construction --from-job villager --from-zone 4
uv run odin assign --building house --zone 35 --construction --from-job villager --from-zone 4
# Assign to a completed scout camp, converting an eligible worker normally:
uv run odin assign --building scout_camp --zone 35 --from-job woodcutter --from-zone 7
# Use a villager already in the scout camp's zone:
uv run odin assign --building scout_camp --zone 35 --from-job villager
```

`--from-zone` is where the worker currently is; `--zone` is where the target
building is. Omit `--from-zone` to use the target building's zone. This also
works with a numeric building UID: Odin reads its current zone. An empty local
worker group reports an error; it does not choose a worker from another zone.
`--construction` selects unfinished sites; the default selects
completed buildings. These choices correspond to `construction_<family>` and
`building_<family>` in the observations. They never fall back to another zone,
family or construction state. A destination zone is required with a family.

Profession names use the zone
count vocabulary, such as `villager`, `woodcutter` or `farmer`. Assignment and
preview also accept `--player PLAYER_UID` for bots. Build uses the local player
and accepts only the destination zone and building family.

`resolve_worker(runtime, job, source_zone_id, building_id=..., player_id=...)`
reads a fresh owned-unit job map and considers living workers in the requested
group. With a target building, it checks the native assignment validator in
ascending UID order and chooses the first eligible match. Without a target,
it chooses the lowest matching UID. This is a stable tie-break, not an economic
ranking. It can divert an already-working unit of the requested profession.
It never substitutes another profession or source zone. An empty or ineligible
group produces an error without dispatching an assignment. Only one assignment
order is sent; rejected orders are not retried against other workers.

`resolve_assignment` resolves both worker and building groups. Within a zone,
it prefers unstaffed construction sites (including incoming assignments when
checking staffing), then uses building UID and worker UID order to find an
eligible pair. Completed buildings use UID order and native eligibility checks,
so a rejected/full building does not prevent trying another matching building.
Native eligibility still decides whether a profession can be reassigned to the
chosen building. The result includes both resolved UIDs for debugging.

Python callers use `env.build(35, "house")`, advance with `env.step()`, then
optionally call
`env.assign_worker("villager", 4, "house", target_zone_id=35, construction=True)` in a later
policy decision. The policy chooses whether and when to assign; the resolver
only translates the chosen profession/source zone into an executable unit ID.
For a worker in the building's zone, use
`env.assign_worker("villager", building_id="house", target_zone_id=35, construction=True)`.
Numeric `--building BUILDING_UID` and `--unit UNIT_UID` remain debug overrides.
This resolver adds
no numeric observation features.

Build returns `placed: true` and `construction_id`, the new site's runtime UID;
`building_id` remains the semantic family name. A `construction_error` means
placement returned an object but its identity could not be uniquely confirmed.
Do not repeat placement because subsequent inspection failed. Staffing belongs
to observations after simulation advances, rather than the build response.

Zone observations now expose:

- `unassigned_construction_<family>`: owned construction count with no living
  owned worker explicitly assigned, alongside the existing construction counts.
- `construction_sites`: owned site IDs, zone, family, expected engine type,
  `assigned_unit_ids` and `has_assigned_worker`, including unmapped families.
- `summary[ZONE_ID].unassigned_construction`: the same nonzero counts by family.

Assignments are read across the whole player's unit collection, so a worker
travelling from another zone counts as assigned. A link does not prove arrival,
path safety or construction progress. No link immediately after placement can
be temporary: native automatic job selection happens on subsequent simulation
updates. These are observations, not a command to assign or a forced penalty.

The policy learns two decisions: what/where to build, and whether/when to
reallocate a worker after observing an unstaffed site. The staffing features
make the second decision visible to a future RL learner; internal ID maps
identify action targets. Odin does not yet implement a learner or rewards, so
these features alone do not teach worker allocation. Training should value the
resulting economy and game outcomes; waiting can be a deliberate choice.

Completion replaces the construction object and changes its UID. Each fresh
observation lists current sites only; an old construction ID is not a handle
for the finished building, and disappearance alone is not proof of completion.

Read a map of living owned unit IDs to their current profession and location:

```powershell
uv run odin tools unit-jobs
uv run odin tools unit-jobs --player PLAYER_UID
```

The result is `{"unit_jobs": {"101": {"job": "woodcutter", "engine_id":
"Woodcutter", "zone_id": 7}}}`. IDs are JSON object keys; pass a chosen ID to
`assign --unit`. `job` uses the same profession vocabulary as the zone counts.
Unknown professions retain their engine type with `job: null`; units without a
current zone have `zone_id: null`. The map includes all living owned unit types,
including military units, and is not a promise that each can build. Use
`assign-preview` to check a chosen unit against the intended construction site.

Local-player zone observations also include `zones.unit_jobs` for owned units
in discovered zones. Allied units remain in friendly counts but are excluded
from the ID map. Professions describe roles, not moment-to-moment activity or
idle status. Each read refreshes the map, so profession changes keep the same
unit identity.

Assignments use the game's `ScriptApi.assign` helper. The default command still
acts for your local player:

```powershell
uv run odin assign --unit UNIT_UID --building BUILDING_UID
```

To act for a bot, select its current player UID. Player, unit and building UIDs
are runtime identities and must be listed again after starting a new match.
Pause an offline match normally, then list players and the chosen bot's objects:

```powershell
uv run odin tools players
uv run odin tools ids --player PLAYER_UID
uv run odin tools buildings --player PLAYER_UID --zone ZONE_ID
uv run odin tools assign-preview --player PLAYER_UID --unit UNIT_UID --building BUILDING_UID
```

The preview only checks ownership and the engine's assignment validator; it does
not change the bot's AI gate or send an order. Bot dispatch requires the
authoritative offline host, a paused match, and stopped stock AI orders:

```powershell
uv run odin ai-stop --player PLAYER_UID
uv run odin assign --player PLAYER_UID --unit UNIT_UID --building BUILDING_UID
```

`ai-stop` reports the previous gate value and verifies the native setter's
read-back. The flag stops the main stock AI decision loop; existing movement,
work and other simulation continue when play resumes. To restore decisions
when the flag was previously false, pause and run:

```powershell
uv run odin ai-resume --player PLAYER_UID
```

Assignment uses only the selected player's unit and zone collections, rechecks
ownership, sends one order without retrying, and confirms the immediate
`assignTo` link. `NorthgardEnv.assign(..., player_id=PLAYER_UID)` exposes the
same selection. The current build/scout actions and observation tensors still
use the local player's context.

On 20 October, a paused live bot test assigned Gunnar's Villager 1195 to Scout
Camp 1282 using player UID61. The native result and immediate link were true,
and Northgard remained running after detach. The test restored Gunnar's prior
AI gate and left the match paused; travel and work after unpausing were not
measured. See [the investigation record](docs/assignment-crash-investigation.md).

## Offline building candidates

Building definitions can be reviewed without starting Northgard. The tool reads
the installed `res.client.pak`, extracts `data.cdb`, and selects ordinary
build-tab candidates for the requested clans:

```powershell
uv run python .\tools\building_catalogue.py "C:\Program Files (x86)\Steam\steamapps\common\Northgard\res.client.pak" --clan Wolf --clan Stag
```

It applies the static clan-type and declared clan restrictions. It does not
answer whether a building is available in a particular zone: that still depends
on live terrain, prerequisites, resources, slots, and game mode. Use the report
to author Odin's small semantic building vocabulary. The live zone action mask
then enables only actions returned by Northgard for the current clan and zone.

The current zone tensor uses the reviewed Wolf/Bear/Stag/Goat/Raven/Boar/Snake/Horse
schema in `src/odin/data/building_schema.json`. It contains 28 semantic families,
such as
`house`, `mine`, `carved_stone`, and `tower`. `GuardTower` and `WatchTower` both
map to `tower`; Stag adds its distinct `hall_of_skalds` family and Goat adds
`sheepfold`. The shared late-game families are `altar_of_kings`, `offering_well`,
and `monument_to_gods`. Raven's `RavenPort` is the distinct `harbor` family; it
is not folded into `longship_dock`. Boar's `MenderHut` is the distinct
`menders_hut` family, because idle Menders generate Lore rather than Food.
Snake adds the distinct `skirmisher_camp` family. Unknown engine IDs are omitted
from counts and action masks. Completed and under-construction counts share each
zone's feature row, and the aligned action mask is nonzero only for owned zones
and engine-available mapped IDs.

Unmapped player-built, construction, and currently available engine IDs are
returned in `zones.unmapped_buildings` with their zone and source. They are
diagnostics only and never create policy features or actions.

Use `--show-unmapped` to print a compact diagnostic report to the terminal's
error stream while keeping the JSON observation stream unchanged:

```powershell
uv run odin run --tensor zones --show-unmapped
```

Horse's `ForgeHorse` maps to the shared `forge` family. `mine` remains in the
shared schema but is unavailable to Horse; its warchiefs mine instead. Warchief
recruitment from the Forge is a planned action, while Forge relic crafting is
deferred.

## Training-clan rollout

The selected clans and rollout order live in
`src/odin/data/training_clans.json`. Wolf and Bear are the baseline. Stag and
Goat follow once that contract is stable, then Raven and Boar. Bear's future
military action set contains both `recruit_warchief` and
`recruit_bear_companion`. Raven's planned Harbor actions are `loot_krowns`,
`scout_shores`, and `deploy_mercenaries`; normal Dock modes are `raid_lore` and
`raid_fame`. Trade routes are deferred. No recruitment or Harbor action is
implemented yet. Boar's future neutral-zone colonisation path is also action
masked separately. Snake adds future `signy_age`, `copied_lore`, and
`copied_lore_choice` fields; no Snake native binding is implemented yet.
