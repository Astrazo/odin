# Villager assignment crash investigation

20 October 2026. The user reports stability after the debugger-disconnect race
fix. Assignment now uses `ScriptApi.assign` again and supports an explicit
acting player. A live paused bot test confirmed the order and immediate link;
travel and work after unpausing remain unmeasured.

## Script assignment restored with selected-player support

At the user's direction, `ScriptApi.assign` f11737 replaces the temporary
`GameLogic.assign` f12262 route. Both reach `Unit.action`; the UI origin alone
was not evidence of a local-player restriction. The definite restriction was
Odin's fixed `this.state.me` lookups. Assignment now resolves an optional player
UID from `GameState.players.array` and carries it through unit lookup, zone
lookup, ownership validation and post-call confirmation. The default remains
the local player. The unused f12262 contract is removed.

Bot dispatch requires the authoritative offline host, normal pause, an AI job,
owned territory and `skipAIOrder=true`. Separate `ai-stop`/`ai-resume` commands
use the inspected f5216 setter, report the prior gate, verify read-back and
avoid redundant writes. Listing and preview commands do not change AI state.
Player selection is also available to the unit/zone and building ID tools.
Build/scout and observation context migration are outside this assignment change.

### Live result in the current match

The running authoritative offline match was already paused. Player UID31 was
Harald (local); UID61 was Gunnar (bot). Gunnar's initial `skipAIOrder` was false.
Preview accepted free Villager UID1195 and completed Scout Camp UID1282 in
Gunnar-owned zone36. One bounded test then:

1. Set Gunnar's AI gate false → true and verified it.
2. Called f11737 once with Gunnar's actual unit and building references.
3. Received `assigned: true` and `assignment_observed: true`.
4. Restored the AI gate true → false and verified it.
5. Confirmed normal pause remained in effect and detached successfully.

Northgard PID27540 was still running after detach. Evidence is in
`artifacts/runs/bot-assignment-validation.json` and
`artifacts/runs/bot-assignment-validation.stderr.log`; the latter records normal
restoration of f11737 and both AI setter calls. This establishes an accepted
bot-owned order and immediate link in a paused match. No game-time advancement,
arrival or ongoing production was tested. Gunnar's stock AI is enabled again
and can make new decisions after unpausing.

The first read-only attach from the sandbox failed before native attachment;
its adapter was cleaned up after confirming `DebugActiveProcess` had returned
false. The successful inspections and bounded action used elevated process
access. No human-player assignment or resource change was requested.

Validation: 65 Python tests and all four Node suites pass, covering actor
selection, foreign ownership, absent/duplicate players, active AI refusal,
host/mode checks, script presence, single dispatch, failed results/read-back,
AI stop/resume and CLI forwarding. The debugger race fixes are retained.

## Follow-up: building command also closes Northgard

After the first bridge changes, the user reported that
`uv run odin build --zone 35 --building scout_camp` printed `requested: true`
and Northgard then closed. This expands the failure beyond explicit worker
assignment. The latest game log, `northgard-debug-20261020-151716-769390.log`,
has no crash trace, and no newer Northgard dump or matching recent Windows
Application Error event was found.

Inspection found a concrete shutdown race in `NativeRuntime.close()`:

1. Python requests DAP `disconnect` and waits for its response.
2. The installed adapter's `disconnectRequest` sends that response **before**
   calling `stopDebug()`.
3. Python receives it and immediately calls `self.process.terminate()`.
4. If Node has not yet completed `DebugActiveProcessStop`, it exits while it
   still owns the Windows debug connection to Northgard.

The installed addon's `src/debug.c` uses `DebugActiveProcess` without changing
kill-on-exit behavior. Windows defaults to terminating attached processes when
their debugger exits; see [DebugSetProcessKillOnExit](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-debugsetprocesskillonexit).
This supplies a direct mechanism for an accepted command followed by the game
disappearing without an application crash dump. It is a stronger explanation
than the earlier GC hypothesis, although the user's exact failure has not yet
been reproduced under instrumentation.

The old one-shot bridge in `northgard-god` waited for adapter exit and left it
running on timeout after an attach attempt. Odin instead terminated it
immediately. This lifecycle difference was more consequential than the first
investigation established. It affects all commands, including read-only ones.
Another game's load could change scheduling enough to expose this race; no
direct interference from that game has been established.

The fix defers the disconnect response until the adapter's cleanup completes,
checks the native detach Boolean that the stock wrapper ignored, and lets Node
exit normally after Python closes its input. Forced adapter termination is
allowed only before an attach attempt or after confirmed detach. Failed detach
leaves the adapter alive with its PID reported. The adapter also blocks its
automatic shutdown on pipe loss while a debug connection or unconfirmed native
recovery remains.

Regression tests reproduce the stock response-before-detach order and verify
that native detach now precedes acknowledgement, failed native detach produces
no success response, attached shutdown is blocked, and Python does not kill
the adapter on a disconnect failure. All four Node suites and all 46 Python
tests pass. An adapter-only smoke check also loaded the actual installed adapter,
completed DAP initialization, and exited normally in 0.117 seconds without
attaching to a game. No Northgard process was available for the live check.

The RAX and EFLAGS changes below remain separate corrections; the first
investigation did not establish either as the cause of the reported exits.

## Existing evidence

The prior investigation is in
`C:/Users/Josh/Repos/northgard-god/docs/experiments/WORKER_ASSIGNMENT_EXPERIMENT.md`.
It records post-call crashes through both `ScriptApi.assign` f11737 and
`GameLogic.assign` f12262, including accepted Scout Camp and Woodcutter Lodge
orders. The latest reported UI-route attempt returned true and immediately
confirmed `unit.assignTo == building`, then crashed after continuing. Same-zone
assignment also failed. Automatic construction staffing worked.

Those results rule out treating legality, cross-zone movement, or the script
callback alone as the explanation. An immediate successful Boolean/link does
not establish that the game can safely continue after the bridge call.

Odin's logs in `artifacts/runs/northgard-debug-*.log` contain startup/network
messages and map generation, but no assignment crash stack trace. The existing
working tree already uses the UI route, validates the pair with
`Building.canAssignTo`, and checks the immediate assignment link. Those changes
were preserved.

## Missing RAX root in the native call stub

`src/odin/native/win64_call.js` saved RCX, RDX, R8–R11 and XMM0–5 on the target
stack, but not the interrupted frame's RAX. The bridge copied RAX into Node's
JavaScript memory, then the stub reused RAX to call the requested function.

HashLink's collector scans target thread stacks and saved runtime registers;
it cannot see the debugger's JavaScript snapshot. If the interrupted frame's
only reference to a managed object is in RAX, an allocating call can lose that
root. Restoring the old numeric register value afterwards cannot resurrect a
collected object. This is a concrete preservation gap and a plausible mechanism
for failure after a successful allocating action. It is not proof that an actual
assignment triggered collection or that RAX held the affected object's only root.

The stub now pushes the original RAX before argument setup and keeps it outside
callee shadow space. After the call it discards that slot while retaining the
return value in RAX; the bridge still reads the result and restores the original
register. Stack alignment and saved-byte accounting include the extra slot.

Reference: [HashLink 1.16 collector](https://github.com/HaxeFoundation/hashlink/blob/1.16/src/gc.c),
especially `gc_save_context`, `gc_mark_stack`, and `gc_mark`.

## Incorrect single-step register

The bridge tested bit `0x100` in adapter register 4. The installed, hash-checked
adapter defines register 4 as DR0 and register 3 as EFLAGS. This could miss real
single stepping or spuriously reject a normal call based on a breakpoint address.
The bridge now uses `Register.EFlags`, matching the adapter's own evaluator.
This defect is independent of proving the assignment crash's cause.

## Correction to the previous dump interpretation

Read-only inspection of
`C:/Users/Josh/AppData/Local/CrashDumps/Northgard.exe.14552.dmp`
(20 October, 09:26:56) confirms exception `0x40000015`, exception thread 7576,
and exception address `OpenAL32.dll+0xd9076`.

The previous note's `RIP = 0xAAAAAAAAAAAAAAAA` claim is not supported by the
AMD64 context at the exception stream's ThreadContext RVA. The stream stores
the context size/RVA at offsets 160/164. At AMD64 CONTEXT offset 248, RIP resolves
to `msvcrt.dll+0x32572`; RSP at offset 152 is `0x69ced15e60`. The separately
captured thread-list context has RIP `ntdll.dll+0xa1954`. Both are valid module
addresses. See Microsoft's [exception stream layout](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_exception_stream)
and [AMD64 CONTEXT layout](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-context).

A raw stack scan also finds `libhl.dll+0x37a0e`, which the installed DLL's export
table places 30 bytes into `hl_sys_exit`. A stack scan is not an unwound call
trace, but this is consistent with a shutdown-time failure. The dump does not
establish corrupted control flow, an audio cause for assignment failures, or
even a direct association with the later assignment attempts. Preserve it as
secondary evidence rather than using it to choose an action workaround.

## Verification and next live check

- Both new regression checks failed against the original implementation.
- All four Node test files pass. The byte interpreter verifies the original RAX
  remains on the active target stack at CALL, alongside its existing checks of
  0–16 mixed arguments, alignment, shadow space, return bits and restoration.
- All 43 Python tests pass. The suite needed execution outside the sandbox
  because the PAK fixture's temporary directory was inaccessible inside it.
- No Northgard process was running during investigation. No game was launched
  or debugger attached, and no assignment was dispatched.

The next decisive check requires a running match: preview one free villager and
one completed ordinary work building, issue one assignment, retain native-call
stderr and game output, and observe continued gameplay after detach. If it
still exits, capture the first exception and its stack before shutdown, and
record whether a GC ran during the native call. Do not infer stability from
`assigned: true` alone. There is no live evidence yet that these fixes eliminate
the reported crash.
