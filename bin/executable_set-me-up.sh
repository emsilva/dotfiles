#!/usr/bin/env bash

###############################################
# Sets up Homebrew and Brewable things.       #
###############################################

#Installs Homebrew if not installed yet.
if ! command -v brew &> /dev/null
then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

#Installs all Homebrew apps necessary
homebrew_casks=(
                 cask-fonts
               )

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
                dockutil
                mysides
                chezmoi
                mas
                meld
                iterm2
		            visual-studio-code
                monitorcontrol
                "--cask whatsapp"
                "--cask telegram"
                "--cask signal"
                "--cask 1password/tap/1password-cli"
                "--cask font-fira-code"
              )

for homebrew_app in "${homebrew_apps[@]}"
do
  if ! brew ls $homebrew_app &> /dev/null
  then
    brew install $homebrew_app
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
