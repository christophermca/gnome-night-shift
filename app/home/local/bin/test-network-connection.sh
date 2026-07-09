#! /bin/bash
handleOffline() {
  echo 'offline';
  systemctl --user stop gnome-mode-shift.timer;
  exit 33;
}

testNetworkConnection() {

# if ! command -v netcap &> /dev/null; then
#   echo 'missing dependency netcap (nc)'
#   exit 33
# fi

if command -v ping &> /dev/null; then
  ping -w 1 -c 1 8.8.8.8 > /dev/null 2>&1 || handleOffline
else
  echo "Missing command `ping`"
  exit 33;
fi
}
