#!/usr/bin/env bash
# Open TCP 8000 on Oracle Cloud Ubuntu OS firewall (iptables).
# Run ON the VPS as a user with sudo:
#   bash scripts/open-port-8000.sh
#
# Security list / NSG must also allow 8000. This only fixes the OS firewall.
# Retest from Windows: http://PUBLIC_IP:8000 — do NOT curl the public IP from the VPS itself.

set -euo pipefail

PORT="${PORT:-8000}"

echo "=== Current INPUT chain ==="
sudo iptables -L INPUT -n -v --line-numbers
echo
echo "=== INPUT rules (iptables -S) ==="
sudo iptables -S INPUT
echo

if sudo iptables -C INPUT -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null; then
  echo "Rule already present: ACCEPT tcp dpt:$PORT"
else
  # Insert before the first REJECT if present; otherwise insert at top.
  REJECT_LINE="$(sudo iptables -L INPUT -n --line-numbers | awk '/REJECT|DROP/ {print $1; exit}')"
  if [[ -n "${REJECT_LINE:-}" ]]; then
    echo "Inserting ACCEPT for TCP $PORT before rule line $REJECT_LINE"
    sudo iptables -I INPUT "$REJECT_LINE" -p tcp --dport "$PORT" -j ACCEPT
  else
    echo "No REJECT/DROP found; inserting ACCEPT for TCP $PORT at top of INPUT"
    sudo iptables -I INPUT -p tcp --dport "$PORT" -j ACCEPT
  fi
fi

echo
echo "=== INPUT after change (8000 / 22 / REJECT) ==="
sudo iptables -L INPUT -n --line-numbers | grep -E "8000|REJECT|DROP|dpt:22|Chain" || true
echo

if command -v nft >/dev/null 2>&1; then
  echo "=== nftables ruleset (if any) ==="
  sudo nft list ruleset 2>/dev/null | head -n 80 || echo "(no nft rules or empty)"
  echo
fi

echo "=== Persist rules ==="
if command -v netfilter-persistent >/dev/null 2>&1; then
  sudo netfilter-persistent save
  echo "Saved via netfilter-persistent"
elif dpkg -l iptables-persistent >/dev/null 2>&1; then
  sudo netfilter-persistent save
  echo "Saved via iptables-persistent"
else
  echo "Installing iptables-persistent (noninteractive)..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
  echo iptables-persistent iptables-persistent/autosave_v4 boolean true | sudo debconf-set-selections
  echo iptables-persistent iptables-persistent/autosave_v6 boolean true | sudo debconf-set-selections
  sudo netfilter-persistent save
  echo "Installed and saved via netfilter-persistent"
fi

echo
echo "Done. From your Windows PC (not from this VPS), open:"
echo "  http://YOUR_PUBLIC_IP:${PORT}/"
echo
echo "If it still times out, check the VNIC Network Security Group in OCI Console"
echo "for ingress TCP ${PORT} from 0.0.0.0/0."
