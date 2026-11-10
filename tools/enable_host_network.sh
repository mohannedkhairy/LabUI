#!/usr/bin/env bash
# One-time privileged host setup. Application units run as the ordinary user.
set -euo pipefail
if [[ "$EUID" != 0 || $# != 1 ]]; then
  echo "Usage (administrator): $0 <labui-user>" >&2
  exit 2
fi
LABUI_USER="$1"
id "$LABUI_USER" >/dev/null
if [[ "$(id -u "$LABUI_USER")" == 0 ]]; then
  echo "LabUI must run under an ordinary user account." >&2
  exit 2
fi
/usr/share/omarchy/bin/omarchy pkg add tailscale
/usr/bin/systemctl enable --now tailscaled.service
/usr/bin/tailscale set --operator="$LABUI_USER"
/usr/bin/loginctl enable-linger "$LABUI_USER"
echo "Tailscale daemon and LabUI boot persistence are configured."
