import os
import sys
import subprocess
import json

HOSTS_PATH   = r"C:\Windows\System32\drivers\etc\hosts"
REDIRECT_IP  = "0.0.0.0"
BLOCK_MARKER = "# FocusGuard"

_INSTALL_CONFIG = os.path.join(
    os.getenv("PROGRAMFILES", "C:\\Program Files"), "FocusGuard", "config.json"
)
if getattr(sys, 'frozen', False):
    _LOCAL_CONFIG = os.path.join(os.path.dirname(sys.executable), "config.json")
else:
    _LOCAL_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

CONFIG_PATH = _INSTALL_CONFIG if os.path.exists(_INSTALL_CONFIG) else _LOCAL_CONFIG


def _fallback_sites():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f).get("blocked_sites", [])
    except Exception:
        return []


def _read_hosts():
    with open(HOSTS_PATH, "r") as f:
        return f.readlines()


def _write_hosts(lines):
    with open(HOSTS_PATH, "w") as f:
        f.writelines(lines)


def block_sites(sites=None):
    """Block sites via hosts file + firewall. Uses provided list or config fallback."""
    if not sites:
        sites = _fallback_sites()
    lines = _read_hosts()
    lines = [l for l in lines if BLOCK_MARKER not in l]
    for site in sites:
        lines.append(f"{REDIRECT_IP} {site} {BLOCK_MARKER}\n")
    _write_hosts(lines)
    _apply_firewall_rules(sites, block=True)


def unblock_sites(sites=None):
    """Remove all FocusGuard entries from hosts file and firewall."""
    lines = _read_hosts()
    lines = [l for l in lines if BLOCK_MARKER not in l]
    _write_hosts(lines)
    if not sites:
        sites = _fallback_sites()
    _apply_firewall_rules(sites, block=False)


def _apply_firewall_rules(sites, block=True):
    for site in sites:
        rule = f"FocusGuard-{site}"
        if block:
            cmd = (f'netsh advfirewall firewall add rule name="{rule}" '
                   f'dir=out action=block remotehost={site} enable=yes')
        else:
            cmd = f'netsh advfirewall firewall delete rule name="{rule}"'
        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
