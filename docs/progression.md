# Lore and military progression

The global progression tensor supports two strategic choices: which clan tech
to learn and which initial ordinary military path to select. It does not
duplicate resource stocks from economy or attach global features to every zone.
No automated tests were added, following the project's manual iteration policy.

## Native evidence

Inspected the installed bytecode matching `supported_build.json`, guided by
the previous project's CLAN_TECH_VOCABULARY and EXPLICIT_GLOBAL_TENSORS notes.
Offline scripts and disassemblies are in `artifacts/runs/progression-*` and
`inspect_progression*.cjs`.

| Purpose | Native method / function index |
|---|---|
| Complete clan tech tree | TechComponent.getAvailableTechs, 13077 |
| Learned tech | TechComponent.hasTech, 13059 |
| Tech prerequisites | TechComponent.canUnlockTech, 13086 |
| Tech affordability/free choice | TechComponent.canPayTech, 13068 |
| Per-tech nominal cost | TechComponent.getNextTechCost, 13076 |
| Per-tech resource | TechComponent.getTechPayRes, 13067 |
| Normal paid research RPC | TechComponent.unlockTech, 13178 |
| Military ability unlocked | TechComponent.hasMiliPathAbility, 13108 |
| Military XP/unlock predicate | TechComponent.canUnlockMiliPathAbility, 13105 |
| Native later-tier automation | TechComponent.canAutoUnlockNextMilitaryPathAbility, 13102 |
| XP level count / requirement | Player.getMilitaryXPLevelsCount / getMilitaryXPLevel, 5139 / 5140 |
| Normal primary military RPC | TechComponent.unlockMiliPathAbility, 13179 |

The lore UI's canClick f26466 combines canUnlockTech with canPayTech. Research
RPC f13178 reaches the authoritative implementation f13095, which rechecks
prerequisites and performs normal resource/free-credit payment before applying
the tech. Payment-bypassing Player.unlockTech/doUnlockTech are not allowlisted.

Military predicate f13105 checks XP, existing ability state and game rules, but
does not enforce the UI's chosen-path restriction. The ordinary UI f24056 derives
the selected group from the first primary unlock, and f33309 invokes public
RPC f13179 when choosing a primary path. Odin allows only the first entry of
an ordinary group while no primary unlocks exist. It sends that one order and
leaves subsequent tiers to the game's normal auto-unlock loop. This avoids
offering arbitrary abilities or cross-path unlocks just because f13105 is true.

Military groups 0/1/2 are the reviewed Leadership/Guardian/Legions groups;
named aliases tactician/conqueror are accepted for Leadership/Legions. Primary
unlocks and free abilities are distinct: free abilities are visible in unlocked
flags but do not select another primary group or increment the primary tier.

## Observation and dispatch

Catalogue labels derive from named native entries. Managed entry.id references
are passed into native methods; action text is never allocated as a target
runtime string or used as an object UID. Full clan tech lists are sorted and
retained after learning. The schema digest includes clan, tech labels/native
names and military group entries. The environment keeps this catalogue for
repeated reads and rejects a changed clan instead of silently shifting columns.

Tech flags combine learned state, prerequisites and affordability. Nominal
costs are also provided in readable records; free choices and blessings can
make actual payment differ. Military masks describe the initial path choice,
not secondary/free-path actions or every tier's automatic state transition.

Reviewed ordinary clans: Wolf, Bear, Stag, Goat, Raven, Boar, Snake and Horse.
Unsupported clans fail explicitly rather than inheriting an invalid mask.
Special stolen/copied/fountain research and exceptional military boards need
their own reviewed selectors. All actions require an authoritative offline
host, with the existing paused/stopped-AI gate for bots, and confirm resulting
state without retrying a paid operation.

## Validation

CLI help, Python/JSON syntax checks and native bytecode inspection completed.
The live read-only extraction succeeded on 21 October for Stag: 25 clan techs,
75 numeric features, no path selected, 38 MilitaryXP against the first 50-XP
threshold. Great Deeds, Lumber/Sharp Axes and Weaponsmith were legal at a nominal
80 Lore each; all three path-selection masks were zero. Northgard remained
running after normal detach. The captured observation and native call/restoration
log are `artifacts/runs/progression-live.json` and `progression-live.stderr.log`.

Live extraction identified two details corrected during implementation: military
indices are full-catalogue positions rather than per-path zero-based tiers, and
tech virtual definitions need the same narrowly scoped adapter cast preservation
as building definitions. `hasMiliPathAbility` has an optional kind19 argument,
not kind14; the bridge rejected the mismatch before calling native code and the
contract now matches inspected metadata. All new signatures were compared with
the installed bytecode. Only the existing allowlist expectation was updated;
no new automated tests were added.

Successful paid research and military selection have not been tested live. No
Lore was spent, no military path was chosen and no game resources were altered
for validation. Other reviewed clans and bot dispatch still need live samples.
