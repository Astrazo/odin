# Semantic group movement

`move --from-zone SOURCE --to-zone TARGET --who SELECTOR [--count N]` covers
evacuation, repositioning, reinforcement and sending fighters into a hostile
zone. The policy chooses the group and destination; runtime IDs, unit targeting
and walking remain internal to execution and the ordinary game simulation.
No new numeric observation features or automated tests are introduced.

## Native evidence

Inspected the installed bytecode pinned by `supported_build.json`, guided by
the previous project's scout and stopped-AI notes. Disassemblies and metadata
are in `artifacts/runs/movement-*` and `inspect_move*.cjs`.

| Operation | Inspected native function |
|---|---|
| Fighter classification | Unit.get_isFighter, f4225, `(Unit) -> Bool` |
| Controllability | Unit.isControlable, f4275, `(Unit, Ref<Bool>) -> Bool`, null optional argument |
| Route/entry validation | Unit.canGoTo, f4068, `(Unit, Zone, Null<Int>) -> Bool`, null optional argument |
| Normal move | Unit.moveToZone, f4415, `(Unit, Zone, Bool, Virtual, BaseUnit) -> Void` |

The f4415 debug argument names are `zone`, `canAttack`, `position`, `target`.
It constructs UnitAction.MoveTo and calls Unit.action f4279, which dispatches
the normal actionImp RPC f4595 to the authoritative implementation f4280.
The MoveTo branch (Unit.hx 5053–5075) checks path eligibility, clears assignTo
and vars.linkedBuilding, calls UnitJob.goto f15073, and applies canAttack (with
native definition-flag exceptions). The ordinary AI zoneMove f5405 uses the
same enum with canAttack=true. Scouts currently use false.

Odin uses true for native fighters and false for other selected units. It does
not invoke the strategic clan AI or choose combat targets. Automatic combat
remains normal unit simulation, independent of stopping the stock AI order loop.
Actual hostile engagement and retreat behaviour still need live confirmation.

## Resolution and reporting

Use the current owned unit job map, filtering by physical source zone and
profession (or all/military). `military` checks the engine's fighter predicate,
including any mapped or unmapped owned type it classifies as a fighter. Native
controllability and route checks exclude unsuitable units before selection.
UID order is only an internal deterministic tie-break.

The destination is resolved by traversing discovered neighbours starting from
owned territory and the selected unit's zone. Owned roots let a scout return
home even while its current zone is not fully revealed. No buildings, units or
other contents of hidden zones are read. This works for selected bots without assuming the local
player's discovery or ownership. Native rules determine access to neutral,
enemy and allied zones; a discovered destination alone is not sufficient.

An explicit positive count must be satisfiable before dispatch; omission uses
all eligible units. The preview shares the same resolver and sends no orders.
Dispatch follows the existing authoritative-offline and paused/stopped-AI bot
guards. Unit UIDs are resolved again for each order. There is no simulation
advance between preflight and dispatch.

Already-heading units with compatible combat behaviour count towards selection
without resending the same order. New orders are confirmed from goingTo or an
immediate destination-zone link. Unconfirmed state stops the cohort; the result
retains earlier successes and lists not-attempted units. Batch movement is not
atomic and is never automatically retried or rolled back. Order confirmation
is not an arrival or combat-success signal.

## Validation

CLI registration, argument validation, Python/JSON syntax and the existing
native allowlist expectation are checked. No new automated tests were added.

The current live match has owned zone30, Scout1149 in zone45, Warrior1152 in
zone30 and civilian workers in zone30. A military preview from30 to45 was
rejected because zone45 was not fully discovered. No move order was sent.

The read-only preview `--from-zone 45 --to-zone 30 --who scout --count 1`
succeeded, selecting Scout1149 with all three new native predicates executing
and restoring normally. This also verified that an owned scout in an unrevealed
source zone can be resolved back to discovered home territory without exposing
the source's hidden contents.

A real move invocation requesting two scouts for that same route was rejected
before dispatch: one scout was eligible. The native call log contains no
unit_move_to_zone invocation. No gameplay move was sent, no building assignment
was interrupted, and Northgard remained running after normal detach. Captures:
`artifacts/runs/movement-live-preview.json`, `movement-live-preview.stderr.log`
and `movement-live-blocked.stderr.log`.

Successful dispatch/arrival, hostile fighter engagement, civilian evacuation
and return/reassignment, mixed groups, and bot movement remain unverified live.

### Military route rejection

A later live check confirmed Warrior1152 in zone30 is classified as military
and controllable, but the native route check rejects zone45. Zone30 connects
directly to zones36,39,35. All three pass the warrior's route check; zone39 is
hostile and connects to zone45. Zone45 is now discovered and hostile, but remains
unreachable from30. The inspected PathComponent.canWalkThrough (f15130) prevents
ordinary units passing through hostile fighters in neutral territory; military
can enter the blocking zone to fight there. Clear the approach before requesting
movement beyond it. A scout reaching45 does not establish a military route.

The command now identifies route-rejected unit professions and UIDs in its
error, rather than only saying there are no eligible units. Read-only captures:
`artifacts/runs/movement-rejection-preview.json` and
`artifacts/runs/movement-rejection-details.json`. No movement orders were sent.
