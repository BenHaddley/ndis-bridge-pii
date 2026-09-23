#!/usr/bin/env bash
# Read-only network/USB observations. Only writes a new evidence directory.
set -u
umask 077

usage() {
  cat <<'HELP'
Usage: bash scripts/collect-diagnostics.sh NEW_OUTPUT_DIRECTORY [USB_INTERFACE]
Run on the Pi. Creates a new directory; refuses an existing path.
No package installs, network changes, active probes, sudo or packet capture.
Optional interface adds driver/device details. Missing tools/permissions are recorded.
Logs include host/network identifiers; review before sharing.
HELP
}

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
  usage
  exit 0
fi
if (( $# < 1 || $# > 2 )); then
  usage >&2
  exit 2
fi
out=$1
iface=${2:-}
if [[ -z $out || ( -n $iface && ! $iface =~ ^[a-zA-Z0-9_.:-]+$ ) ]]; then
  printf 'Invalid output directory or interface name.\n' >&2
  exit 2
fi
# mkdir without -p deliberately refuses existing directories, including symlinks.
if ! mkdir -- "$out"; then
  printf 'Choose a new output directory inside an existing parent.\n' >&2
  exit 1
fi
summary="$out/summary.txt"
printf 'Collection UTC: %s\nHardware test verdict: NOT DETERMINED\n' "$(date -u +%FT%TZ)" > "$summary"
failures=0
capture() {
  local label=$1 rc
  shift
  if ! command -v "$1" >/dev/null 2>&1; then
    printf '%s: unavailable (%s)\n' "$label" "$1" >> "$summary"
    failures=$((failures + 1))
    return
  fi
  "$@" > "$out/$label.txt" 2>&1
  rc=$?
  printf '%s: exit %s\n' "$label" "$rc" >> "$summary"
  if (( rc != 0 )); then failures=$((failures + 1)); fi
}
capture os cat /etc/os-release
capture kernel uname -a
capture usb lsusb
capture usb-tree lsusb -t
capture links ip -details link show
capture addresses ip -brief address show
capture routes ip route show table all
capture ipv6-routes ip -6 route show table all
capture nm-version nmcli --version
capture nm-devices nmcli device status
capture nm-addressing nmcli -f GENERAL,IP4,DHCP4,IP6,DHCP6 device show
capture nm-profiles nmcli -f NAME,UUID,TYPE,DEVICE connection show
capture kernel-log journalctl -k -b -n 200 --no-pager
if [[ -n $iface ]]; then
  capture interface ip -s link show dev "$iface"
  capture driver ethtool -i "$iface"
  capture device-properties udevadm info --query=property --path="/sys/class/net/$iface"
fi
printf 'Unavailable/failed observations: %s\n' "$failures" >> "$summary"
printf 'Evidence saved to %s. Read summary.txt; collection is not a hardware pass.\n' "$out"
