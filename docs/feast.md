# Feast observations and action

The economic decision is when to exchange the current resource cost for a
temporary production/growth boost. Temporal observations expose its duration
alongside winter timing; economy observations already expose the available stock.
`can_feast` masks unaffordable requests, active feasts and defeated clans.

## Inspected native path

All IDs refer to the bytecode pinned in `supported_build.json`. Inspection is
recorded in `artifacts/runs/feast-native.txt` and `feast-defeat-check.txt`.

| Function | ID | Signature |
|---|---|---|
| ResourcesComponent.isFeasting | 13537 | (ResourcesComponent) -> Bool |
| ResourcesComponent.getRemainingFeastTime | 13539 | (ResourcesComponent) -> nullable Float |
| ResourcesComponent.getFeastCost | 13528 | (ResourcesComponent) -> Array of resource/quantity |
| Player.canFeast | 4727 | (Player, Array) -> Bool |
| Player.isDefeated | 4978 | (Player, Ref of Bool) -> Bool; optional argument null |
| ResourcesComponent.netStartFeast | 13686 | (ResourcesComponent, callback) -> Void; callback null |

The public netStartFeast RPC invokes netStartFeast__impl f13534 on the host.
It checks the current cost and active state, then invokes startFeast f13536 with
null options. That function checks defeat state, pays through useResources,
updates feast counts, instigator and start time, and applies normal effects.
Odin does not expose the options that can bypass payment or an existing feast.

Costs come from the game, including free feasts, escalating cost, team leader
count, reductions and the resource substitution from a relic. The current native
cost function returns one Food or Money entry. The readable tool preserves its
array shape; temporal encoding explicitly rejects an unsupported cost shape or
resource so it cannot silently misrepresent future game changes.

State and remaining time getters resolve shared team feasts through the native
team leader logic. Null remaining time before the first feast becomes zero.
Time is measured in simulation seconds, so pausing prevents its countdown.

## Live validation

The initial read returned no active feast, zero remaining time, a100-food cost
and can_feast=true. A single paid action reduced Food from500 to400 in the same
stopped frame. Native state immediately showed an active feast with60 seconds
remaining, a next cost of150 Food and can_feast=false. A duplicate action raised
`A feast is already active.` before the RPC. Temporal extraction returned nine
values with the expected resource flags, next cost and active state.

Captures: `artifacts/runs/feast-live-preview.json`, `feast-live-start.json` and
their stderr logs. The logs show native calls restoring normally. Python/JSON
syntax, CLI help and the existing native contract allowlist check passed.
No automated tests were added. Free feasts, Money costs, shared team feasts,
expiry and bot execution have not been validated live.
