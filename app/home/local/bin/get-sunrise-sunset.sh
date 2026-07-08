#!/bin/sh

source /usr/lib/gnome-mode-shift/shared-variables.sh

#check for dependencies [redshift, netcap]
if ! command -v redshift &> /dev/null; then
  echo "redshift is not found. Did you check if it's installed?";
  exit 33
fi

if ! command -v netcap &> /dev/null; then
  echo 'missing dependency netcap (nc)'
  exit 33
fi

if nc -zw1 google.com 443; then
  echo "we have connectivity"
else
  echo "we do not have connection"
  exit 33
fi

lookup_day_or_night=$(redshift -vp | grep -oP '(?<=Period: )\w+$|(?<=Period: )\w+(?=\))$' | tr [A-Z] [a-z]) # tr API tr from, to

if [[ $lookup_day_or_night == $RDSHFT_DAY ]]; then
  current=$DAY_MODE
elif [[ $lookup_day_or_night == $RDSHFT_NIGHT ]]; then
  current=$NIGHT_MODE
fi

echo "current_day_night::: ${current}"

save_configuration() {
  local -r day_night_mode=$(cat $DAY_NIGHT_MODE_PATH)

  if [[ -n $current && $day_night_mode != $current ]]; then
    if [[ ! -f  $DAY_NIGHT_MODE_PATH ]]; then
      touch $DAY_NIGHT_MODE_PATH
    fi

    echo $current > $DAY_NIGHT_MODE_PATH
    export DAY_NIGHT=$current
  else
    # does nothing
    echo "The current state is the same"
  fi
}

save_configuration
