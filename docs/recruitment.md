# Native chief and companion recruitment

The policy chooses the unit to recruit. Optional zone selection lets it control
where that unit appears; otherwise the resolver chooses the lowest-UID building
that passes the game's recruitment checks. Python does not maintain separate
clan-to-building tables or assume that every clan has one chief.

## Inspected native path

All IDs refer to the pinned supported bytecode. Disassemblies are recorded in
`artifacts/runs/recruitment-native.txt`, `recruitment-catalogue-native.txt`,
`recruitment-companions-native.txt` and `recruitment-chief-classification.txt`.

| Function | ID | Signature after receiver |
|---|---|---|
| Player.getAvailableHeroes | 5023 | () -> Array of String |
| Player.getAvailableWarchiefs | 5024 | () -> Array of String |
| Building.canHireHero | 5799 | (Player) -> Bool |
| Player.getNoHireHeroReason | 5027 | (Building, kind String, nullable phase) -> enum; phase null |
| Player.getWarchiefCost | 5022 | (kind String) -> Array of resource/quantity |
| Player.hireHero | 5278 | (Building, kind String, nullable phase, callback) -> Void; phase/callback null |
| Unit.get_isWarchief | 4235 | () -> Bool |

getAvailableHeroes combines native chief and companion lists. The chief list
also resolves cosmetic choices. Building.canHireHero checks ownership/state and
the native clan-specific HBuilding.getHeroHireBuildings rules, with native game
mode exceptions. getNoHireHeroReason validates the unit against the clan's hero
list, existing units, recruitment cooldowns, cost and special requirements.
The null-building query reports unit-level eligibility separately from locations.

The public hireHero RPC dispatches on the host to hireHero__impl f5031. It checks
canHireHero, pays getWarchiefCost through useResources, then spawns from the chosen
building and applies normal chief effects. Odin calls neither spawnUnit nor the
internal free-spawn functions. Native payment handles any free-chief cost rules.
The action is confirmed by exactly one new living owned UID of the selected
native kind. An unconfirmed result is not retried.

The reviewed scope is Wolf, Bear, Stag, Goat, Raven, Boar, Snake and Horse.
Exceptional clans requiring additional recruitment parameters are rejected.
Generic `warchief` is deliberately ambiguous for multiple-chief catalogues;
explicit named choice preserves the economic decision of which chief to buy.

## Observation and selection

`tools recruitment` returns every current native choice, cost, building location,
native rejection reason and mask. All current completed owned recruitment
buildings are considered; a zone filter restricts the search. No eligible
building produces `NoRecruitmentBuilding`, while `unit_reason` independently
reports restrictions such as `NoRes`, `AlreadyOne` or cooldowns. The environment
includes this metadata under progression.recruitment and encodes the two
semantic recruitment options into progression.x as described below. Existing
profession counts report chiefs and companions.

Cosmetic Hero03 was absent from the reviewed static profession map. Both the
owned job tool and zone unit observation now fall back to native get_isWarchief
for otherwise unmapped player-unit kinds, preserving the existing warchief
column and movement/assignment selection. Raw native kind remains available for
exact recruitment confirmation. Neutral unit mappings remain separate.

## Live validation

Stag's catalogue returned Hero03, an eligible TrainingCamp1350 in zone30 and
cost150 Money/5 Iron. Initial rejection was `NoRes`; Iron stock was0. The debug
resource tool granted exactly5 Iron. The funded preview became eligible and one
normal recruitment produced Hero03 UID1552. Money changed from272.3119512171195
to122.31195121711949 and Iron5 to0 in the same stopped frame.

A second request was rejected as `AlreadyOne` before dispatch. The next mask
was0. Both the job map and zone observation classified the cosmetic unit as a
warchief; friendly_warchief was1. Captures are
`artifacts/runs/recruitment-live-preview.json`, `recruitment-live-validation.json`
and their stderr logs. Normal debugger restoration completed.

The match contains Stag and Snake, so no Bear or Horse live recruitment could be
checked (`recruitment-clan-audit.json`). Companion recruitment, multiple chiefs,
multiple eligible buildings, filtered zones, cooldown expiry and bot dispatch
remain unverified live. No automated tests were added. Python syntax, CLI help,
diff whitespace and the existing native allowlist check passed.

## Seven-clan audit

Reviewed Wolf, Bear, Stag, Goat, Raven, Boar and Snake against the installed unit
catalogue and HBuilding.getHeroHireBuildings f16734. Ordinary baseline rules:

| Clan | Chief family | Base recruitment cost | Recruitment buildings |
|---|---|---|---|
| Wolf | Berserker | 200 Money +5 Iron | TrainingCamp, AxeCenter, ShieldCenter |
| Bear | Maiden / Skjaldmo | 150 Money +5 Iron | TrainingCamp, AxeCenter, ShieldCenter |
| Stag | Hero03 and native cosmetic alternatives | 150 Money +5 Iron | TrainingCamp, AxeCenter, ShieldCenter |
| Goat | Hero01 and native cosmetic alternatives | 150 Money +5 Iron | TrainingCamp, AxeCenter, ShieldCenter |
| Raven | Hero02/Liv and native cosmetic alternatives | 150 Money +5 Iron | TrainingCamp, AxeCenter, ShieldCenter |
| Boar | Hero04/BerserkerBoar selected by native cosmetics | 150 Money +5 Iron | TrainingCamp, AxeCenter, ShieldCenter |
| Snake | WarchiefSnake / Signy | 150 Money, no Iron | SkirmishCenter |

These are base data costs, not a replacement for getWarchiefCost at runtime.
Native free-chief rules, bonuses and mode modifiers can change actual costs.
The unit catalogue also contains banner characters and deprecated units; their
presence in Data.unit.all does not make them ordinary recruitment choices.
getAvailableHeroes remains authoritative for the current player.

Player.startGame f5067 contains Snake's automatic WarchiefSnake spawn from the
starting building (Unit.hx-independent Player source line7415). The current
Snake player61 also returns Signy, a SkirmishCenter in zone86, cost150 Money
and rejection AlreadyOne. Respawning her after death still follows native
recruitment and cooldown checks; starting with her does not remove that action.

Bear's companion is BearMaiden, named Kaija, the Armored Bear, with base cost
40 Money +40 Food. Bear is a separate Brown Bear wildlife record with no hero
recruitment cost. This audit corrected the `bear`/`bear_companion` alias to select
BearMaiden and added it to the existing bear_companion profession family.
`kaija` is also accepted. The native hero list must still provide that choice;
the alias cannot recruit it for another clan.

For these seven clans the numeric recruitment vocabulary stays fixed as
warchief and bear_companion. Native chief variants resolve internally;
the companion mask is zero for clans without it. Snake's chief mask is zero
while Signy is already present. The encoding is appended to progression.x.

Evidence: `artifacts/runs/seven-clan-hire-buildings.txt`,
`seven-clan-hero-maps.txt`, `seven-clan-unit-data.json`,
`seven-clan-variant-data.json`, `seven-clan-start-game.txt` and
`seven-clan-base-cost-getter.txt`. This audit read data and current Stag/Snake
state without issuing recruitment orders. Bear alias/count changes were checked
for syntax and schema validity; actual Bear recruitment remains unverified live.

## Numeric progression encoding

Ten fixed columns are appended after the existing progression features:

| Choice | Column suffixes, prefixed with recruit_CHOICE_ |
|---|---|
| warchief | available, can_recruit, cost_food, cost_gold, cost_iron |
| bear_companion | available, can_recruit, cost_food, cost_gold, cost_iron |

The native observer assigns a recruitment_type to each choice, using the native
chief list and reviewed BearMaiden companion mapping. Both semantic action
resolution and numeric encoding consume this classification. The encoder does
not derive model labels from cosmetic strings such as Hero03.

Available is1 when the semantic slot maps to exactly one native choice, even
if that choice is currently owned, unaffordable or on cooldown. Can_recruit is1
only when at least one owned building passes the native eligibility check.
Native costs are represented numerically even when blocked; absent slots have
zero costs. Multiple-chief ambiguity, including Horse, disables the generic
slot without choosing a chief on the policy's behalf. Explicit native choices
remain usable through the existing action. Unknown cost resources raise a
clear error instead of silently dropping a cost outside this reviewed encoding.

The top-level progression recruit_ids and recruit_action_mask use fixed order
[warchief, bear_companion]. The nested readable recruitment object retains its
native choice IDs and masks for diagnostics. The schema fingerprint includes
the new ordered feature/action vocabulary. Model input sizes must increase by10;
the rest of the progression vocabulary still depends on the clan's lore tree.
Both tools progression and NorthgardEnv.observe use the same observation path,
including the acting player stored in the catalogue, with no duplicate reads.

Read-only live validation produced85 progression values for both current Stag
and Snake players (previously75), with the same ten recruitment suffix columns
and the fixed action order. Both chief masks were0 due to AlreadyOne. Stag's
numeric cost was food0/gold150/iron5, Snake's food0/gold150/iron0. Both companion
slots were unavailable with zero costs and masks. Fingerprints changed as
expected. Captures: `artifacts/runs/recruitment-numeric-stag.json` and
`recruitment-numeric-snake.json`, plus stderr logs. No recruitment orders or
resource grants were sent for this validation. Bear's active companion slot
still needs live validation in a Bear match. No automated tests were added.
