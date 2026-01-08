#!/usr/bin/env python3
# tracker.py — PokerOK Session Tracker (single-file CLI)
# Python 3.10+
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, date, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------
# Constants / Defaults
# ---------------------------

DEFAULT_CONFIG = {
    "currency": "USD",
    "data_file": "sessions.json",
    "timezone": "Europe/Madrid",  # stored for display; stdlib doesn't handle IANA without zoneinfo use
    "date_format": "%Y-%m-%d",
    "week_start": "monday",
}

ALLOWED_GAMES = {"NLH", "PLO"}

STAKE_RE = re.compile(r"^(NL|PLO)\d+$", re.IGNORECASE)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")


# ---------------------------
# Error handling
# ---------------------------

class TrackerError(Exception):
    """Base error for user-facing messages."""


def die(msg: str, code: int = 1) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    raise SystemExit(code)


# ---------------------------
# Data model
# ---------------------------

@dataclass
class Session:
    id: int
    room: str
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    duration_min: int
    stake: str
    game: str
    profit: float
    currency: str
    hands: Optional[int] = None
    tables: Optional[int] = None
    notes: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Session":
        return Session(**d)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------
# Storage / Config
# ---------------------------

def script_dir() -> Path:
    return Path(__file__).resolve().parent


def load_or_init_config(cfg_path: Path) -> Dict[str, Any]:
    if not cfg_path.exists():
        cfg_path.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
        return dict(DEFAULT_CONFIG)

    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        if not isinstance(cfg, dict):
            raise ValueError("config is not an object")
    except Exception as e:
        raise TrackerError(f"Failed to read config.json: {e}")

    # merge defaults (forward-compatible)
    merged = dict(DEFAULT_CONFIG)
    merged.update(cfg)
    # persist merged if new keys added
    if merged != cfg:
        cfg_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def load_or_init_sessions(data_path: Path) -> List[Session]:
    if not data_path.exists():
        data_path.write_text("[]", encoding="utf-8")
        return []

    try:
        raw = json.loads(data_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("sessions.json is not a list")
        return [Session.from_dict(x) for x in raw]
    except Exception as e:
        raise TrackerError(f"Failed to read {data_path.name}: {e}")


def save_sessions(data_path: Path, sessions: List[Session]) -> None:
    data_path.write_text(
        json.dumps([s.to_dict() for s in sessions], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def next_id(sessions: List[Session]) -> int:
    return (max((s.id for s in sessions), default=0) + 1)


# ---------------------------
# Parsing / Validation
# ---------------------------

def parse_date_str(s: str) -> date:
    if not DATE_RE.match(s):
        raise TrackerError("date must be in YYYY-MM-DD format")
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise TrackerError("invalid date value")


def parse_time_str(s: str) -> time:
    if not TIME_RE.match(s):
        raise TrackerError("time must be in HH:MM format")
    try:
        return datetime.strptime(s, "%H:%M").time()
    except ValueError:
        raise TrackerError("invalid time value")


def validate_game(game: str) -> str:
    g = game.strip().upper()
    if g not in ALLOWED_GAMES:
        raise TrackerError(f"game must be one of: {', '.join(sorted(ALLOWED_GAMES))}")
    return g


def validate_stake(stake: str) -> str:
    st = stake.strip()
    if not st:
        raise TrackerError("stake must be non-empty")
    # recommended but not strict — still provide warning-ish validation
    if not STAKE_RE.match(st):
        # allow other stake formats but keep minimal validation
        # If you prefer strictness, replace with raise TrackerError(...)
        return st
    return st.upper()


def parse_float(s: str) -> float:
    try:
        return float(s)
    except ValueError:
        raise TrackerError("profit must be a number (e.g., 12.5 or -7.25)")


def parse_nonneg_int(s: str, field_name: str) -> int:
    try:
        v = int(s)
    except ValueError:
        raise TrackerError(f"{field_name} must be an integer")
    if v < 0:
        raise TrackerError(f"{field_name} must be >= 0")
    return v


def calc_duration_minutes(start_hm: str, end_hm: str) -> int:
    st = parse_time_str(start_hm)
    en = parse_time_str(end_hm)
    # anchor at arbitrary date
    base = date(2000, 1, 1)
    dt_start = datetime.combine(base, st)
    dt_end = datetime.combine(base, en)
    if dt_end < dt_start:
        dt_end += timedelta(days=1)
    delta = dt_end - dt_start
    mins = int(round(delta.total_seconds() / 60.0))
    return max(mins, 0)


def now_iso_local() -> str:
    # local timestamp with offset if available
    # Using local timezone offset from system; config timezone is informational.
    return datetime.now().astimezone().isoformat(timespec="seconds")


def prompt_input(label: str, validator, optional: bool = False, default: Optional[str] = None) -> Optional[Any]:
    while True:
        suffix = ""
        if default is not None:
            suffix = f" [{default}]"
        raw = input(f"{label}{suffix}: ").strip()
        if not raw and default is not None:
            raw = default
        if not raw:
            if optional:
                return None
            print("  This field is required.")
            continue
        try:
            return validator(raw)
        except TrackerError as e:
            print(f"  {e}")


# ---------------------------
# Formatting helpers
# ---------------------------

def fmt_money(v: float) -> str:
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.2f}"


def fmt_duration(mins: int) -> str:
    h = mins // 60
    m = mins % 60
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def print_table(rows: List[List[str]], headers: List[str]) -> None:
    if not rows:
        print("No sessions found.")
        return
    cols = list(zip(*([headers] + rows)))
    widths = [max(len(str(x)) for x in col) for col in cols]
    def line(items: List[str]) -> str:
        return " | ".join(str(items[i]).ljust(widths[i]) for i in range(len(items)))
    print(line(headers))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(line(r))


def session_row(s: Session) -> List[str]:
    start_end = f"{s.start_time}-{s.end_time}"
    return [
        str(s.id),
        s.date,
        s.stake,
        s.game,
        start_end,
        str(s.duration_min),
        f"{fmt_money(s.profit)} {s.currency}",
        "" if s.hands is None else str(s.hands),
        "" if s.tables is None else str(s.tables),
        "" if not s.notes else (s.notes if len(s.notes) <= 30 else s.notes[:27] + "..."),
    ]


# ---------------------------
# Filtering / Periods
# ---------------------------

def filter_sessions(
    sessions: List[Session],
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    stake: Optional[str] = None,
    game: Optional[str] = None,
) -> List[Session]:
    fd = parse_date_str(from_date).toordinal() if from_date else None
    td = parse_date_str(to_date).toordinal() if to_date else None
    st = stake.strip().upper() if stake else None
    gm = game.strip().upper() if game else None

    out: List[Session] = []
    for s in sessions:
        d_ord = parse_date_str(s.date).toordinal()
        if fd is not None and d_ord < fd:
            continue
        if td is not None and d_ord > td:
            continue
        if st is not None and s.stake.strip().upper() != st:
            continue
        if gm is not None and s.game.strip().upper() != gm:
            continue
        out.append(s)
    return out


def compute_period_range(period: str) -> Tuple[str, str]:
    today = datetime.now().date()
    p = period.lower().strip()

    if p == "all":
        return "0001-01-01", "9999-12-31"
    if p == "day":
        return today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    if p == "week":
        # week starts Monday by default (per config, but keep simple)
        # Monday=0
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    if p == "month":
        start = today.replace(day=1)
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1)
        else:
            next_month = start.replace(month=start.month + 1)
        end = next_month - timedelta(days=1)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    if p == "year":
        start = today.replace(month=1, day=1)
        end = today.replace(month=12, day=31)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    raise TrackerError("period must be one of: day, week, month, year, all")


# ---------------------------
# Commands implementation
# ---------------------------

def cmd_add(args: argparse.Namespace, cfg: Dict[str, Any], sessions: List[Session], data_path: Path) -> None:
    # Determine whether to prompt interactively
    interactive = any(getattr(args, k) is None for k in ["date", "start", "end", "profit", "stake", "game"])

    if interactive:
        print("Interactive add mode (PokerOK)")
        d = prompt_input("Date (YYYY-MM-DD)", lambda x: parse_date_str(x).strftime("%Y-%m-%d"))
        st = prompt_input("Start time (HH:MM)", lambda x: parse_time_str(x).strftime("%H:%M"))
        en = prompt_input("End time (HH:MM)", lambda x: parse_time_str(x).strftime("%H:%M"))
        pr = prompt_input("Profit", parse_float)
        sk = prompt_input("Stake (e.g., NL10 / PLO25)", validate_stake)
        gm = prompt_input("Game (NLH/PLO)", validate_game)
        hands = prompt_input("Hands (optional)", lambda x: parse_nonneg_int(x, "hands"), optional=True)
        tables = prompt_input("Tables (optional)", lambda x: parse_nonneg_int(x, "tables"), optional=True)
        notes = input("Notes (optional): ").strip() or None
    else:
        d = parse_date_str(args.date).strftime("%Y-%m-%d")
        st = parse_time_str(args.start).strftime("%H:%M")
        en = parse_time_str(args.end).strftime("%H:%M")
        pr = parse_float(str(args.profit))
        sk = validate_stake(args.stake)
        gm = validate_game(args.game)
        hands = args.hands if args.hands is None else parse_nonneg_int(str(args.hands), "hands")
        tables = args.tables if args.tables is None else parse_nonneg_int(str(args.tables), "tables")
        notes = args.notes.strip() if args.notes else None
        if notes == "":
            notes = None

    dur = calc_duration_minutes(st, en)

    sid = next_id(sessions)
    ts = now_iso_local()
    s = Session(
        id=sid,
        room="PokerOK",
        date=d,
        start_time=st,
        end_time=en,
        duration_min=dur,
        stake=sk,
        game=gm,
        profit=float(pr),
        currency=str(cfg.get("currency", "USD")),
        hands=hands,
        tables=tables,
        notes=notes,
        created_at=ts,
        updated_at=ts,
    )
    sessions.append(s)
    save_sessions(data_path, sessions)

    print(f"Added session #{s.id}: {s.date} {s.stake} {s.game} {s.start_time}-{s.end_time} "
          f"({s.duration_min}m) Profit: {fmt_money(s.profit)} {s.currency}")


def cmd_list(args: argparse.Namespace, sessions: List[Session]) -> None:
    filtered = filter_sessions(sessions, args.from_date, args.to_date, args.stake, args.game)
    reverse = True
    if args.asc:
        reverse = False
    filtered.sort(key=lambda s: (s.date, s.start_time, s.id), reverse=reverse)

    limit = args.limit
    if limit is not None and limit >= 0:
        filtered = filtered[:limit]

    headers = ["id", "date", "stake", "game", "start-end", "dur_min", "profit", "hands", "tables", "notes"]
    rows = [session_row(s) for s in filtered]
    print_table(rows, headers)


def compute_stats_block(sessions: List[Session]) -> Dict[str, Any]:
    count = len(sessions)
    total_profit = sum(s.profit for s in sessions)
    total_min = sum(s.duration_min for s in sessions)
    avg_profit = (total_profit / count) if count else 0.0
    total_hours = total_min / 60.0 if total_min else 0.0
    profit_per_hour = (total_profit / total_hours) if total_hours > 0 else 0.0

    hands_total = sum((s.hands or 0) for s in sessions)
    hands_known = any(s.hands is not None for s in sessions)
    hands_per_hour = (hands_total / total_hours) if (hands_known and total_hours > 0) else None

    best = sorted(sessions, key=lambda s: s.profit, reverse=True)[:3]
    worst = sorted(sessions, key=lambda s: s.profit)[:3]

    return {
        "count": count,
        "total_profit": total_profit,
        "avg_profit": avg_profit,
        "total_min": total_min,
        "profit_per_hour": profit_per_hour,
        "hands_total": hands_total if hands_known else None,
        "hands_per_hour": hands_per_hour,
        "best": best,
        "worst": worst,
    }


def print_stats(title: str, block: Dict[str, Any], currency: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    print(f"Sessions: {block['count']}")
    print(f"Total profit: {fmt_money(block['total_profit'])} {currency}")
    print(f"Avg profit/session: {fmt_money(block['avg_profit'])} {currency}")
    print(f"Total duration: {fmt_duration(block['total_min'])} ({block['total_min']} min)")
    print(f"Profit/hour: {fmt_money(block['profit_per_hour'])} {currency}/h")
    if block["hands_total"] is not None:
        print(f"Hands (total): {block['hands_total']}")
        if block["hands_per_hour"] is not None:
            print(f"Hands/hour: {block['hands_per_hour']:.0f}")

    def show_list(label: str, items: List[Session]) -> None:
        print(f"\n{label}:")
        if not items:
            print("  (none)")
            return
        for s in items:
            print(f"  #{s.id} {s.date} {s.stake} {s.game} {fmt_money(s.profit)} {s.currency}")

    show_list("Top 3 best sessions", block["best"])
    show_list("Top 3 worst sessions", block["worst"])
    print("")


def cmd_stats(args: argparse.Namespace, cfg: Dict[str, Any], sessions: List[Session]) -> None:
    if args.from_date or args.to_date:
        fd = args.from_date
        td = args.to_date
        if fd:
            parse_date_str(fd)
        if td:
            parse_date_str(td)
        if fd is None:
            fd = "0001-01-01"
        if td is None:
            td = "9999-12-31"
    else:
        fd, td = compute_period_range(args.period)

    filtered = filter_sessions(sessions, fd, td, args.stake, args.game)
    filtered.sort(key=lambda s: (s.date, s.start_time, s.id))

    currency = str(cfg.get("currency", "USD"))
    title = f"Stats for {fd} .. {td}"
    overall = compute_stats_block(filtered)
    print_stats(title, overall, currency)

    by = (args.by or "").strip().lower()
    if by in ("stake", "game") and filtered:
        groups: Dict[str, List[Session]] = {}
        for s in filtered:
            key = s.stake if by == "stake" else s.game
            groups.setdefault(key, []).append(s)

        for key in sorted(groups.keys()):
            blk = compute_stats_block(groups[key])
            print_stats(f"Group: {by} = {key}", blk, currency)
    elif args.by:
        raise TrackerError("--by must be one of: stake, game")


def find_session_by_id(sessions: List[Session], sid: int) -> Session:
    for s in sessions:
        if s.id == sid:
            return s
    raise TrackerError(f"session id {sid} not found")


def cmd_edit(args: argparse.Namespace, cfg: Dict[str, Any], sessions: List[Session], data_path: Path) -> None:
    sid = args.id
    s = find_session_by_id(sessions, sid)

    changed = False

    if args.date is not None:
        s.date = parse_date_str(args.date).strftime("%Y-%m-%d")
        changed = True
    if args.start is not None:
        s.start_time = parse_time_str(args.start).strftime("%H:%M")
        changed = True
    if args.end is not None:
        s.end_time = parse_time_str(args.end).strftime("%H:%M")
        changed = True
    if args.profit is not None:
        s.profit = parse_float(str(args.profit))
        changed = True
    if args.stake is not None:
        s.stake = validate_stake(args.stake)
        changed = True
    if args.game is not None:
        s.game = validate_game(args.game)
        changed = True
    if args.hands is not None:
        s.hands = parse_nonneg_int(str(args.hands), "hands")
        changed = True
    if args.tables is not None:
        s.tables = parse_nonneg_int(str(args.tables), "tables")
        changed = True
    if args.notes is not None:
        s.notes = args.notes.strip() or None
        changed = True

    # If any of start/end updated, recompute duration
    if args.start is not None or args.end is not None:
        s.duration_min = calc_duration_minutes(s.start_time, s.end_time)
        changed = True

    if not changed:
        print("Nothing to update. Provide fields to edit.")
        return

    s.currency = str(cfg.get("currency", s.currency))
    s.updated_at = now_iso_local()
    save_sessions(data_path, sessions)

    print(f"Updated session #{s.id}: {s.date} {s.stake} {s.game} {s.start_time}-{s.end_time} "
          f"({s.duration_min}m) Profit: {fmt_money(s.profit)} {s.currency}")


def cmd_delete(args: argparse.Namespace, sessions: List[Session], data_path: Path) -> None:
    sid = args.id
    before = len(sessions)
    sessions[:] = [s for s in sessions if s.id != sid]
    if len(sessions) == before:
        raise TrackerError(f"session id {sid} not found")
    save_sessions(data_path, sessions)
    print(f"Deleted session #{sid}.")


def cmd_export(args: argparse.Namespace, sessions: List[Session]) -> None:
    fmt = (args.format or "csv").lower().strip()
    if fmt != "csv":
        raise TrackerError("only csv export is supported")

    out_path = Path(args.out or "sessions_export.csv").resolve()

    # union of keys
    rows = [s.to_dict() for s in sessions]
    if not rows:
        # still export header
        fieldnames = list(Session.__dataclass_fields__.keys())
    else:
        # keep stable ordering based on dataclass
        fieldnames = list(Session.__dataclass_fields__.keys())

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"Exported {len(sessions)} sessions to {out_path}")


def cmd_config(args: argparse.Namespace, cfg: Dict[str, Any], cfg_path: Path) -> None:
    if args.set is None:
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        return

    if "=" not in args.set:
        raise TrackerError("--set must be in key=value format")
    key, value = args.set.split("=", 1)
    key = key.strip()
    value = value.strip()

    if key not in DEFAULT_CONFIG:
        raise TrackerError(f"unknown config key: {key}")

    # basic type coercion for known keys
    if key in ("data_file", "currency", "timezone", "date_format", "week_start"):
        cfg[key] = value
    else:
        cfg[key] = value

    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Config updated: {key}={value}")


# ---------------------------
# Argparse
# ---------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tracker.py",
        description="PokerOK Session Tracker (CLI, single-file).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # add
    pa = sub.add_parser("add", help="Add a session (flags or interactive if missing required args).")
    pa.add_argument("--date", help="YYYY-MM-DD")
    pa.add_argument("--start", help="HH:MM")
    pa.add_argument("--end", help="HH:MM")
    pa.add_argument("--profit", help="Profit number, e.g. 12.5 or -7.25")
    pa.add_argument("--stake", help="Stake, e.g. NL10, PLO25")
    pa.add_argument("--game", help="Game type: NLH or PLO")
    pa.add_argument("--hands", help="Hands count (optional)")
    pa.add_argument("--tables", help="Tables count (optional)")
    pa.add_argument("--notes", help="Notes (optional)")
    pa.set_defaults(func="add")

    # list
    pl = sub.add_parser("list", help="List sessions with optional filters.")
    pl.add_argument("--from", dest="from_date", help="YYYY-MM-DD (start date)")
    pl.add_argument("--to", dest="to_date", help="YYYY-MM-DD (end date)")
    pl.add_argument("--stake", help="Filter by stake (exact match)")
    pl.add_argument("--game", help="Filter by game (NLH/PLO)")
    pl.add_argument("--limit", type=int, default=20, help="Max rows to display (default 20). Use -1 for all.")
    order = pl.add_mutually_exclusive_group()
    order.add_argument("--desc", action="store_true", help="Sort descending (default).")
    order.add_argument("--asc", action="store_true", help="Sort ascending.")
    pl.set_defaults(func="list")

    # stats
    ps = sub.add_parser("stats", help="Show statistics for a period or date range.")
    ps.add_argument("--period", default="month", help="day|week|month|year|all (default month)")
    ps.add_argument("--from", dest="from_date", help="YYYY-MM-DD (overrides --period)")
    ps.add_argument("--to", dest="to_date", help="YYYY-MM-DD (overrides --period)")
    ps.add_argument("--stake", help="Filter by stake (exact match)")
    ps.add_argument("--game", help="Filter by game (NLH/PLO)")
    ps.add_argument("--by", help="Group by: stake or game")
    ps.set_defaults(func="stats")

    # edit
    pe = sub.add_parser("edit", help="Edit a session by id (updates only provided fields).")
    pe.add_argument("--id", type=int, required=True, help="Session id")
    pe.add_argument("--date", help="YYYY-MM-DD")
    pe.add_argument("--start", help="HH:MM")
    pe.add_argument("--end", help="HH:MM")
    pe.add_argument("--profit", help="Profit number")
    pe.add_argument("--stake", help="Stake")
    pe.add_argument("--game", help="Game")
    pe.add_argument("--hands", help="Hands (>=0)")
    pe.add_argument("--tables", help="Tables (>=0)")
    pe.add_argument("--notes", help="Notes (set empty string to clear)")
    pe.set_defaults(func="edit")

    # delete
    pd = sub.add_parser("delete", help="Delete a session by id.")
    pd.add_argument("--id", type=int, required=True, help="Session id")
    pd.set_defaults(func="delete")

    # export
    px = sub.add_parser("export", help="Export sessions to CSV.")
    px.add_argument("--format", default="csv", help="Only csv is supported")
    px.add_argument("--out", default="sessions_export.csv", help="Output filename (default sessions_export.csv)")
    px.set_defaults(func="export")

    # config
    pc = sub.add_parser("config", help="Show or update config.")
    pc.add_argument("--set", help="Set config key=value (e.g., currency=EUR)")
    pc.set_defaults(func="config")

    return p


# ---------------------------
# Main
# ---------------------------

def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    base = script_dir()
    cfg_path = base / "config.json"

    try:
        cfg = load_or_init_config(cfg_path)
        data_path = base / str(cfg.get("data_file", "sessions.json"))
        sessions = load_or_init_sessions(data_path)

        if args.command == "add":
            cmd_add(args, cfg, sessions, data_path)
        elif args.command == "list":
            cmd_list(args, sessions)
        elif args.command == "stats":
            cmd_stats(args, cfg, sessions)
        elif args.command == "edit":
            cmd_edit(args, cfg, sessions, data_path)
        elif args.command == "delete":
            cmd_delete(args, sessions, data_path)
        elif args.command == "export":
            cmd_export(args, sessions)
        elif args.command == "config":
            cmd_config(args, cfg, cfg_path)
        else:
            parser.print_help()

    except TrackerError as e:
        die(str(e), 1)
    except KeyboardInterrupt:
        die("cancelled by user", 1)


if __name__ == "__main__":
    main()