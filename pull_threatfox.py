#!/usr/bin/env python3
"""
pull_threatfox.py  —  runs inside GitHub Actions (NOT on your server)

It reads your abuse.ch Auth-Key from an environment variable (provided by
GitHub Secrets), calls the ThreatFox API, defangs the indicators so they're
safe to display, slims them to the fields the website card needs, and writes
threatfox.json into the repo. The Action then commits that file.

The Auth-Key is NEVER written to the file, the repo, or the logs.
"""

import os
import sys
import json
import time
import re
import urllib.request

API_URL   = "https://threatfox-api.abuse.ch/api/v1/"
OUT_FILE  = "threatfox.json"          # written to repo root
AUTH_KEY  = os.environ.get("THREATFOX_AUTH_KEY", "")
DAYS_BACK = 1                          # IOCs from the last N days
MAX_ROWS  = 40                         # how many to keep for the card


def defang(value, ioc_type):
    """Make indicators non-clickable so the page can't route anyone to live C2."""
    if not value:
        return ""
    v = value
    if ioc_type in ("url", "domain", "ip:port"):
        v = v.replace("http://", "hxxp://").replace("https://", "hxxps://")
        if ioc_type == "url":
            v = v.replace(".", "[.]")
        else:
            # bracket the last dot only, keeps it readable
            v = re.sub(r"\.(?=[^.]*$)", "[.]", v)
    if ioc_type.endswith("hash"):
        v = (v[:12] + "..." + v[-4:]) if len(v) > 20 else v
    return v


def fetch():
    if not AUTH_KEY:
        print("ERROR: THREATFOX_AUTH_KEY is not set", file=sys.stderr)
        sys.exit(1)
    body = json.dumps({"query": "get_iocs", "days": DAYS_BACK}).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={"Auth-Key": AUTH_KEY, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("query_status") != "ok":
        print(f"ERROR: API status {data.get('query_status')}", file=sys.stderr)
        sys.exit(1)
    return data.get("data", [])


def normalize(rows):
    out = []
    for i in rows[:MAX_ROWS]:
        t = i.get("ioc_type", "")
        out.append({
            "ioc":        defang(i.get("ioc", ""), t),
            "type":       t,
            "malware":    i.get("malware_printable") or i.get("malware") or "Unknown",
            "confidence": i.get("confidence_level", 0),
            "first_seen": i.get("first_seen", ""),
        })
    return out


def main():
    iocs = normalize(fetch())
    envelope = {
        "updated": int(time.time()),
        "source":  "abuse.ch / ThreatFox",
        "count":   len(iocs),
        "iocs":    iocs,
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(envelope, f, ensure_ascii=False, separators=(",", ":"))
    print(f"wrote {len(iocs)} IOCs to {OUT_FILE}")


if __name__ == "__main__":
    main()
