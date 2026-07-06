#!/bin/bash

source /usr/lib/gnome-night-shift/shared-variabes.sh

echo '::AUTO-UPDATE-GNOME-THEME::'

# This function depends on redshift
auto_update_gnome_theme() {

  DAY_NIGHT=$(cat $DAY_NIGHT_MODE_PATH)

  if [ -z $DAY_NIGHT ]; then
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
