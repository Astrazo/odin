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
- feast active state, remaining time, next resource/cost and start eligibility
- clan lore research, military XP/path progression and legal progression choices
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

Available names are `pause`, `economy`, `temporal`, `zones` and `progression`.

## Feasts

```powershell
uv run odin tools feast
uv run odin feast
uv run odin run --tensor temporal
```

`tools feast` reads the active feast, remaining simulation seconds, next native
cost and `can_feast`. `feast` sends one normal paid request and confirms the
active state. Both accept optional `--player`; actions for bots require their
stock AI orders stopped and the game paused. Python uses `env.feast(player_id=...)`.

The temporal tensor now has nine values: the existing three clock/season values,
then `is_feasting`, `feast_time_remaining`, `feast_resource_food`,
`feast_resource_gold`, `feast_cost`, `can_feast`. The resource flags encode the
native Food/Money choice without an arbitrary numeric ID. Cost always describes
the next feast, including native discounts/free feasts; `can_feast` is the action
mask. The readable `feast` metadata contains the native resource name and cost.
Consumers using the previous three-value temporal shape must update their input.

Live validation started one feast: food500 ->400, remaining time60 seconds,
next cost150 food, and a duplicate request rejected before dispatch. See
[native evidence and validation](docs/feast.md).

## Chief and companion recruitment

```powershell
uv run odin tools recruitment
uv run odin recruit warchief
uv run odin recruit bear
uv run odin recruit warchief --zone 30
```

The game supplies the clan's chief/companion choices, recruitment-building rules,
costs, cooldown/uniqueness checks and paid recruitment request. Odin scans current
owned buildings and chooses the lowest-UID eligible location; optional `--zone`
restricts that search. No recruitment-building list is hardcoded in Python.
Both commands accept optional `--player`; bot recruitment requires a paused
offline match and stopped stock AI orders.

`warchief` resolves automatically when the clan has one chief choice. With
multiple chiefs, use one of the named `id` values from `tools recruitment`.
`bear` (also `bear_companion`) selects the Bear companion when the native clan
catalogue provides it. Choice IDs can reflect cosmetic variants; runtime UIDs
remain internal. Already-present units, costs and cooldowns remain native rules.

The tool returns costs, eligible/blocked locations and `recruit_action_mask`
aligned with its native `recruit_ids`. Progression observations include this
readable information under `progression.recruitment` and append ten numeric
columns: for each of `warchief`, then `bear_companion`, the suffixes are
`available`, `can_recruit`, `cost_food`, `cost_gold`, `cost_iron`, prefixed with
`recruit_<choice>_`. Availability means the semantic action has one native
counterpart for this clan; current eligibility also requires a legal building,
resources, uniqueness and cooldown checks. An unavailable slot has zero costs
and mask. Costs remain visible when recruitment is temporarily blocked.

Top-level `progression.recruit_ids` is always `["warchief", "bear_companion"]`,
with `progression.recruit_action_mask` in the same order. Pass the chosen label
to `env.recruit(...)`; native unit variants and building UIDs are resolved
internally. Multiple-chief clans require explicit native choices and have the
generic warchief slot masked. This encoding adds ten columns and changes the
progression schema fingerprint; existing model inputs need updating.
Existing zone unit counts and job maps recognise cosmetic chiefs via
the native warchief classifier. Python uses `env.recruit("warchief", zone_id=...)`.

Live validation recruited Stag's cosmetic chief after granting the missing5 iron.
The normal request paid150 Krowns and5 iron, a duplicate returned `AlreadyOne`,
the mask switched off, and the unit appeared in the warchief count/job map.
Bear and multiple-chief recruitment still need live validation with those clans.
See [native recruitment evidence](docs/recruitment.md).

## Building upgrades and debug resources

```powershell
uv run odin tools upgrade-preview --building town_hall --zone 30
uv run odin upgrade --building town_hall --zone 30
uv run odin debug add-resource stone 10
uv run odin debug add-resource wood 200
uv run odin debug add-resource gold 100
```

Upgrade selection uses a completed building family and owned zone, choosing an
eligible building before using its lowest runtime UID as a tie-break. A numeric
`--building` UID also works for debugging; omit `--zone` in that case. The preview
reports native blocking reason, nominal next cost, free-upgrade eligibility and
current level. The action upgrades one ordinary level using normal payment and
confirms the level increased. Transformation branches are not exposed.
Both commands accept optional `--player`; bot actions require a paused match and
stopped stock AI orders. Python uses `env.upgrade("town_hall", zone_id=30)`.

Zone observations retain total completed counts and append
`upgraded_building_<family>` counts. `upgrade_action_mask` is a zone-by-building
matrix aligned with `zone_ids` and `building_ids`; a1 means at least one owned
building of that family can currently upgrade. Consumers must account for the
extra observation columns.

`debug add-resource RESOURCE AMOUNT` grants a positive amount in an offline host
match. Resources are `food`, `wood`, `gold` (also `krowns`/`money`), `stone`, `iron`
and `lore`. Optional `--player` selects another clan. The result reports requested
and actual added amounts using native resource bookkeeping and limits. Debug
grants are separate from environment policy actions and never run automatically
when an upgrade is unaffordable.

Live validation granted the missing10 stone, changed the town hall's eligibility
from `CantPay` to allowed, then upgraded it from level0 to1. The normal request
deducted100 wood,50 Krowns and10 stone. The observation showed one upgraded town
hall and a zero mask after reaching `NoUpgrade`. See [native evidence](docs/upgrades.md).

## Lore and military progression

```powershell
uv run odin tools progression
uv run odin run --tensor progression
uv run odin lore lumber
uv run odin military guardian
```

`tools progression` is read-only. It lists the clan's complete tech tree with
semantic `id`, display `name`, learned state, native cost/resource and
`can_research`, plus military path choices with `selected` and `can_select`.
Use the listed IDs for actions. Lore also accepts a matching display name such
as `odin lore "Sharp Axes"`. Military accepts the native path labels `leadership`,
`guardian`, `legions`, with `tactician` and `conqueror` as aliases for the first
and third. IDs are named catalogue entries, not runtime object UIDs.

The new global tensor contains next lore cost, free lore choices, military XP,
next XP threshold, native auto-unlock state, two flags per clan tech
(`unlocked`, `can_research`), path selected/available flags and military ability
unlock flags. Lore stock remains in the economy tensor. `lore_action_mask` and
`military_action_mask` align with the returned `tech_ids` and `military_path_ids`.
The complete learned/locked vocabulary stays stable within a clan; the schema
fingerprint includes the clan and catalogue. Pin feature names/fingerprint
before reusing trained weights with another clan or game build.

Lore eligibility combines native prerequisite and payment predicates; the
catalogue getter alone does not indicate legality. Listed costs are native
nominal costs: free choices and blessings use the normal engine payment rules.
Military selection is limited to the first primary ordinary path, requires the
native XP/legality check and is masked after a path is selected. Later ordinary
tiers are left to native auto-unlock. Free secondary paths, Dragon/Lynx boards,
Owl research, stolen/copied lore subchoices and other exceptional progression
are not exposed by these actions. The reviewed clans are Wolf, Bear, Stag,
Goat, Raven, Boar, Snake and Horse.

Both actions and the read-only tool accept `--player PLAYER_UID`. Bot dispatch
requires a paused authoritative offline match with that bot's stock AI stopped,
as with assignment. Actions send one normal public RPC and confirm learned
state; an unconfirmed result is not automatically retried. Python exposes
`env.lore("lumber", player_id=...)` and `env.military("guardian", player_id=...)`.

See [the native bindings and validation record](docs/progression.md).

## Moving units

```powershell
uv run odin move --from-zone 7 --to-zone 4 --who villager
uv run odin move --from-zone 4 --to-zone 7 --who military
uv run odin move --from-zone 4 --to-zone 7 --who warrior --count 3
uv run odin move --from-zone 7 --to-zone 4 --who all
```

`--who` accepts a profession from the unit-count vocabulary, `military` (the
native fighter predicate), or `all`. Selection includes only living owned units
currently in `--from-zone`; runtime IDs are resolved internally in ascending
order. Omit `--count` to select all eligible matches. An explicit count is exact:
if fewer units are eligible, no order is sent. Unknown professions, nonpositive
counts and identical source/destination zones are rejected.

Preview the same command without moving anyone:

```powershell
uv run odin tools move-preview --from-zone 7 --to-zone 4 --who villager --count 2
```

The preview shows eligible count, selected unit IDs, excluded units/reasons and
whether the request can be dispatched. Native controllability and path checks
decide eligibility. General movement requires a destination in the
discovered map, whether friendly, neutral or enemy-owned; use the separate
scout action for undiscovered targets. No hidden-zone contents are exported.

Fighters receive normal movement with `canAttack=true`; other units receive
`false`. This uses native unit actions and leaves ordinary combat to the game.
There is no separate attack command. Moving does not prove arrival, survival,
zone clearance or colonisation; use subsequent observations to decide what to
do next. Native movement clears building assignment/work links, so returning a
specialist may require a separate `assign` action and a fresh profession read.

Results distinguish confirmed or already-existing destination orders from
unconfirmed ones. If one order fails, earlier orders may still be active;
remaining units are reported as not attempted and no orders are retried.
Both commands accept `--player PLAYER_UID`; bot movement requires a paused
authoritative offline match with that bot's stock AI orders stopped.
Python exposes `env.move(7, 4, "villager", count=2, player_id=...)`.

See [movement bindings and live validation](docs/movement.md).

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
shared schema but is unavailable to Horse; its warchiefs mine instead. The
recruitment resolver uses native building rules, including Horse's Forge;
multiple chiefs require explicit choices. Forge relic crafting is deferred.

## Training-clan rollout

The selected clans and rollout order live in
`src/odin/data/training_clans.json`. Wolf and Bear are the baseline. Stag and
Goat follow once that contract is stable, then Raven and Boar. Bear's recruitment
choices contain both `warchief` and `bear_companion`. Raven's planned Harbor actions are `loot_krowns`,
`scout_shores`, and `deploy_mercenaries`; normal Dock modes are `raid_lore` and
`raid_fame`. Trade routes and Harbor actions are deferred. Recruitment is
implemented as described above. Boar's future neutral-zone colonisation path is also action
masked separately. Snake adds future `signy_age`, `copied_lore`, and
`copied_lore_choice` fields; those Snake-specific observations are not implemented yet.
