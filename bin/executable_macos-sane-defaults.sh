#!/usr/bin/env bash

################################
# Finder & Desktop Preferences #
################################

# Always show suffixes
defaults write NSGlobalDomain AppleShowAllExtensions -bool true

# Always search current folder
defaults write com.apple.finder FXDefaultSearchScope -string "SCcf"

# Show path bar and status bar
defaults write com.apple.finder ShowStatusBar -bool true
defaults write com.apple.finder ShowPathbar -bool true

# Devices for the sidebar
defaults write com.apple.sidebarlists systemitems -dict-add ShowServers -int 1
defaults write com.apple.sidebarlists systemitems -dict-add ShowRemovable -int 1
defaults write com.apple.sidebarlists systemitems -dict-add ShowHardDisks -int 1
defaults write com.apple.sidebarlists systemitems -dict-add ShowEjectables -int 1

# Items to display on the desktop
defaults write com.apple.finder ShowHardDrivesOnDesktop -int 1
defaults write com.apple.finder ShowMountedServersOnDesktop -int 1
defaults write com.apple.finder ShowExternalHardDrivesOnDesktop -int 1
defaults write com.apple.finder ShowRemovableMediaOnDesktop -int 1

# Open home in new window
defaults write com.apple.finder NewWindowTarget -string "PfLo"
defaults write com.apple.finder NewWindowTargetPath -string "'file://$HOME/"

# List view in by default
# Possible: `icnv`, `clmv`, `Flwv`
defaults write com.apple.finder FXPreferredViewStyle -string "Nlsv"

# Show the ~/Library folder
chflags nohidden ~/Library

########
# Dock #
########

# Dock: Make it popup faster
defaults write com.apple.dock autohide-delay -float 0
defaults write com.apple.dock autohide-time-modifier -float 0

# Remove everything (I like the dock to only show open apps. I open apps through Alfred)
dockutil --remove all > /dev/null 2>&1


########################
# General UI Behaviour #
########################


# Scroll bars
# Possible: "WhenScrolling", "Automatic" and "Always"
defaults write NSGlobalDomain AppleShowScrollBars -string "Always"

# System Preferences: Trackpad
# Trackpad: Tap
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad Clicking -bool true
defaults write com.apple.AppleMultitouchTrackpad Clicking -bool true
defaults -currentHost write NSGlobalDomain com.apple.mouse.tapBehavior -int 1
defaults write NSGlobalDomain com.apple.mouse.tapBehavior -int 1

# Trackpad: Two-Finger-Tap
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadRightClick -bool true
defaults write com.apple.AppleMultitouchTrackpad TrackpadRightClick -bool true
defaults -currentHost write NSGlobalDomain com.apple.trackpad.enableSecondaryClick -bool true
defaults write com.apple.AppleMultitouchTrackpad TrackpadRightClick -bool true

# Keyboard key repeat
defaults write -g InitialKeyRepeat -int 10
defaults write -g KeyRepeat -int 1

# Auto correct off, Auto capitalize off, Hold for accented keys off
defaults write NSGlobalDomain NSAutomaticSpellingCorrectionEnabled -bool false
defaults write NSGlobalDomain NSAutomaticCapitalizationEnabled -bool false
defaults write -g ApplePressAndHoldEnabled -bool false

# Hot corners
# Possible values: 0 no-op; 2 Mission Control; 3 Show application windows;
# 4 Desktop; 5 Start screen saver; 6 Disable screen saver; 7 Dashboard;
# 10 Put display to sleep; 11 Launchpad; 12 Notification Center

#Top left
defaults write com.apple.dock wvous-tl-corner -int 3
defaults write com.apple.dock wvous-tl-modifier -int 0

#Top right
defaults write com.apple.dock wvous-tr-corner -int 4
defaults write com.apple.dock wvous-tr-modifier -int 0

#Bottom left
defaults write com.apple.dock wvous-bl-corner -int 2
defaults write com.apple.dock wvous-bl-modifier -int 0

#Bottom right
defaults write com.apple.dock wvous-br-corner -int 5
defaults write com.apple.dock wvous-br-modifier -int 0
