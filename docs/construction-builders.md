# Construction staffing and building identity investigation

20 October 2026. This is an investigation and design recommendation, not a
change to build behaviour. No new game orders, placements, worker transfers or
native allowlist entries were added. No Northgard process was available for a
live construction/completion test during this investigation.

Inspection used the installed bytecode and recorded debugger adapter for the
hashes in `src/odin/data/supported_build.json`. Function IDs below apply to that
build. Disassemblies and inspection scripts are in `artifacts/runs/construction-*`
and `artifacts/runs/inspect_construction*.cjs`.

## What Odin currently does

`build_building` validates an owned zone, resolves the available engine definition,
and invokes `Tools.buildInZone` f26048 once with normal placement/construction
defaults. Its response only reports the requested zone/family/engine ID and
`requested: true`. It does not return the construction UID, observe a builder,
or promise construction will progress.

`NativeRuntime.call_native` retains only DAP's formatted result string. The native
helper returns an actual Building object, but that object's identity is not
currently carried into the Python action result. The existing zone observation
counts completed buildings and construction by semantic family; it does not
expose per-site progress, assigned/incoming builders or a persistent request ID.

Consequently the current model can see that a construction exists, but lacks the
details needed to choose between waiting, moving a villager and reallocating a
specialist. Placement success alone is not a staffed-construction result.

## Native local staffing is asynchronous and limited

The Building constructor f12538 calls `Building.wakeupVillager` f5921 under
game/clan/mode conditions (Building.hx lines218–222).

`wakeupVillager` (Building.hx lines7045–7071) filters candidates by unit kind,
assignment/action state, definition flags and matching owner, and selects a
nearby candidate using world-coordinate distance. Its ordinary search starts
from the site's `zone.units`; a branch using particular player local flags
instead searches the owner's units. The meaning and applicability of those
flags must be established before relying on that broader branch for normal
human/bot play. It is not safe to promise global builder dispatch from this
method alone.

The method sends a normal unit action with a callback that reaches
`Player.unitCommand` (callback f22546). It does not directly set a worker's
assignment to this particular site in the placement call.

`UnitJob.autoAssign` f15062 is a separate job-selection stage. Its selection
closure f36987 searches `u.zone.buildings`, first considering the prior
assignment and then distance among eligible local buildings. On selection,
f15062 sets `assignTo` and, where applicable, `vars.linkedBuilding`. It is called
from normal job choice/work paths, including f15054 and f15067.

Implications:

- A local villager can begin building after subsequent simulation updates even
  if no assignment is visible immediately when placement returns.
- A newly placed site with no immediate link is not sufficient evidence of
  failed automatic staffing, especially when the match is normally paused.
- Ordinary local job choice is not a service for finding a villager in another
  zone and transporting it to a new construction site.
- A fallback that assigns another worker immediately can compete with normal
  job selection. An explicit chosen-builder command and a later automatic
  staffing check should have distinct, documented behavior.

## The stock AI has a separate logistics decision

`AIJob.checkConstruction` f5389 (AIJob.hx lines670–694):

1. Walks its player's zones and finds construction zones without builders.
2. Checks hostility and whether a builder is already travelling there.
3. Finds a movable unit using the AI's villager-kind setting.
4. Calls the AI's normal zone-move routine for the selected candidate.

The inspected call chain is `regularUpdate` f5377 → `checkOrders` f5379 →
`extraOrders` f5393 → `checkConstruction` f5389. The main `skipAIOrder` gate is
before this work in f5377. Therefore stopping the stock AI for model control
also removes this route's help with remote construction staffing. That does
not disable ordinary unit jobs or all possible AI/event callbacks.

Calling this stock AI routine as Odin's generic fallback would import its
candidate-selection and economic decisions. It is useful evidence of how the
game handles incoming builders, but should not silently substitute for the
policy's worker-allocation decisions.

## Completion really replaces the object

The normal construction-work callback f36994 (inside `UnitJob.buildJob` f15064)
removes the old building with `Entity.remove` f2992 at UnitJob.hx line3326.
It then calls `Player.createBuilding` f5038 at line3327 and writes the returned
replacement into the job's captured building reference.

`Player.createBuilding` (Player.hx lines6170 onward) reads the old site's
`realInf.id`, coordinates, flip state and construction arguments, creates fresh
building state, and invokes the Building factory f12534. This confirms the
user's observation: the completed building must not be identified by the old
construction UID. This is an actual replacement, not merely a display-name
change from Construction to the completed kind.

The native job owns its reference transition. Odin should assign a builder to
the construction site's current UID and let that normal job run, rather than
attempting to reassign against the disappeared UID after completion.

If Odin needs persistent completion tracking, use an Odin request/task handle
separate from native UIDs. Record the construction UID, owner, zone, requested
engine kind and placement coordinates. Resolve a replacement from fresh state
with those attributes, accepting only an unambiguous match. Site disappearance
alone could also mean cancellation, destruction or lost visibility. Never pick
the first completed building of the same kind in a zone.

## Revised decision boundary

The earlier suggestion to mask all construction whenever no free villager
exists was too restrictive. Building legality and builder availability are
different questions. A policy can rationally place a site now and staff it later.

Also, unassigned does not mean economically costless: an ordinary villager may
be gathering Food. The model needs the current work/resource context even when
a worker has no building assignment.

Recommended responsibilities:

| Decision | Responsibility |
|---|---|
| Where/what/when to build | Model policy |
| Which worker to divert, or whether to wait | Model policy |
| Native eligibility, ownership, path feasibility and command dispatch | Odin execution layer |
| Walk to an assigned construction and perform normal work | Native unit/job systems |
| Normal completion and replacement object creation | Native construction system |

An optional nearest-free heuristic is a useful baseline or explicit convenience
mode, not a universal rule. It should exclude existing building assignments,
linked/incoming work and active orders, and check native eligibility and
reachability. Straight-line distance is only an approximation to travel time;
the fact that a worker is in a neighbouring zone does not prove a cheap/safe
path. A busy worker's eligibility to build/retrain must come from the game's
validator, not an assumption that every civilian specialist is interchangeable.

## Suggested next implementation, not yet applied

First expose construction and worker information without changing allocation:

- Capture and return the actual new construction UID and placement metadata.
  Retain the existing DAP evaluation result/reference or inspect the before/after
  zone UID set. Do not re-evaluate `Tools.buildInZone(...)` to read a field: that
  would place another building.
- Expose each site's actual kind, desired completed kind, progress and assigned/
  linked/incoming worker IDs. Distinguish `awaiting_assignment`, `builder_incoming`,
  `building` and verified completion; do not infer these from counts alone.
- Expose candidate worker IDs, current role/job/resource, location, current
  assignment/link, active movement/order state and verified eligibility/path
  feasibility. Candidate ranking can start with a labelled distance estimate;
  avoid claiming it is the shortest native route.

Then support an explicit chosen builder as an optional argument to build. One
policy decision can choose `(zone, building family, worker ID)`; Odin places
the site once and issues the normal assignment to that returned site. After
placement, assignment can still fail, so report `placed` and `builder_assigned`
separately and never repeat placement as a retry.

Keep site-only placement and existing-site assignment available. They allow the
model to wait or reallocate a worker later without deciding to place the same
building again. Any eventual free-worker convenience mode should return a clear
`needs_builder`/pending result when no candidate is available; it should not
silently steal a production worker, reject an otherwise legal build solely for
that reason, or claim the construction is staffed.

The proposed eligibility reads have inspected native candidates:
`Unit.get_isVillager` f4239, `Unit.isControlable(null)` f4275 and
`Unit.canGoTo(zone, null)` f4068. These are not newly enabled by this investigation.
Existing `Building.canAssignTo` and `ScriptApi.assign` remain the normal site
validation/dispatch route. Full route-cost ranking, role-change semantics and a
live remote-builder/completion lifecycle test remain to be established.
