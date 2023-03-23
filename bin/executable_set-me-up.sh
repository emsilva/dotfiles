#!/usr/bin/env bash

###############################################
# Sets up Homebrew and Brewable things.       #
###############################################

#Installs Homebrew if not installed yet.
if ! command -v brew &> /dev/null
then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

#Installs all Homebrew apps
homebrew_casks=( "d12frosted/emacs-plus" )
for homebrew_cask in "${homebrew_casks[@]}"
do
  if ! brew tap | grep $homebrew_cask &> /dev/null
  then
    brew tap $homebrew_cask
  fi
done

homebrew_apps=(
                python3
                python-tk@3.9
                coreutils
                cmake
                wget
                dockutil
                mysides
                chezmoi
                mas
                iterm2
                visual-studio-code
                monitorcontrol
                handbrake
                ruby
                mosh
                marked
                shellcheck
                graphviz
                jq
                grep
                ansible
                ripgrep
                fd
                tradingview
                mactex
                openjdk
                plantuml
                "emacs-plus@28 --with-native-comp --with-modern-black-variant-icon"
                "--cask whatsapp"
                "--cask telegram"
                "--cask signal"
                "--cask 1password/tap/1password-cli"
              )

for homebrew_app in "${homebrew_apps[@]}"
do
  if ! brew ls $homebrew_app &> /dev/null
  then
    brew install $homebrew_app
  fi
done

###############################################
# Sets up dotfiles                            #
###############################################
if ! test -d ~/.local/share/chezmoi/
then
  chezmoi init --apply emsilva/dotfiles
fi

###############################################
# Installs Ruby Gems                          #
###############################################
ruby_gems=(
                video_transcoding
          )

for ruby_gem in "${ruby_gems[@]}"
do
  if ! gem list | grep $ruby_gem &> /dev/null
  then
    gem install $ruby_gem
  fi
done

###############################################
# Installs MacApp Store Apps                  #
###############################################
macstore_apps=(
                402670023  # Keyboard Pilot
                425424353  # The Unarchiver
                1508732804 # Soulver
                403504866  # PCalc
                937984704  # Amphetamine
                1561788435 # Usage
                1224268771 # Screens
              )

for macstore_app in "${macstore_apps[@]}"
do
  mas install $macstore_app
done

###############################################
# Sets up unlinked github repos.              #
###############################################
github_repos=(
                "trapd00r/LS_COLORS"
                "zplug/zplug"
)
for github_repo in "${github_repos[@]}"
do
  dirname=`echo $github_repo | cut -d '/' -f2`
  if ! test -d ~/.local/share/$dirname &> /dev/null
  then
    git clone https://github.com/$github_repo ~/.local/share/$dirname
  fi
done

###############################################
# Everything Else                             #
###############################################

# Doom Emacs
# Check if the Doom binary does not exist
if ! test -f ~/.emacs.d/bin/doom; then
  # If it doesn't exist, check if the ~/.emacs.d directory exists
  if [ -d ~/.emacs.d ]; then
    # If the directory exists, delete it and all of its contents
    echo "Deleting existing ~/.emacs.d directory..."
    rm -rf ~/.emacs.d
  fi
  # Clone the Doom Emacs repository from GitHub to the ~/.emacs.d directory
  echo "Cloning Doom Emacs repository to ~/.emacs.d directory..."
  git clone --depth 1 https://github.com/doomemacs/doomemacs ~/.emacs.d
  ~/.emacs.d/bin/doom install
  ~/.emacs.d/bin/doom sync
else
  # If the Doom binary exists, output a message indicating that Doom Emacs is already installed
  echo "Doom Emacs is already installed!"
fi

# iTerm2
# installs shell integration for iTerm2
# https://iterm2.com/documentation-shell-integration.html
if ! test -f ~/.iterm2_shell_integration.zsh
then
  curl -L https://iterm2.com/shell_integration/install_shell_integration.sh | bash
fi

# Sets up and loads iTerm2 preferences
defaults write com.googlecode.iterm2 PrefsCustomFolder -string "~/.local/share/iterm2/"
defaults write com.googlecode.iterm2 LoadPrefsFromCustomFolder -bool true

# installs oh-my-zsh
# https://ohmyz.sh/
if ! test -d ~/.oh-my-zsh/
then
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --keep-zshrc
fi
