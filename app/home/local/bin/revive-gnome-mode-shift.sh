#!/bin/bash
TIMER="gnome-mode-shift.timer"

run_cmd() {
	if [ $# -eq 0 ]; then
		echo "run_cmd() is missing arguments; exiting 33"
		exit 33
	fi
	_CMD=$1;
	# Find all active human user IDs logged into graphical sessions
	for UID_USER in $(loginctl list-users --no-legend | awk '{print $1}'); do
	    # Verify the user has an active runtime D-Bus path available

	    #Guard against missing CMD
	    if [ -z "$_CMD" ]; then
		echo missing $_CMD
	    fi
	    echo "USE this CMD: $_CMD"
	      if [ -d "/run/user/${UID_USER}" ]; then
		  # Run systemctl inside the user's specific context without needing passwords
		  sudo -u "#${UID_USER}" XDG_RUNTIME_DIR="/run/user/${UID_USER}" systemctl --user "$_CMD" "$TIMER"
	  else
		  echo "missing directory"
	      fi
	done
}

INTERFACE="$1"
ACTION="$2"
echo "$INTERFACE, $CMD, $ACTION, $TIMER"

case "$ACTION" in
  up)
    echo "case1"
    #if [ "$(nmcli networking connectivity)" = "full" ]; then
      CMD="start"
      run_cmd $CMD
    #fi
    ;;
  down)
    echo "case2"
    CMD="stop"
    run_cmd $CMD
    ;;
esac

