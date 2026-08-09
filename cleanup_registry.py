#!/usr/bin/env python3
"""
SENTINEL — Registry Cleanup

Removes rows that should never have been recorded as devices, plus
demo/seed data left over from testing.

The registry is append-only: once anything is written it stays forever.
That means broadcast/multicast MACs, seeded demo devices, and threat
events from months-old test runs keep inflating the dashboard counts.

Dry-run by default. Nothing is deleted without --apply, and --apply
always writes a timestamped backup of the database first.

    python cleanup_registry.py            # show what would be removed
    python cleanup_registry.py --apply    # back up, then remove
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "sentinel.db"

# MACs hardcoded by seed_data.py — real hardware never uses these.
SEED_MACS = {
    "aa:bb:cc:dd:ee:ff",
    "00:11:22:33:44:55",
    "11:22:33:44:55:66",
    "de:ad:be:ef:ca:fe",
}


def is_group_mac(mac: str | None) -> bool:
    """Broadcast or multicast MAC — a destination group, not a device."""
    if not mac:
        return True
    parts = mac.strip().lower().split(":")
    if len(parts) != 6:
        return True
    try:
        first = int(parts[0], 16)
    except ValueError:
        return True
    if first & 0x01:
        return True
    return all(p == "00" for p in parts)


def classify(rows, stale_days: int):
    """Split device rows into (junk_with_reason, keep)."""
    junk, keep = [], []
    cutoff = datetime.utcnow() - timedelta(days=stale_days)

    for device_id, mac, ip, vendor, last_seen in rows:
        reason = None
        norm_mac = (mac or "").strip().lower()

        if is_group_mac(mac):
            reason = "broadcast/multicast MAC"
        elif norm_mac in SEED_MACS:
            reason = "seed/demo data"
        elif last_seen:
            try:
                seen = datetime.fromisoformat(last_seen)
                if seen < cutoff:
                    reason = f"stale (last seen {seen.date()})"
            except ValueError:
                pass

        (junk if reason else keep).append((device_id, mac, ip, vendor, reason))

    return junk, keep


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean the SENTINEL device registry")
    parser.add_argument("--apply", action="store_true",
                        help="Actually delete (default is dry-run)")
    parser.add_argument("--stale-days", type=int, default=30,
                        help="Treat devices unseen for this many days as stale (default: 30)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT device_id, mac, ip, vendor, last_seen FROM devices")
    junk, keep = classify(cur.fetchall(), args.stale_days)

    cur.execute("SELECT COUNT(*) FROM threat_events WHERE LOWER(device_id) IN ({})".format(
        ",".join("?" * len(SEED_MACS))), tuple(SEED_MACS))
    seed_threats = cur.fetchone()[0]

    print(f"\n  Database: {DB_PATH}")
    print(f"  {'DRY RUN — nothing will be deleted' if not args.apply else 'APPLYING CHANGES'}\n")

    print(f"  REMOVE ({len(junk)} devices):")
    if junk:
        for device_id, mac, ip, vendor, reason in junk:
            print(f"    {ip or '—':<28} {mac:<20} {reason}")
    else:
        print("    (nothing)")

    print(f"\n  KEEP ({len(keep)} devices):")
    for device_id, mac, ip, vendor, _ in keep:
        print(f"    {ip or '—':<28} {mac:<20} {vendor or ''}")

    print(f"\n  Threat events attached to seed devices: {seed_threats}")

    if not args.apply:
        print("\n  Re-run with --apply to delete.\n")
        conn.close()
        return 0

    backup = DB_PATH.with_suffix(f".db.backup-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(DB_PATH, backup)
    print(f"\n  Backup written: {backup}")

    ids = [d[0] for d in junk]
    if ids:
        cur.executemany("DELETE FROM devices WHERE device_id = ?", [(i,) for i in ids])
    cur.execute("DELETE FROM threat_events WHERE LOWER(device_id) IN ({})".format(
        ",".join("?" * len(SEED_MACS))), tuple(SEED_MACS))
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM devices")
    devices_left = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM threat_events")
    threats_left = cur.fetchone()[0]
    conn.close()

    print(f"  Removed {len(ids)} devices and {seed_threats} threat events.")
    print(f"  Registry now holds {devices_left} devices, {threats_left} threat events.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
