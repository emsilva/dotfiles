#!/usr/bin/env bash
# Cheat sheet for ~/.tmux.conf — invoked by `prefix /` (display-popup + less -R).
# Keep in sync when you add/change bindings in ~/.tmux.conf.
#
# Colors use the Monokai Pro palette (matches the tmux status bar + kitty theme).

P=$'\e[1;38;2;171;157;242m'   # bold purple — section headers + accents
Y=$'\e[38;2;255;216;102m'     # yellow      — key chords
D=$'\e[38;2;146;146;147m'     # dim grey    — annotations
R=$'\e[0m'                    # reset

cat <<EOF

  ${P}TMUX CHEAT SHEET${R}  ${D}— prefix is${R} ${Y}Ctrl-Space${R}

  ${P}SESSIONS${R}
    ${Y}prefix d${R}              detach from current session
    ${Y}prefix s${R}              session picker (zoomed)
    ${Y}prefix \$${R}              rename session
    ${Y}prefix (   /   )${R}      previous / next session
    ${D}From a shell outside tmux:${R}
    ${Y}tmux new -s NAME${R}      start new named session
    ${Y}tmux a -t NAME${R}        attach to a session
    ${Y}tmux ls${R}               list running sessions

  ${P}WINDOWS${R}  ${D}(like tabs)${R}
    ${Y}prefix c${R}              new window (opens in current dir)
    ${Y}prefix 1..9${R}           jump to window N
    ${Y}prefix n   /   p${R}      next / previous window
    ${Y}prefix Tab${R}            last (most-recent) window
    ${Y}prefix w${R}              window picker (zoomed)
    ${Y}prefix ,${R}              rename current window
    ${Y}prefix <   /   >${R}      move window left / right (mash)
    ${Y}prefix &${R}              kill window

  ${P}PANES${R}  ${D}(splits inside a window)${R}
    ${Y}prefix |${R}              split vertical   (panes side-by-side)
    ${Y}prefix -${R}              split horizontal (panes stacked)
    ${Y}Alt-h/j/k/l${R}           move between panes (no prefix)
    ${Y}Alt-Shift-H/J/K/L${R}     resize pane         (no prefix)
    ${Y}prefix h/j/k/l${R}        move between panes (prefix style)
    ${Y}prefix H/J/K/L${R}        resize pane (mash after one prefix)
    ${Y}prefix z${R}              zoom toggle (fullscreen current pane)
    ${Y}prefix Space${R}          cycle preset layouts
    ${Y}prefix q${R}              flash pane numbers (then digit to jump)
    ${Y}prefix {   /   }${R}      swap current pane with previous / next
    ${Y}prefix !${R}              break current pane into its own window
    ${Y}prefix x${R}              kill current pane

  ${P}COPY MODE${R}  ${D}(vim-style — set via mode-keys vi)${R}
    ${Y}prefix [${R}              enter copy mode
    ${Y}h j k l   w b   gg G${R}  navigation
    ${Y}/   ?${R}                 search forward / back
    ${Y}n   N${R}                 next / previous match
    ${Y}v${R}                     begin selection
    ${Y}Ctrl-v${R}                toggle rectangular (block) selection
    ${Y}y${R}                     copy → system clipboard via OSC 52
    ${Y}q${R}                     exit copy mode
    ${Y}prefix ]${R}              paste from tmux buffer (most recent yank)
    ${Y}prefix =${R}              choose from older paste buffers

  ${P}MOUSE${R}  ${D}(mouse is on; hold Shift to bypass tmux)${R}
    ${Y}click pane${R}            focus that pane
    ${Y}drag border${R}           resize panes
    ${Y}drag inside pane${R}      select text → OS clipboard
    ${Y}Shift + drag${R}          bypass tmux, use kitty's native selection
    ${Y}wheel${R}                 scroll (enters copy mode automatically)

  ${P}SCRATCH${R}  ${D}(persistent floating shell, runs over any pane layout)${R}
    ${Y}F11${R}                   toggle scratch popup (attaches to "scratch"
                            session — state persists between invocations)

  ${P}NESTED TMUX${R}  ${D}(running tmux inside another tmux, e.g. over ssh)${R}
    ${Y}prefix prefix <key>${R}   send <key> to the INNER tmux
    ${Y}F12${R}                   toggle passthrough on/off (no prefix; outer
                            tmux dims its status bar while passthrough is on)

  ${P}MISC${R}
    ${Y}prefix r${R}              reload ~/.tmux.conf
    ${Y}prefix m${R}              toggle mouse on / off
    ${Y}prefix ?${R}              full list of EVERY binding (built-in)
    ${Y}prefix /${R}              ${D}this cheat sheet${R}
    ${Y}prefix :${R}              tmux command prompt

  ${D}Scroll with j/k or arrows.  Press q to close.${R}

EOF
