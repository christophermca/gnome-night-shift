#! /bin/bash
testNetworkConnection() {
  if command -v curl &> /dev/null; then
    curl -s -w "%{http_code}\n" -f https://archlinux.org  &> /dev/null
  else
    echo "Missing command `curl`"
    exit 33;
  fi
}
