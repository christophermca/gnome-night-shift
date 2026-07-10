#!/bin/bash

source /usr/lib/gnome-mode-shift/shared-variables.sh

echo '::AUTO-UPDATE-GNOME-THEME::'

# This function depends on redshift
auto_update_gnome_theme() {

  DAY_NIGHT=$(cat $IS_DAY_OR_NIGHT)

  if [ -z $DAY_NIGHT ]; then
    echo "missing day_night; Check provided path: $IS_DAY_OR_NIGHT"
    exit 33
  fi

if [ $DAY_NIGHT == $DAY_MODE ]; then
  PREFER_MODE='prefer-light';
elif [ $DAY_NIGHT == $NIGHT_MODE ]; then
  PREFER_MODE='prefer-dark';
fi

if [[ -n $PREFER_MODE ]]; then
  gsettings set org.gnome.desktop.interface color-scheme $PREFER_MODE
fi

}

auto_update_gnome_theme
