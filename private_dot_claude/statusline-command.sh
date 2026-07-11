#!/usr/bin/env bash
# ~/.claude/statusline-command.sh
# Full truecolor status line:
# Segments (gray │-separated), left→right:
#   repo (bold cyan) │ branch icon + name (purple), + worktree marker if linked │
#   model marker (Nerd glyph, tinted per model) + effort dot │
#   context gauge (icon colored by usage + %) │ session gauge (icon colored + % + timer) │
#   weekly usage as a colored circle-slice pie (8 steps) at the far right.
# Uses Nerd Font glyphs — requires a Nerd-patched terminal font (e.g. CaskaydiaCove NF).

input=$(cat)

cwd=$(echo "$input" | jq -r '.cwd // ""')

# (old implementation removed)
if false; then
  # placeholder — never executes
  true
  if false; then
    echo "$status_out" | grep -q "^??"         && flags="${flags}…"   # untracked
  fi
  # Stash
  stash_count=$(git -C "$cwd" --no-optional-locks stash list 2>/dev/null | wc -l | tr -d ' ')
  [ "${stash_count:-0}" -gt 0 ] && flags="${flags}⧉"
  # Ahead/behind
  ahead=$(git -C "$cwd" --no-optional-locks rev-list --count @{u}..HEAD 2>/dev/null || echo "")
  : noop
  git_info=" $(printf '') ${branch}${flags:+ $flags}"
fi

# ── ANSI helpers ──────────────────────────────────────────────────────────────
esc=$'\033'
reset="${esc}[0m"
bold="${esc}[1m"

rgb()    { printf "${esc}[38;2;%d;%d;%dm" "$1" "$2" "$3"; }
# Monokai Pro palette
BOLD_CYAN="${bold}$(rgb 120 220 232)"     # #78DCE8 — cyan (directory/repo)
WHITE="$(rgb 252 252 250)"               # #FCFCFA — white (git icon)
PURPLE="$(rgb 171 157 242)"             # #AB9DF2 — purple (branch name)
PINK="$(rgb 255 97 136)"               # #FF6188 — pink (Opus model)
GREEN_FG="$(rgb 169 220 118)"            # #A9DC76 — green
RED_FG="$(rgb 255 97 89)"               # #FF6188 — pink/red
GRAY="$(rgb 140 140 140)"
PIPE="${GRAY} | ${reset}"

# Middle-truncate long branch/worktree names so they don't blow out the line:
# keep the first 8 chars + … + the last 4 (e.g. fix/walk-gaps-required-clamp-audit-stamp → fix/walk…tamp).
# First-8 preserves the type/ prefix (fix/, feat/, chore/…); last-4 keeps the distinguishing
# suffix so sibling branches sharing a prefix don't collapse to the same truncated label.
truncate_mid() {
  local s="$1" head=8 tail=4
  local len=${#s}
  local ell=$'\xe2\x80\xa6'   # … (U+2026) as explicit UTF-8 bytes so an editor can't mangle it
  if [ "$len" -gt $((head + tail + 1)) ]; then
    printf '%s%s%s' "${s:0:head}" "$ell" "${s: -tail}"
  else
    printf '%s' "$s"
  fi
}

# ── Input fields ──────────────────────────────────────────────────────────────
repo_name=$(echo "$input" | jq -r '.workspace.repo.name // ""')
model_full=$(echo "$input" | jq -r '.model.display_name // .model.id // ""')
effort=$(echo "$input"    | jq -r '.effort.level // empty')

# Shorten model to a single uppercase initial of its family (Opus→O, Sonnet→S, Haiku→H, Fable→F)
model=$(printf '%s' "$model_full" | grep -oiE 'opus|sonnet|haiku|fable' | head -1)
if [ -n "$model" ]; then
  model="$(printf '%s' "$model" | cut -c1 | tr '[:lower:]' '[:upper:]')"
else
  model="$model_full"
fi

# ── Repo name (bold yellow) ───────────────────────────────────────────────────
if [ -z "$repo_name" ]; then
  # No repo.name from Claude Code (older builds, or a session launched from a worktree
  # where project_dir is the worktree folder). Derive the name from git's COMMON dir,
  # which resolves a linked worktree back to the main checkout — so the label is always
  # the project (e.g. my-project), never a worktree directory name.
  common_abs=$(git -C "$cwd" --no-optional-locks rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
  [ -n "$common_abs" ] && repo_name=$(basename "$(dirname "$common_abs")" 2>/dev/null)
  # Last resort: cwd isn't a git repo at all.
  [ -z "$repo_name" ] && repo_name=$(echo "$input" | jq -r '.workspace.project_dir // .cwd // ""' | xargs basename 2>/dev/null)
fi
repo_part="${BOLD_CYAN}${repo_name}${reset}"

# ── Git branch (bold cyan, leaf icon) ─────────────────────────────────────────
branch=""
if [ -n "$cwd" ]; then
  branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null \
        || git -C "$cwd" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
fi
# Branch icon: octicons git-branch (Nerd Font, U+F418); byte-escaped so an editor
# can't mangle it — needs a Nerd-patched terminal font (CaskaydiaCove NF).
BRANCH_ICON=$'\xef\x90\x98'   #  U+F418 octicons git-branch
branch_part=""
if [ -n "$branch" ]; then
  branch_disp=$(truncate_mid "$branch")
  branch_part="${WHITE}${BRANCH_ICON}${reset} ${PURPLE}(${branch_disp})${reset}"
fi

# Resolve a git-dir path (relative or absolute) to an absolute, symlink-free path
resolve_git_path() {
  local base="$1" path="$2"
  case "$path" in
    /*) (cd "$path" 2>/dev/null && pwd) ;;
    *)  (cd "$base/$path" 2>/dev/null && pwd) ;;
  esac
}

# ── Worktree indicator ────────────────────────────────────────────────────────
# When cwd is a linked worktree (git worktree add), not the main checkout, prefix
# the branch with ↳ so it reads as "this branch is on a worktree". The worktree
# name is intentionally NOT shown — the branch already identifies the line of work.
in_worktree=""
if [ -n "$cwd" ]; then
  raw_git_dir=$(git -C "$cwd" --no-optional-locks rev-parse --git-dir 2>/dev/null)
  raw_git_common_dir=$(git -C "$cwd" --no-optional-locks rev-parse --git-common-dir 2>/dev/null)
  if [ -n "$raw_git_dir" ] && [ -n "$raw_git_common_dir" ]; then
    git_dir_abs=$(resolve_git_path "$cwd" "$raw_git_dir")
    git_common_dir_abs=$(resolve_git_path "$cwd" "$raw_git_common_dir")
    [ -n "$git_dir_abs" ] && [ "$git_dir_abs" != "$git_common_dir_abs" ] && in_worktree=1
  fi
fi
# Worktree marker: material file-tree (Nerd Font, U+F0645).
WORKTREE_ICON=$'\xf3\xb0\x99\x85'   # 󰙅 U+F0645 material file-tree
[ -n "$in_worktree" ] && [ -n "$branch_part" ] && branch_part="${WHITE}${WORKTREE_ICON}${reset} ${branch_part}"

# ── Reasoning-effort indicator ────────────────────────────────────────────────
# One block, colored by level:  low ▮(gray) · medium ▮(green) · high ▮(yellow) · xhigh ▮(orange) · max ▮(red).
# NOTE: "ultracode" is NOT distinguishable in a statusline — Claude Code reports it as
# xhigh — so ultracode shows the same orange block as xhigh.
EFF_GREEN="$(rgb 169 220 118)"   # #A9DC76
EFF_YELLOW="$(rgb 255 216 102)"  # #FFD866
EFF_ORANGE="$(rgb 252 152 103)"  # #FC9867
EFF_RED="$(rgb 255 97 89)"       # #FF6159
DOT=$'\xef\x84\x91'             #  U+F111 fontawesome circle — effort/context/session dot
stopwatch=$'\xf3\xb1\x8e\xab'   #  U+F13AB material timer — clock before the reset countdown
effort_block() {
  local c
  case "$1" in
    low)    c="$GRAY"       ;;
    medium) c="$EFF_GREEN"  ;;
    high)   c="$EFF_YELLOW" ;;
    xhigh)  c="$EFF_ORANGE" ;;   # ultracode reports as xhigh → same orange
    max)    c="$EFF_RED"    ;;
    *) return 1 ;;  # unknown / effort-less model → no block
  esac
  printf '%s%s%s' "$c" "$DOT" "$reset"
}

# ── Model marker + effort block ───────────────────────────────────────────────
# The model marker is a Nerd Font glyph (needs a Nerd-patched terminal font, e.g.
# CaskaydiaCove NF); written as explicit UTF-8 bytes so an editor can't mangle it.
# Unlike an emoji, a Nerd glyph is plain text, so it takes ANSI color. The icon is
# shown alone (no initial letter) and tinted per model, so its COLOR is the model
# tell: Opus orange · Sonnet green · Haiku cyan · Fable pink · anything else white.
MODEL_ICON=$'\xf3\xb1\x9a\x9d'  # 󱚝 U+F169D — Material Design icon via Nerd Fonts
model_part=""
if [ -n "$model" ]; then
  case "$model" in
    O) model_color="$EFF_ORANGE"        ;;  # Opus   — #FC9867 orange
    S) model_color="$GREEN_FG"          ;;  # Sonnet — #A9DC76 green
    H) model_color="$(rgb 120 220 232)" ;;  # Haiku  — #78DCE8 cyan
    F) model_color="$PINK"              ;;  # Fable  — #FF6188 pink
    *) model_color="$WHITE"             ;;  # unknown / full display name
  esac
  model_part="${model_color}${MODEL_ICON}${reset}"
  if [ -n "$effort" ]; then
    eff=$(effort_block "$effort") && model_part="${model_part} ${eff}"
  fi
fi

# ── Context-window usage gauge ────────────────────────────────────────────────
# Coarse bucket, not an exact count: <50% green · 50–75% yellow · 75–90% orange · >90% red.
# Prefers the pre-computed context_window.used_percentage field (current CC versions).
# Falls back to scanning the transcript's last assistant usage block for older versions
# (jq's `//` treats JSON null as falsy too, so "no messages yet" also falls through here).
ctx_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

if [ -z "$ctx_pct" ]; then
  transcript_path=$(echo "$input" | jq -r '.transcript_path // empty')
  window_size=$(echo "$input" | jq -r '.context_window.context_window_size // empty')
  if [ -z "$window_size" ]; then
    # 1M-context models advertise it in the model id/display name (e.g. "...[1m]");
    # otherwise assume the standard 200k window.
    if printf '%s' "$model_full" | grep -qi '1m'; then
      window_size=1000000
    else
      window_size=200000
    fi
  fi
  if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
    last_usage=$(jq -c 'select(.message.usage != null) | .message.usage' "$transcript_path" 2>/dev/null | tail -1)
    if [ -n "$last_usage" ]; then
      used_tokens=$(echo "$last_usage" | jq '(.input_tokens // 0) + (.cache_read_input_tokens // 0) + (.cache_creation_input_tokens // 0)' 2>/dev/null)
      [ -n "$used_tokens" ] && ctx_pct=$(awk -v u="$used_tokens" -v w="$window_size" 'BEGIN { if (w > 0) printf "%.0f", (u / w) * 100 }')
    fi
  fi
fi

# Context gauge icon: codicons window (Nerd Font, U+EB7F); byte-escaped, needs a
# Nerd-patched terminal font (CaskaydiaCove NF).
CTX_ICON=$'\xee\xad\xbf'   #  U+EB7F codicons window
ctx_part=""
if [ -n "$ctx_pct" ]; then
  ctx_int=$(awk -v p="$ctx_pct" 'BEGIN { printf "%d", p + 0 }' 2>/dev/null)
  if [ -n "$ctx_int" ]; then
    if   [ "$ctx_int" -lt 50 ]; then ctx_color="$GREEN_FG"     # < 50%
    elif [ "$ctx_int" -lt 75 ]; then ctx_color="$EFF_YELLOW"   # 50–75%
    elif [ "$ctx_int" -lt 90 ]; then ctx_color="$EFF_ORANGE"   # 75–90%
    else                              ctx_color="$RED_FG"      # > 90% — close to full
    fi
    ctx_part="${ctx_color}${CTX_ICON}${reset} ${ctx_int}%"
  fi
fi
[ -z "$ctx_part" ] && ctx_part="${GRAY}${CTX_ICON} ?${reset}"

# ── Session-limit gauge (5-hour rate-limit window) ────────────────────────────
# Hourglass-icon prefixed to set it apart from the context gauge. Same coarse buckets as the
# context gauge: <50% green · 50–75% yellow · 75–90% orange · >90% red.
# Reads the pre-computed rate_limits.five_hour.used_percentage (the same number
# /usage shows for the session). Absent on plans/auth that don't report limits
# (e.g. API-key billing) → the segment is dropped entirely, like the effort block.
# NOTE: refreshes only when the statusline re-runs (assistant message / mode
# change), so a long idle won't tick the number until the next update — set
# refreshInterval in settings.json if you want it to advance on a timer.
sess_pct=$(echo "$input"   | jq -r '.rate_limits.five_hour.used_percentage // empty')
sess_reset=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // empty')

# Session gauge icon: fontawesome hourglass-half (Nerd Font, U+F252).
SESS_ICON=$'\xef\x89\x92'   #  U+F252 fontawesome hourglass-half
sess_part=""
if [ -n "$sess_pct" ]; then
  sess_int=$(awk -v p="$sess_pct" 'BEGIN { printf "%d", p + 0 }' 2>/dev/null)
  if [ -n "$sess_int" ]; then
    if   [ "$sess_int" -lt 50 ]; then sess_color="$GREEN_FG"     # < 50%
    elif [ "$sess_int" -lt 75 ]; then sess_color="$EFF_YELLOW"   # 50–75%
    elif [ "$sess_int" -lt 90 ]; then sess_color="$EFF_ORANGE"   # 75–90%
    else                              sess_color="$RED_FG"       # > 90% — close to the limit
    fi
    sess_part="${sess_color}${SESS_ICON}${reset} ${sess_int}%"

    # ── Countdown to session reset ────────────────────────────────────────────
    # resets_at is a Unix epoch (seconds). Show whole minutes left in the 5-hour
    # window after the timer glyph (e.g.  12m), so you can see how long until it rolls
    # over. ≥60 min collapses to "HhMm" (no space); a stale/past timestamp clamps to 0m.
    # Like the % itself, this only advances when the statusline re-runs.
    if [ -n "$sess_reset" ]; then
      rem_min=$(awk -v r="$sess_reset" -v n="$(date +%s)" 'BEGIN { d=int((r-n)/60); if (d<0) d=0; print d }')
      if [ "${rem_min:-0}" -ge 60 ]; then
        reset_disp="$((rem_min / 60))h$((rem_min % 60))m"
      else
        reset_disp="${rem_min:-0}m"
      fi
      sess_part="${sess_part} ${stopwatch} ${reset_disp}"
    fi
  fi
fi

# ── Weekly-usage gauge (7-day rate-limit window) ──────────────────────────────
# A single circle-slice (pie) glyph at the far end of the line: its FILL shows how
# much of the weekly limit is spent — eight eighth-steps (1/8 … full), rounded to
# the nearest eighth — and its COLOR flags urgency on the same buckets as the
# context/session gauges (<50 green · 50–75 yellow · 75–90 orange · ≥90 red). No %,
# no reset countdown — just the glyph. Source: .rate_limits.seven_day (sibling of
# the 5-hour window). Absent (non-subscription auth, or not yet reported) → the
# segment is dropped entirely, like the session gauge. Glyphs are Material Design
# circle-slice-1..8 (Nerd Font, U+F0A9E–F0AA5), explicit UTF-8 bytes so an editor
# can't mangle them — needs a Nerd-patched terminal font (CaskaydiaCove NF).
SLICE=( $'\xf3\xb0\xaa\x9e' $'\xf3\xb0\xaa\x9f' $'\xf3\xb0\xaa\xa0' $'\xf3\xb0\xaa\xa1' \
        $'\xf3\xb0\xaa\xa2' $'\xf3\xb0\xaa\xa3' $'\xf3\xb0\xaa\xa4' $'\xf3\xb0\xaa\xa5' )
#          󰪞1/8             󰪟2/8             󰪠3/8             󰪡4/8
#          󰪢5/8             󰪣6/8             󰪤7/8             󰪥8/8 (full)

week_pct=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')

week_part=""
if [ -n "$week_pct" ]; then
  week_int=$(awk -v p="$week_pct" 'BEGIN { printf "%d", p + 0 }' 2>/dev/null)
  if [ -n "$week_int" ]; then
    # Fill level 1–8 = the usage % rounded to the nearest eighth, clamped to 1..8.
    lvl=$(( (week_int * 8 + 50) / 100 ))
    [ "$lvl" -lt 1 ] && lvl=1
    [ "$lvl" -gt 8 ] && lvl=8
    week_glyph="${SLICE[$((lvl - 1))]}"
    # Urgency color — same buckets as the context/session gauges.
    if   [ "$week_int" -lt 50 ]; then week_color="$GREEN_FG"     # < 50%
    elif [ "$week_int" -lt 75 ]; then week_color="$EFF_YELLOW"   # 50–75%
    elif [ "$week_int" -lt 90 ]; then week_color="$EFF_ORANGE"   # 75–90%
    else                              week_color="$RED_FG"       # > 90% — near the weekly cap
    fi
    week_part="${week_color}${week_glyph}${reset}"
  fi
fi

# ── Assemble ──────────────────────────────────────────────────────────────────
out="${repo_part}"
[ -n "$branch_part"   ] && out="${out}${PIPE}${branch_part}"
[ -n "$model_part"    ] && out="${out}${PIPE}${model_part}"
out="${out}${PIPE}${ctx_part}"
[ -n "$sess_part" ] && out="${out}${PIPE}${sess_part}"
# Weekly moon rides at the very end, attached by a plain space (no gray pipe).
[ -n "$week_part" ] && out="${out} ${week_part}"

printf '%b' "$out"
