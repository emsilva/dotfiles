# Relay gate: design (piece 2 of 2, the 50% trigger)

Piece 1 (`2026-10-12-session-relay-design.md`) built `/relay`: a lead hands its work to a successor in a new herdr
pane, which picks up, takes over and closes the old lead. Nothing fires it on its own. This piece fires it.

## Goal

A herdr lead relays itself when its context reaches 50%, at the first safe point, with no owner and no external
watcher. It never kills work to do so, never loops after a failed relay, and tells the owner when it cannot relay.

Success: a lead left running overnight runs `/relay` at its first safe turn end at or after 50%, without nudging
from anyone, and a failed relay costs at most one automatic retry. The 30-minute watch loop becomes unnecessary.
One long turn can still overshoot: the measured worst case went from 70.5% to 83.8% inside a single 40-minute turn.
The mid-turn nudge aims to shorten such turns, but the probe showed the model does not obey it within the turn, so
nothing here relies on it.

## Owner decisions (2026-10-13)

- **Scope: herdr leads only.** A session is a lead when its herdr pane name starts with `lead-`, or (fast path,
  works while herdr is down) its session id is the project's `relay/lead.json`. Every relayed successor already
  carries a `lead-` name. A lead started by hand must be named `lead-<project>` at start. Workers are never
  blocked, nudged or alerted (the herd rules `/clear` them at about 40%); they pay a hook start per tool call, and a
  failure of the hook itself raises its one tooling toast in any session, workers included (Error handling).
  Subagents, workflow children and teammates are excluded. **One lead per project**: piece 1 names successors
  `lead-<slug>-next` and `lead-<slug>`, and herdr names are unique.
- **Not safe at the cap: keep waiting and alert.** Past 50% the lead is told to start nothing new in-session and
  drain. At 60% and each further 10 points, still unable to relay, the owner is alerted. The gate never stops a
  subagent or a run to force a relay.
- **Back-off: one retry, then alert.** After a failed relay, one automatic retry after 30 minutes; after a second
  failure the gate stops asking for that session and alerts the owner, who retries with `/relay`. A failure that
  will repeat identically (an identity mismatch, a taken agent name) skips the retry. A failure at the hand-over
  stage never retries: the old lead is frozen holding the record until the owner decides.
- **Alerts: toast and push.** A herdr toast raised by the hook, the message in the lead's pane, and a push
  notification the lead sends so it reaches the owner off-terminal.
- **Approach B:** a Stop gate that enforces at turn end, plus an advisory nudge after tool calls.
- **An owner conversation defers the ask** (coordinator's call, 2026-10-13, from the research's finding that
  relays landed mid-interview): a typed prompt in the last 10 minutes holds the ask until 60%. Prompts typed by
  herdr count too, because the transcript cannot tell them apart.
- **Deployment waits for the owner** (coordinator's call while the owner was away, 2026-10-13): registering the
  hooks in the live `~/.claude/settings.json` puts the gate in every running session, and that file has drifted
  from its chezmoi template in both directions (`chezmoi status` shows `MM`). The build is tested with per-session
  `--settings`; the owner switches it on.

Earlier owner decisions still hold: 50% is the only automatic trigger (no unit-of-work relays); long work runs
detached with an exit-code file; a lead never compacts instead of relaying.

## Measured facts (probes 2026-10-13, Claude Code 2.1.296, herdr 0.9.2-preview)

Three scratch sessions ran with logging hooks on Stop, SubagentStop and PostToolUse
(`~/code/claude/tmp/relay-gate-probe/`, `hooks-run1.log`, `hooks-run2.log`, `hooks.log`). The first ran a Bash call
and one subagent; the second started a background Bash task and a Monitor; the third ran a subagent and an
in-process teammate.

- **Stop fires for the main thread only.** A subagent's end fires SubagentStop. Hidden internal agents also fire
  SubagentStop (empty `agent_type`).
- **Subagent tool calls fire PostToolUse with `agent_id` and `agent_type`**, the parent's `session_id`, and the
  parent's `transcript_path`. The transcript path therefore cannot tell a subagent from the lead; `agent_id` can.
- `HERDR_ENV`, `HERDR_PANE_ID`, `CLAUDE_PID` (the main claude process) and `CLAUDE_EFFORT` are set in hook
  processes. **`CLAUDE_CODE_CHILD_SESSION` is `1` in every hook process**, the main thread's Stop included (third
  probe), and in the lead's own Bash shell: it marks any process Claude Code spawned, not a subagent, so it cannot
  identify one.
- **Stop input carries `background_tasks`**, live: `[{"id", "type", "status", "description", …}]`. A running
  subagent appears as `"type": "subagent"` while it runs and is gone after; a `run_in_background` Bash task and a
  Monitor both appear as `"type": "shell"` with their `command`; a running in-process teammate as
  `"type": "teammate"`. A teammate's tool calls carry an `agent_id` (`a<name>-<hex>`) and its end fires
  SubagentStop, like a subagent's. Also `session_crons`, `stop_hook_active`,
  `prompt_id`, `last_assistant_message`.
- **A Stop `{"decision": "block", "reason": …}` works:** the model continued and did what the reason said. The
  next Stop had `stop_hook_active: true`. The pane shows the block as "Stop hook error occurred"; the transcript
  records it as a `hook_blocking_error` attachment.
- **PostToolUse `additionalContext` is delivered** (a `hook_additional_context` attachment), but the model did not
  follow it in that turn. It is advisory; only the Stop block enforces.
- **`herdr notification show` from a hook works** (exit 0).
- **Each notification turn has a new `prompt_id`** (`225a8494` → `cdddf6d0`), so no per-prompt counter can stop a
  loop: the gate's memory must persist across turns, in a file.
- **The transcript is flushed before Stop runs:** on three Stops the newest main-thread assistant record (with its
  usage) ended exactly at the file size the hook saw, and its text matched `last_assistant_message`.
- `PushNotification` is a deferred tool: its schema must be loaded with ToolSearch before the first call.
- The meter (previous research, re-derived twice): fill = input + cache_read + cache_creation of the **last
  `usage.iterations` entry of type `message`** on the newest main-thread assistant record, over a 1,000,000-token
  window for `claude-opus-5-5`. The top-level usage doubles on advisor turns. An Opus session starts at about 5%.
- Cost: `herdr agent get <pane>` 0.10–0.22 s; a full parse of a real 10 MB lead transcript 0.05 s.

## Design

### Parts

| Part | Where | What |
|---|---|---|
| `relay-gate.py` | `scripts/` of the session-handoff skill | the hook: `stop` mode (gate) and `tool` mode (nudge) |
| `transcript.context_fill()` | `scripts/transcript.py` | the meter, shared by both modes |
| `transcript.WINDOWS` | `scripts/transcript.py` | context window per model id |
| `relaylib.blockers()` | a shared module in `scripts/` | the safe-point rules `relay-check.py checklist` and the gate both use |
| gate state | `<project>/relay/gate/<session-id>.json` | per-session memory, leads only |
| registration | `~/.claude/settings.json` (owner) or `--settings` (tests) | Stop and PostToolUse entries |

`<project>` is the directory holding the session's transcript (`dirname(transcript_path)`), so a lead working in a
worktree still finds its own project's `relay/`. The state lives under `relay/`, beside the relay dirs and outside
`memory/`, so nothing loads into context.

Registration (stdlib Python, `python3 -I`, `sys.dont_write_bytecode` like every relay CLI):

    "Stop":        [{"hooks": [{"type": "command", "command": "python3 -I ~/.claude/skills/session-handoff/scripts/relay-gate.py stop || true", "timeout": 10}]}]
    "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "python3 -I ~/.claude/skills/session-handoff/scripts/relay-gate.py tool || true", "timeout": 5}]}]

`|| true` makes a hook that cannot start (the script missing or moved, an interpreter error) exit 0. Python exits 2
on a missing file, and a hook's exit 2 blocks: a Stop registration made before the script is deployed would block
every turn end of every session.

Constants, each with a test-only environment override: threshold 50 (`RELAY_GATE_THRESHOLD`), cap 60
(`RELAY_GATE_CAP`), band step 10 (`RELAY_GATE_STEP`), back-off 1,800 s (`RELAY_GATE_BACKOFF_S`), throttle 60 s
(`RELAY_GATE_THROTTLE_S`), window override (`RELAY_GATE_WINDOW`, tokens), owner-conversation window 600 s
(`RELAY_GATE_OWNER_S`; the live run needs it because `herdr agent prompt` is recorded as a typed prompt).

### The meter

`context_fill(transcript_path)` parses the whole transcript with `transcript.records()`, takes the newest
assistant record that is not `isSidechain`, carries `usage`, and whose model does not start with `<` (the same skip
as `last_model`). It sums input + cache_read + cache_creation of the record's last `usage.iterations` entry of type
`message` (the top-level `usage` when there are no iterations) and divides by the window: `RELAY_GATE_WINDOW` when
set, else `WINDOWS[model]`. It returns `{"pct", "tokens", "model"}`, or `None` when no record is usable or the
window is unknown.

`WINDOWS` starts with `{"claude-opus-5-5": 1_000_000}`, the only measured window. After an auto-compaction the
newest record already carries the post-compaction usage.

### Bands

Band B for fill F, with threshold T, cap C and step S: B = T + S × floor((F − T) / S) for F ≥ T. With the defaults,
50–59.9 is band 50, 60–69.9 band 60, and so on. The cap C is the first band that raises owner alerts.

When the meter reads more than one step below the lowest band recorded in the state, in `nudged`, `alerted`,
`asked` or `pending` (a compaction, or a `/compact` despite the rule), the gate clears `asked`, `nudged`, `alerted`,
`pending` and `drain_owed`: the band memory of a fuller context does not carry over.

### Who is gated

Checked in this order; any failing check exits 0 with no output and writes nothing:

1. `HERDR_ENV == "1"` and `HERDR_PANE_ID` set.
2. The input has no `agent_id` (PostToolUse from a subagent or teammate carries one; Stop never fires for
   either). `CLAUDE_CODE_CHILD_SESSION` is not checked: it is `1` for the lead too.
3. Tool mode only: the throttle (below).
4. The meter reads F ≥ T. A window it does not know is handled after check 5.
5. The session is a lead: its session id equals `session_id` in `<project>/relay/lead.json` (fast path), or the
   pane's herdr name (`herdr agent get $HERDR_PANE_ID`, 2 s bound) starts with `lead-`.

Only a session that passes check 5 gets a state file. A lead whose model has no known window gets one tooling toast
per session naming the model, and is otherwise inert.

### This session's relays

Both modes read the relay dirs under `<project>/relay/` whose `checklist.json` names this session as
`predecessor.session_id`, and classify each by fact:

- **closed**: `closed.json` present. Ignored (a later `closed.json` supersedes a `failed.json`).
- **failed**: `failed.json` present, or the dir is **abandoned**: no `handover.md`, and the newest mtime among
  `checklist.json`, `launch.json`, `receipt.json`, `fix-*` and `fired/*` is 25 minutes old or more (piece 1 waits at
  most 20 minutes for a receipt and 15 per fix round, each starting a fresh file). The failure time is the mtime of
  `failed.json`, or that newest mtime for an abandoned dir; the `at` field is for humans and is never parsed.
- **frozen**: `handover.md` present, no `closed.json`. The predecessor is frozen by design.
- **in progress**: anything else (no terminal file, newer than 25 minutes).

A failure **will repeat** when its `failed.json` has `stage: check` and a reason naming an identity mismatch, or
any stage with a reason naming `agent_name_taken`.

### Stop mode: the gate

For a gated lead at fill F in band B, with `background_tasks` from the input:

1. **In progress or frozen.** Any relay of this session in progress → allow, silent. Frozen → allow, silent, and
   once that dir's `handover.md` is 30 minutes old raise one owner alert "hand-over not closed" (recorded per dir).
   A predecessor the owner resumes after a hand-over is never gated again: the owner relays it by hand.
2. **Failures** (failed and abandoned relays of this session):
   - any at the hand-over stage → allow, silent; this precedes the rules below (the predecessor's protocol
     already told the owner, and the old lead stays frozen until the owner decides);
   - two or more, or one that will repeat → **given up**: the first time, an owner alert (below) naming the relay
     dirs, then `given_up` is recorded; after that, allow, silent;
   - one, less than the back-off ago → allow, silent;
   - one, at least the back-off ago → go on: this is attempt 2.

   The attempt number is 1 + the number of failed relays.
3. **Safe point.** Not safe when any of:
   - `background_tasks` is missing from the input (unknown counts as not safe);
   - it holds a task with a non-terminal `status` whose `type` is anything other than `shell` (`subagent` and
     `teammate` measured; `workflow` and any type the gate does not know defer too, and the cap alert names them);
   - it holds an entry that is not a JSON object (unknown; the cap alert names it);
   - `relaylib.blockers()` reports something: the transcript's open `agent` or `workflow` tasks, or the repo at
     `cwd` mid-merge, rebase, cherry-pick or revert. These are the same rules `relay-check.py checklist` refuses
     on, so a gate that asks can never meet a checklist that refuses.

   Not safe and B < C: record `drain_owed` if B is neither in `nudged` nor the band of a `pending` nudge (one printed
   and not yet confirmed: if it turns out lost, tool mode prints B again at its next metered call), allow, silent.
   Not safe and B ≥ C, B not in `alerted`: record B, then an owner alert (below) naming what blocks the relay,
   asking the lead to keep draining and end its turn, not to relay. Already alerted → allow, silent.
4. **Owner conversation.** A typed prompt (`transcript.prompts()`) less than 10 minutes old and B < C → allow,
   silent.
5. **Dedupe.** `asked` holds the band, the attempt and the open task ids of the last ask, and how many asks were
   made in that band. Ask again only when the band rose, the attempt rose, or a task in `asked.tasks` is no longer
   open (closed); never because a task was added, and never because the band fell (a fall of more than one step
   resets the bands, above). An ask after a fall records the band already asked, so going back up is no rise. At
   most 3 asks per band and attempt; after that only a band rise or a new attempt asks again.
6. **Ask.** Record `asked` with the time of the ask, clear `drain_owed` (the lead is asked to relay, not to drain),
   then block:

       relay-gate: context is 52% (threshold 50%). Run /relay now, automatic relay attempt 1 of 2. Open background
       tasks: b1 'Wait for the slice 13 report' (shell). The successor re-arms waiters. If one of them is long
       work that must finish first, end your turn instead: the gate asks again when a listed task closes or the
       next band starts.

   At B ≥ C (a safe lead that declined at 50%) the same block also carries the band's owner alert.

### Tool mode: the nudge

Checks 1–2, then the throttle: unless `drain_owed` is set, the meter runs at most once per throttle period per
lead, using the read time recorded in the state. A session with no state file (not yet known as a lead) is metered
on every call; that costs 5–50 ms and writes nothing. Then checks 4–5, then "This session's relays": in progress,
frozen or given up → exit silent; in back-off → exit silent. An ask of the current attempt less than 15 minutes old →
exit silent: the lead may be running `/relay`, and nothing shows that until `checklist` writes the relay dir (in
progress covers the time after). Otherwise, when B is not in `nudged` or `drain_owed` is set, record the nudge as
`pending` (B, the call's `tool_use_id`, whether `drain_owed` was set, and the time) and print:

    {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "relay-gate: context is 51%.
     A relay is due. Finish the current step, start nothing new in-session (no subagents, no attached runs), then
     end your turn; the gate runs /relay at turn end."}}

**A nudge counts only once the transcript shows it delivered.** Claude Code kills a PostToolUse hook that outlives
its timeout and discards its output, but by then the gate has written its state. Measured 2026-10-13, with the
output held past the 5 s timeout: 7 of 7 calls were killed, and `nudged` held three bands with none delivered
(e2e defect D2). So, after the relays checks and before deciding, a call with a `pending` nudge looks up its
`tool_use_id` in the transcript. Delivered wins when both records are present:
- a `hook_additional_context` record containing `relay-gate:` means delivered. Add its band to `nudged`, clear
  `drain_owed` if the nudge was a drain nudge, and clear `pending`;
- a `hook_cancelled` record means lost. Clear `pending`, so the band (and a drain nudge) can be printed again.
  A PostToolUse cancel names no hook, so another hook's timeout on the same tool call reads as ours when our
  record is absent. That is accepted: the worst case is one extra print;
- neither, and the nudge is less than 2 minutes old: print nothing this call;
- neither, and the nudge is 2 minutes old or more (or its time cannot be read, or lies in the future): count it as
  delivered, as above. A transcript the gate cannot read, for example after Claude Code renames these records,
  then degrades to one print per band, never to a reprint every few minutes. A lost nudge is caught by its
  `hook_cancelled`, not by this expiry.

Unless the nudge is held (neither record, less than 2 minutes old), the call then decides as if nothing were
pending. The age is measured when the state is read, not when the call started: a parallel call may have saved
the nudge after this call began.

The outcome is reliably there in time: the previous call's record was on disk at the next call in 14 of 14 measured
cases. A call whose input has no `tool_use_id` cannot be confirmed, so it records B in `nudged` and clears
`drain_owed` at once, as before. A throttled call does not look; the next metered call does.

**The meter can read one request behind.** At PostToolUse, the assistant record that issued the tool is often not
on disk yet. Measured: 8 of 15 calls, up to 4.7 s late (e2e defect D3, a property of Claude Code). The meter then
reads the previous request, so a nudge can arrive one request late and name a lower percentage, and a band can be
skipped when one request crosses two. Stop is unaffected: the transcript is flushed before Stop runs.

### Alerts

An **owner alert** is a herdr toast raised by the hook (`herdr notification show "Relay gate: <project>" --body
<text> --sound request`) plus a block whose reason asks the lead to push the same text to the owner: `relay-gate: <text> Load the push
tool with ToolSearch select:PushNotification and send the owner: "<text>" Then <keep draining | end your turn>.` The
alert is recorded before the block is printed, so it never repeats; a lost toast is acceptable because the push and
the pane carry the same text. Owner alerts:

- not safe at C and each later band (once per band), naming what blocks the relay;
- given up (once per session), naming the failed relay dirs;
- hand-over not closed after 30 minutes (once per relay dir).

A **tooling toast** is the toast alone, once per session, because nothing waits on a decision: a lead's model has
no known window; the hook itself failed (Error handling).

### State file

    {"version": 1, "meter": {"pct": 51.2, "read_at": "<UTC>"}, "nudged": [50], "drain_owed": false,
     "alerted": [60], "asked": {"band": 50, "attempt": 1, "tasks": ["b1"], "count": 1, "at": "<UTC>"},
     "given_up": false, "handover_alerted": ["<relay-id>"], "toasted": ["unknown-model"],
     "pending": {"band": 60, "tool_use_id": "toolu_…", "drain": false, "at": "<UTC>"}}

`pending` is `null` when no nudge awaits confirmation. A file written before `pending` existed loads with
`pending: null`; it still has `version` 1.

Written atomically (temp file and rename) only for leads. A missing, unreadable or wrong-shaped file (any key of the
wrong type, or another `version`) is an empty state. The Stop mode prunes `relay/gate/*.json` files of other
sessions older than 7 days.

### Order of work and time budget

Each call computes the decision, writes the state, prints and flushes its output, and only then raises any toast,
fire-and-forget (a detached `herdr notification show`, not awaited). Every herdr call is bounded at 2 s, and so is
the git call of `relaylib.blockers()`: a git that does not answer in time cannot tell, like a git that fails, and adds
no blocker (`relay-check.py checklist` runs the same code). The Stop mode stops gathering after 7 s and the tool mode
after 3 s, inside the 10 s and 5 s hook timeouts; past its deadline a call exits 0 with no output (silent, and the
next call decides afresh).

### Error handling

The gate never fails closed. Any exception: append the traceback to `<project>/relay/gate/errors.log` (or
`~/.claude/relay-gate-errors.log` when the project dir is unknown; either is trimmed to its last 100 KB), raise one
tooling toast per session, deduplicated by an `O_EXCL` marker file `relay/gate/<session-id>.error` independent of
the state, and exit 0 with no output.

### Changes to piece 1

- `relay-check.py`: `blockers()` moves into `relaylib.py`, which `relay-check.py` and the gate both import; no
  behaviour change.
- `references/relay.md` and `SKILL.md`: a section on automatic relays (what triggers one, how a lead declines, the
  back-off, given up, where the state lives, one lead per project, a resumed predecessor is relayed by hand).
- `~/.claude/CLAUDE.md`: the "Herd layout" section says to name a coordinator `lead-<project>` at start
  (`relay-check.py name --repo <repo>` prints it), and the 50% lines say the gate fires `/relay` once switched on.
- `relay-launch.sh` is unchanged: a successor inherits the owner's global hooks.

## Testing

**Probes** (done before the gate code; Measured facts): the child-session variable, teammates in
`background_tasks`, and the transcript flush before Stop.

**Unit tests** (`tests/test_relay_gate.py`, the existing fixtures and herdr stub):

- meter: the advisor-doubling record reads the `message` iteration, not the top level; sidechain and `<` models
  ignored; unknown window → `None`; `RELAY_GATE_WINDOW` override;
- bands: relative to the threshold; reset after a drop of more than one step;
- identity: outside herdr; `agent_id` (a subagent's and a teammate's); `CLAUDE_CODE_CHILD_SESSION=1` on the lead
  still gated; `lead.json` match; `lead-` name; neither (no state file written);
- relay classification: closed supersedes failed; abandoned at 25 minutes (by mtimes); frozen; in progress; failure
  time from the `failed.json` mtime; will-repeat reasons;
- Stop decisions, one test per row: below threshold; in progress; frozen (silent, then one hand-over alert at 30
  minutes); two failures → given up (one alert block, then silent); a will-repeat failure → given up; one failure
  inside the back-off; one after it → attempt 2 even with the same band and tasks as the last ask; not safe below
  the cap (`drain_owed`); not safe at the cap (one alert per band); missing `background_tasks`; unknown task type;
  a running teammate; a transcript-open workflow; git mid-merge; owner prompt 5 minutes ago (silent) and
  at the cap (asks); safe (block text); same band, attempt and tasks (silent); a task added (silent); a listed task
  closed (asks again); band rose (asks, with the alert); band fell and rose back (silent); fourth ask in a band
  (silent);
- the loop test (the research's T13), exact counts: replay 40 Stop events with notification turns and new prompt
  ids after one failed relay: zero blocks while the back-off runs; exactly one block, attempt 2 of 2, at the first
  safe Stop after it; after a second failure exactly one given-up alert block; zero after that;
- nudge: once per band, counted only once confirmed: delivered, cancelled (printed again), held while unconfirmed,
  counted as delivered after 2 minutes or a future stamp, a drain nudge paying `drain_owed` only when delivered, no
  `tool_use_id` counted at once, an unsafe Stop owing no drain for a pending band, a pending band reset by a
  compaction drop, and a call that confirms then decides in the same call; `drain_owed` delivered at the next call
  without throttle; silent in progress, frozen,
  back-off and given up; silent for 15 minutes after an ask of the current attempt, a band crossing included, and
  not after an ask of an earlier attempt; an ask clears `drain_owed`; throttle; `agent_id` exits;
- alerts and order: the state is written before the output, the toast is detached and its failure changes nothing;
- fail-open: garbage stdin, a raising helper → exit 0, no stdout, one line in `errors.log`, one marker, one toast;
  a wrong-shaped state is empty; `errors.log` trimmed.

**Live end to end** in a scratch herdr tab, as piece 1's Task 10, with the gate registered by `--settings`, the
lead on `claude-opus-5-5`, and the test overrides set so a small session crosses the bands (for example threshold
7, cap 9, step 1, back-off 120 s):

1. pass: the lead crosses the threshold, the gate blocks, the lead runs `/relay`, the successor closes it;
2. not safe: a running background subagent defers the block; its completion turn gets the block;
3. failure and back-off: a relay made to fail at the receipt stage → silent through the back-off → exactly one
   retry → second failure → one given-up toast and push request, no further blocks across several turns;
4. the nudge appears once per band in a long turn.

## Out of scope

- A live workflow-child identity test: it needs a Workflow run, which needs the owner's opt-in. A workflow's agents
  fire SubagentStop and carry `agent_id`, and a running workflow defers the gate either way.
- An enforcing per-step lever (PostToolBatch `continue:false`): the overshoot of one long turn is accepted.
- A StopFailure hook (a turn ended by an API error skips Stop; the next turn's Stop catches up).
- Vetoing idle auto-compaction; a status-line sidecar meter; Codex workers (they run no Claude hooks).
- Two leads in one project; windows for models other than `claude-opus-5-5` until measured.
