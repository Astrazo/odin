# Construction staffing and building identity investigation

## Why retain explicit worker selection

Worker allocation has an economic cost. Even a villager gathering Food gives
up production while travelling and building. If no suitable villager is
available, choosing between waiting and diverting a specialist changes which
resource production is interrupted. A nearest-worker rule cannot express that
tradeoff on its own.

We are keeping profession/zone assignment, the internal ID map and construction
staffing observations so the policy can make that choice. Native assignment
validation still decides which workers are eligible. A deterministic selection
rule can be compared later as a baseline; it is not the default introduced here.

This is a design hypothesis, not evidence that the extra inputs improve wins.
The practical checks are whether worker choices change under different resource
shortages, whether sites get completed, and whether the economy and eventual
game results improve relative to the simpler baseline. Further observation
detail needs a concrete decision it enables before we add it.

## Implementation update — 21 October 2026

The worker source zone is optional. With `--from-job` but no `--from-zone`,
assignment and preview use the target building's current zone. An explicit
source zone overrides that default. If the local worker group is empty or
ineligible, no worker from another zone is substituted. Semantic destinations
still require `--zone`; numeric building UIDs provide their own zone.

Both worker and destination resolution are implemented in `actions/workers.py`.
`assign --from-job PROFESSION --from-zone SOURCE --building FAMILY --zone TARGET`
resolves both current native identities. Add `--construction` to select an
unfinished site; completed buildings are the default. It prefers unstaffed
construction, then uses building UID and worker UID order among eligible pairs.
It never substitutes another family, destination zone, construction state,
profession or source zone. Fresh resolution handles completion's UID change
without accidentally treating a completed building as the requested construction.
This keeps the economic choice at the profession/zone level without adding
per-worker numeric features. Read-only preview supports the same selector and
existing-site assignment supports bot selection. A read-only live check on
21 October failed during debugger initialization in the sandbox; the retry
outside the sandbox timed out during attach. No assignment was sent, so native
validation of semantic targeting remains pending. No automated tests were added
for this work, per the project workflow.

The stale adapter connection was subsequently cleared after verifying that
Northgard had no active Windows debugger. Read-only listings now work. The
current match has a completed ScoutCamp and villagers in zone39. The subsequent
semantic preview was not run because permission was declined, so pair selection
and dispatch remain unverified live. Misspelled CLI professions are now rejected
before opening the debugger, with a spelling suggestion where possible.

Build and assign are separate actions. Build places a site without an Odin
worker order. The game can automatically staff it when simulation advances.
The next observation exposes remaining unstaffed sites; the policy can choose
to wait or send a separate profession/zone assignment. No automatic fallback
assignment is scheduled. The earlier combined-action path has been removed.

The investigation below describes the original behaviour on 20 October. The
current implementation provides:

- `build --zone ZONE --building FAMILY` / `NorthgardEnv.build(zone, family)`
  only place the selected building. Assignment uses the separate resolver and
  normal native validation/dispatch path.
- Site identity is resolved from the before/after zone UID sets, accepting only
  one new Construction with the requested exact engine kind. Placement is
  invoked once. Unknown/ambiguous identity leaves the placed result intact with
  an error field and no confirmed construction UID. There is no automatic retry.
- Build returns placement and site identity only. Staffing is read through
  observations; it does not trigger an Odin assignment automatically.
- Owned construction IDs and assigned unit IDs appear in
  `zones.construction_sites`. Numeric `unassigned_construction_<family>` counts
  and summary fields make missing explicit assignments visible per zone.
- Assignments are collected from living owned units across all zones, so a
  worker ordered from another zone does not look absent. This reads `assignTo`,
  not current activity, progress or native path success. Automatic assignment
  may appear on the next simulation update, especially after a paused placement.
- Each observation reads fresh site identities; completion removes the old UID
  from construction targets. No persistent completion tracker is implemented.

The existing assignment action remains available for a later policy decision.
The learner, candidate-slot action encoding and reward function are not yet
implemented. Site counts are numeric policy inputs; runtime UIDs are target
identities rather than meaningful scalar features. Building progress, linked
job state, confirmed arrival, eligibility masks and path-cost ranking remain
future work. Live placement/remote-worker/completion validation remains pending;
no Northgard process was available during implementation.

## Original investigation

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

## Observation follow-ups from the investigation

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

Keep placement and existing-site assignment separate. One decision chooses the
building family and destination zone. After simulation advances, a later policy
decision can choose a worker profession and source zone for an unstaffed site.
The resolver translates that group into a current eligible worker UID and sends
the normal assignment. It does not place another building, schedule a fallback
or decide that waiting is wrong. Missing workers do not invalidate a legal
placement; an unavailable assignment group is reported by the assign action.

The proposed eligibility reads have inspected native candidates:
`Unit.get_isVillager` f4239, `Unit.isControlable(null)` f4275 and
`Unit.canGoTo(zone, null)` f4068. These are not newly enabled by this investigation.
Existing `Building.canAssignTo` and `ScriptApi.assign` remain the normal site
validation/dispatch route. Full route-cost ranking, role-change semantics and a
live remote-builder/completion lifecycle test remain to be established.
