# Colonisation action

20 October 2026. Read-only listing/preview tested live. Paid dispatch is
implemented and tested offline; a live start/completion test remains pending.
Existing debugger detach/race fixes are retained.

## Native path on the supported build

Inspection used the installed `hlboot.dat` and hash-recorded debugger adapter;
the supported hashes remain in `src/odin/data/supported_build.json`.

| Function | Signature including receiver | Purpose |
|---|---|---|
| f14622 `WorldComponent.getNoColonizeReason` | `(WorldComponent, Zone, ColonizeTestType) -> NoColonizeReason` | Complete native rejection reason for the selected player/mode |
| f14618 `WorldComponent.colonizeCost` | `(WorldComponent, Zone, String, Ref<Bool>, Ref<Bool>, Null<Bool>) -> virtual {opt, qty, res}` | Native cost; optional arguments supplied as null |
| f14688 `WorldComponent.startColonize` | `(WorldComponent, Zone, Bool callback) -> Void` | Public RPC; only a null callback is permitted by the bridge |
| f14623 `WorldComponent.startColonize__impl` | `(WorldComponent, Zone) -> Bool` | Engine implementation reached through the RPC; not directly allowlisted |

The public wrapper routes through hxbit and calls its implementation on an
authoritative host. The implementation determines the cost, calls `canColonize`
with `ColonizeTestType.Res(cost.res)`, uses the player's resource component to
pay, and sets `zone.colonizeBy` to that player. Python sends no synthetic
callback and does not modify ownership, progress, resources or network fields.

`ColonizeTestType` has `Res(String)`, `CurrentRes`, `Dominion` and `Purify`.
Preview explicitly passes the existing native `CurrentRes` enum constant. The
validator expands it to `Res(colonizeCost(...).res)` before its affordability
and resource-specific cooldown checks. **Null is not an equivalent full check**:
it skips the resource switch in `getNoColonizeReason`. The bridge now supports
pointer-shaped enum values (kind18), plus function arguments (kind10) constrained
to null in this RPC's contract. No enum or callback is allocated by Python.

`ScriptApi.colonize` f11674 was deliberately excluded. It calls `$Debug.colonize`
f19499, which can discover the zone and invoke `Zone.takeControl` directly. That
is a scenario/debug takeover rather than the normal paid colonisation request.
Neither debug function is allowlisted; regression checks enforce this.

## Selection and command behavior

An optional `--player` resolves the current player UID through the existing
player selector. Without it, the command uses `this.state.me`. Traversal starts
at that player's owned zones, validates root ownership, and considers only
immediate neighbours discovered by that same player and with no player owner.
Hidden neighbour IDs, owner details, costs and contents are not inspected.
Repeated borders are deduplicated and their visible source IDs are merged.

The tool returns `colonisable_zones` and `blocked_zones`. Each entry includes
`zone_id`, `adjacent_to`, `can_colonise`, the raw native reason (or null), and
`cost: {resource, quantity}`. Reasons such as `Occupied`, `MissingResources`,
`LonelyZone` and `NearbyAttack` come from Northgard rather than Python guesses.

Dispatch requires an authoritative offline match. For a non-local player it
also requires normal pause, an AI job, owned territory and stopped stock AI
orders. The chosen border and full native validator are checked again in the
current stopped frame before sending one RPC. The RPC revalidates and pays the
cost internally. No retries are made. Success requires `colonizeBy == player`
or immediate ownership. This confirms acceptance/start, not timed completion.

The implementation uses the current native resource mode; choosing alternate
payment modes, distant/special expansion paths, cancellation, and observation
tensor integration are outside this change. The listing is the current action
mask source for manual/agent tool use.

## Verification

Offline tests cover costs, full-mode reason selection, blocked and hidden
targets, owned/non-border rejection, duplicate borders, selected bot context,
active-AI/pause/authority/multiplayer rejection, exactly one public RPC,
immediate start/ownership confirmation and no retry on unconfirmed results.
CLI tests verify the command/preview/listing forward the selected player.

The read-only tool completed a live attach/read/detach in the current match.
It reported zones85 and92 next to owned zone97 as legal, each at Food20;
zone89 was blocked with `Occupied`. Normal-restoration records include f14622
and f14618. Evidence: `artifacts/runs/colonisation-preview.json` and
`artifacts/runs/colonisation-preview.stderr.log`.

No colonisation was dispatched and no resources were spent during that check.
The next live proof should use an explicitly chosen currently legal border,
record the selected player's stocks and native cost, send one request, confirm
the immediate link and payment, then observe completion after normal play
resumes. Re-list candidates rather than treating the recorded IDs/cost as fixed.
