#!/bin/bash

source /usr/lib/gnome-night-shift/shared-variables.sh


is_day_or_night() {
  start_stop="$(cat ${STATE_FOLDER}/times)"
  IFS="," read -r start stop <<< "$start_stop"
  current_time=`date '+%H:%M'`
  echo "---" $current_time $start $stop

  if [[ "$current_time" > "$stop" ]]; then
    DAY_NIGHT='day'
  fi

  if [[ "$current_time" > "$start" ]]; then
    DAY_NIGHT='night'
  fi

  save_configuration() {
    local -r day_night_mode=$(cat $IS_DAY_OR_NIGHT)

    if [[ -n $DAY_NIGHT && $day_night_mode != $DAY_NIGHT ]]; then
      if [[ ! -f  $IS_DAY_OR_NIGHT ]]; then
        touch $IS_DAY_OR_NIGHT
      fi

      echo $DAY_NIGHT > $IS_DAY_OR_NIGHT
      export DAY_NIGHT=$DAY_NIGHT
    else
      # does nothing
      echo "The current state is the same"
    fi
  }

save_configuration

}

is_day_or_night
