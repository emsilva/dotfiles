alias :e='vim'
alias oldvim='/usr/bin/vim'
alias sy='systemctl'
alias ls='/usr/local/bin/gls --color=auto' 
alias ll='/usr/local/bin/gls --color=auto -GFhl' 
alias be='bundle exec'
alias bi='bundle install'
alias bu='bundle update'
alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias git='LANG=en_US.UTF-8 git'
alias g="git status"
function gg () {
  git commit -a -m "$@"
}
alias be='bundle exec'

