"""SQLite storage for the SmartPark system.

The data manager writes here, the dashboard reads the history from here.
Run this file directly to print a short report of what is stored.
"""
import os
import sqlite3

import config


def get_connection():
    folder = os.path.dirname(config.DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    return sqlite3.connect(config.DB_PATH, timeout=5)


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS devices (
                device_id   TEXT PRIMARY KEY,
                device_type TEXT NOT NULL,
                last_seen   TEXT NOT NULL,
                status      TEXT
            );
            CREATE TABLE IF NOT EXISTS readings (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        TEXT NOT NULL,
                device_id TEXT NOT NULL,
                metric    TEXT NOT NULL,
                value     TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                ts     TEXT NOT NULL,
                source TEXT NOT NULL,
                event  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                ts      TEXT NOT NULL,
                level   TEXT NOT NULL,
                message TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS occupancy (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                ts       TEXT NOT NULL,
                occupied INTEGER NOT NULL,
                free     INTEGER NOT NULL,
                capacity INTEGER NOT NULL,
                percent  REAL NOT NULL
            );
        """)


# --- writers
def upsert_device(device_id, device_type, ts, status):
    with get_connection() as conn:
        conn.execute("""INSERT INTO devices(device_id, device_type, last_seen, status)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(device_id) DO UPDATE SET
                            last_seen = excluded.last_seen,
                            status = excluded.status""",
                     (device_id, device_type, ts, status))


def add_reading(ts, device_id, metric, value):
    with get_connection() as conn:
        conn.execute("INSERT INTO readings(ts, device_id, metric, value) VALUES (?, ?, ?, ?)",
                     (ts, device_id, metric, str(value)))


def add_event(ts, source, event):
    with get_connection() as conn:
        conn.execute("INSERT INTO events(ts, source, event) VALUES (?, ?, ?)",
                     (ts, source, event))


def add_alert(ts, level, message):
    with get_connection() as conn:
        conn.execute("INSERT INTO alerts(ts, level, message) VALUES (?, ?, ?)",
                     (ts, level, message))


def add_occupancy(ts, occupied, free, capacity, percent):
    with get_connection() as conn:
        conn.execute("""INSERT INTO occupancy(ts, occupied, free, capacity, percent)
                        VALUES (?, ?, ?, ?, ?)""",
                     (ts, occupied, free, capacity, percent))


# --- readers
def occupancy_history(limit=300):
    """Last `limit` occupancy samples, oldest first: [(ts, percent), ...]"""
    with get_connection() as conn:
        rows = conn.execute("""SELECT ts, percent FROM occupancy
                               ORDER BY id DESC LIMIT ?""", (limit,)).fetchall()
    rows.reverse()
    return rows


def recent_alerts(limit=50):
    with get_connection() as conn:
        rows = conn.execute("""SELECT ts, level, message FROM alerts
                               ORDER BY id DESC LIMIT ?""", (limit,)).fetchall()
    rows.reverse()
    return rows


def count(table):
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]


if __name__ == "__main__":
    init_db()
    print("Database:", config.DB_PATH)
    for table in ("devices", "readings", "events", "alerts", "occupancy"):
        print("  %-10s %6d rows" % (table, count(table)))
    print("\nLast alerts:")
    for ts, level, message in recent_alerts(10):
        print("  %s  %-8s %s" % (ts, level, message))
    print("\nDevices:")
    with get_connection() as conn:
        for row in conn.execute("SELECT device_id, device_type, last_seen, status FROM devices"):
            print("  %-8s %-10s %s  %s" % row)
