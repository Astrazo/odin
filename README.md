# Odin

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
