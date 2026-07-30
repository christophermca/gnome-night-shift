#!/bin/sh

#-----#
# redshift expected search terms
# subject to change depending on the redshift api
#-----#
RDSHFT_NIGHT="night"
RDSHFT_DAY="daytime"

#-----#
# theme_switcher
#-----#

NIGHT_MODE="night"
DAY_MODE="day"
STATE_FOLDER="/home/${USER}/.local/state/gnome-night-shift"
IS_DAY_OR_NIGHT="${STATE_FOLDER}/is-day-or-night"
