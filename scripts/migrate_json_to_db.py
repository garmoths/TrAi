#!/usr/bin/env python3
"""Migrate existing JSON DB files into the SQLite-backed `utils.db` store.

This script will read known JSON files (settings.json, guide.json, giveaways.json,
levels.json, uyarilar.json) and import their contents into the DB under keys:
`settings`, `guide`, `giveaways`, `levels`, `uyarilar`.

It will create a timestamped backup of each original file (if present) before importing.
"""
import os
import json
import shutil
from datetime import datetime

from utils import db

FILES = {
    "settings": "settings.json",
    "guide": "guide.json",
    "giveaways": "giveaways.json",
    "levels": "levels.json",
    "uyarilar": "uyarilar.json",
}


def backup(path: str):
    if not os.path.exists(path):
        return None
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dest = f"{path}.backup.{stamp}"
    shutil.copy2(path, dest)
    return dest


def load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def main():
    print("Initializing DB...")
    db.init_db()

    for key, fname in FILES.items():
        if not os.path.exists(fname):
            print(f"Skipping {fname}: not found")
            continue
        print(f"Processing {fname} -> DB key '{key}'")
        data = load_json(fname)
        if data is None:
            print(f"  Could not parse {fname}, skipping")
            continue
        b = backup(fname)
        if b:
            print(f"  Backed up {fname} -> {b}")
        db.kv_set(key, data)
        print(f"  Imported {fname} into DB as '{key}'")

    print("Migration complete.")


if __name__ == '__main__':
    main()
