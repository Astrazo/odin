# Building upgrades and offline resource grants

The policy chooses whether to spend resources improving an existing building.
It selects a family and zone, using the same fresh building resolver as worker
assignment. Resolution prefers native-eligible buildings, then lowest UID. An
already upgraded building does not block another eligible copy of its family.
Constructions are excluded; upgrade is separate from construction staffing.

## Native evidence

Inspected the bytecode pinned in `supported_build.json`; captures are in
`artifacts/runs/upgrades-native.txt`, `upgrade-free-native.txt` and
`upgrade-methods.jsonl`.

| Operation | Native function | Arguments after receiver |
|---|---|---|
| Upgraded state | Building.isUpgraded, f5821 | none |
| Blocking reason | Building.getNoUpgradeReason, f5889 | none |
| Nominal next cost | Building.getUpgradeCost, f5818 | nullable level, null |
| Free upgrade | UpgradesComponent.hasFreeBuildingUpgrades, f13200 | building, null ordinary branch |
| Normal upgrade | Building.doUpgrade, f6041 | null ordinary branch, null callback |
| Debug resource grant | ResourcesComponent.addResource, f13495 | resource String, Float64 amount, null default reason |

getNoUpgradeReason covers available levels, clan restrictions, hostility,
technology, prerequisite buildings and current affordability/free upgrades.
Building.canUpgrade f5887 is simply a null-reason check. Odin uses that same check
before dispatch and masks any non-null reason.

The upgraded-town-hall prerequisite is already part of that mask. In f5889,
ordinary non-TownHall upgrades check the owner's town-hall status flags and
return a prerequisite-building reason when they are absent. This uses the same
status bits as Player.get_upgradedTH f4816. Native free-upgrade/clan exceptions
remain governed by the engine. Resource grants alone do not satisfy this
prerequisite. The action's preflight reads the same reason, so a direct command
cannot skip a masked prerequisite. Inspection is captured in
`artifacts/runs/upgrade-townhall-prerequisite.txt` and `upgrades-ops.txt`.

doUpgrade is the normal public RPC. On the host it dispatches to
doUpgrade__impl f5822, then _doUpgrade f5823 with default options. The latter
charges native useResources or consumes a native free upgrade, increments the
upgrade level and applies effects. The internal bypass/options path is not
exposed. Odin verifies a level increase on the freshly resolved owned UID;
unconfirmed actions are not retried. Ordinary upgrades retain the building UID
in the observed case; native building transformations are outside this action.

Nominal cost comes from the native getter, including its reductions and resource
substitutions. `free_upgrade` indicates normal free-upgrade handling; nominal
`cost` should not be interpreted as a guaranteed debit. The action's returned
eligibility/cost describe its preflight; upgrade_level describes the confirmed
result. Run another preview for the next level.

Debug resource grants require an authoritative offline match, allow only the
six basic economy resources, and report before/after amounts. They use native
bookkeeping, not direct writes to cached stocks. They retain native caps and
clan/resource rules, so the requested amount may differ from the actual change.
They are only exposed under the CLI debug group, with no NorthgardEnv helper.

## Observations

Existing completed-building counts include both ordinary and upgraded buildings.
The appended upgraded count per family is a subset, enabling a policy to tell
whether its infrastructure has already been improved. Native isUpgraded also
handles definition flags rather than assuming every building's kind changes.
The upgrade mask is true if any matching owned completed building has no native
blocking reason. Non-owned zones have zero upgrade masks. No runtime UIDs enter
the numeric observation vector.

## Live validation

TownHall1140 in zone30 initially had level0 and reason `CantPay`. Cost was
100 Wood,50 Money,10 Stone, with no free upgrade. Resource stocks in the stopped
frame were Wood272.1157897330703, Money253.2710029637623, Stone0.

The debug tool added exactly10 Stone, reporting before0/after10. A fresh preview
became eligible. One normal doUpgrade request changed level0 to1 and deducted
exactly100 Wood,50 Money and10 Stone. A subsequent preview returned `NoUpgrade`
with no further cost. Building observations reported
`upgraded_building_town_hall=1` and its upgrade mask0. Captures:
`artifacts/runs/upgrade-live-preview.json`, `upgrade-live-validation.json` and
their stderr logs. No new automated tests were added; syntax, CLI help and the
existing native allowlist check were run.

An initial preview hit the adapter's unsupported VArray/null equality, after
the getter returned safely. Checking the getter's null result directly fixed
the preview; no upgrade was sent during that failed attempt.

Other building families, multiple copies, free upgrades, resource caps, clan
exceptions and bot upgrades/resource grants remain unverified live.
