"""Upload command: push MangoHud CSV logs to FlightlessSomething via API."""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import sys
import time
from typing import Any, Dict, List, Optional

from .constants import (
    BENCH_LOG_DIR,
    FLIGHTLESS_BASE,
    FLIGHTLESS_TOKEN_FILE,
    FLIGHTLESS_URL,
    PROG_NAME,
    UPLOAD_HISTORY_FILE,
    VERSION,
)
from .utils import _extract_game_name, _normalize_csv_for_flightless, find_logs, log


# ── Helper: filter out summary/current symlink files ──────────────────


def _is_real_csv(p: pathlib.Path) -> bool:
    return (
        not p.name.endswith("-current-mangohud.csv")
        and not p.name.endswith("_summary.csv")
        and p.name != "current.csv"
    )


# ── Upload history ─────────────────────────────────────────────────────


def _load_upload_history() -> Dict[str, List[str]]:
    if not UPLOAD_HISTORY_FILE.exists():
        return {}
    try:
        return json.loads(UPLOAD_HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_upload_history(history: Dict[str, List[str]]) -> None:
    UPLOAD_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")


def _mark_uploaded(benchmark_id: str, filenames: List[str]) -> None:
    history = _load_upload_history()
    existing = set(history.get(benchmark_id, []))
    existing.update(filenames)
    history[benchmark_id] = sorted(existing)
    _save_upload_history(history)


# ── Token management ───────────────────────────────────────────────────


def _load_token_file() -> Optional[str]:
    """Read API token from ~/.flightless-token, enforcing mode 600."""
    p = FLIGHTLESS_TOKEN_FILE
    if not p.exists():
        return None
    mode = p.stat().st_mode & 0o777
    if mode != 0o600:
        log.error(
            "%s has permissions %04o -- must be 600.\n"
            "  Fix with: chmod 600 %s",
            p, mode, p,
        )
        sys.exit(1)
    token = p.read_text(encoding="utf-8").strip()
    if not token:
        log.error("%s is empty.", p)
        sys.exit(1)
    return token


def _prompt_and_save_token() -> str:
    """Interactively prompt for a FlightlessSomething API token."""
    import termios
    import tty

    if not sys.stdin.isatty():
        log.error(
            "No API token found and stdin is not a terminal.\n"
            "  Set FLIGHTLESS_TOKEN env var or create %s (mode 600).",
            FLIGHTLESS_TOKEN_FILE,
        )
        sys.exit(1)

    print()
    print("  No FlightlessSomething API token found.")
    print(f"  Get one at: {FLIGHTLESS_BASE}/api-tokens")
    print()
    print(f"  Token will be saved to {FLIGHTLESS_TOKEN_FILE} (mode 600).")
    print("  Paste your API token then press Enter:")
    print("  > ", end="", flush=True)

    token_chars: List[str] = []
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.cbreak(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch in ("\n", "\r"):
                break
            elif ch in ("\x7f", "\x08"):
                if token_chars:
                    token_chars.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
            elif ch == "\x03":
                raise KeyboardInterrupt
            elif ch == "\x04":
                break
            else:
                token_chars.append(ch)
                sys.stdout.write("*")
                sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

    print()
    token = "".join(token_chars).strip()
    if not token:
        log.error("No token entered.")
        sys.exit(1)

    FLIGHTLESS_TOKEN_FILE.write_text(token + "\n", encoding="utf-8")
    FLIGHTLESS_TOKEN_FILE.chmod(0o600)
    print(f"  Token saved to {FLIGHTLESS_TOKEN_FILE}")
    print()
    return token


# ── API helpers ────────────────────────────────────────────────────────


def _fetch_current_user_id(token: str, base_url: str) -> Optional[int]:
    import urllib.request

    print(f"  Authenticating with {base_url} ...", end="", flush=True)
    req = urllib.request.Request(
        f"{base_url}/api/tokens",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        data = json.loads(urllib.request.urlopen(req).read().decode("utf-8", errors="replace"))
        if isinstance(data, list) and data:
            uid = data[0].get("UserID") or data[0].get("user_id")
            print(f" OK (user ID {uid})")
            return uid
        print(" OK (no tokens returned)")
        return None
    except Exception as exc:
        print(" FAILED")
        log.warning("Could not fetch current user ID: %s", exc)
        return None


def _fetch_benchmarks(
    token: str, base_url: str, per_page: int = 50
) -> List[Dict[str, Any]]:
    """Return all benchmarks belonging to the authenticated user."""
    import urllib.request

    user_id = _fetch_current_user_id(token, base_url)
    all_benchmarks: List[Dict[str, Any]] = []
    page = 1
    user_filter = f"&user_id={user_id}" if user_id else ""
    while True:
        url = f"{base_url}/api/benchmarks?per_page={per_page}&page={page}{user_filter}"
        print(f"  Fetching benchmarks (page {page}) ...", end="", flush=True)
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {token}"}
        )
        try:
            data = json.loads(urllib.request.urlopen(req).read().decode("utf-8", errors="replace"))
        except Exception as exc:
            print(" FAILED")
            log.error("Failed to fetch benchmark list: %s", exc)
            break

        benchmarks = data.get("benchmarks") or []
        if not benchmarks:
            print(" done")
            break

        matched = [
            b for b in benchmarks
            if user_id is None or (b.get("UserID") or b.get("user_id")) == user_id
        ]
        all_benchmarks.extend(matched)
        total_pages = data.get("total_pages", 1)
        print(f" {len(matched)} matched (total so far: {len(all_benchmarks)})")

        if page >= total_pages:
            break
        if not user_filter and len(matched) == 0 and page >= 2:
            log.debug("No matches on consecutive pages, stopping early.")
            break
        page += 1

    return all_benchmarks


def _fetch_benchmark_run_names(token: str, base_url: str, benchmark_id: str) -> Optional[set]:
    """Return set of filenames already in the benchmark from the API, or None on error."""
    import urllib.request

    url = f"{base_url}/api/benchmarks/{benchmark_id}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        data = json.loads(urllib.request.urlopen(req).read().decode("utf-8", errors="replace"))
        labels = data.get("run_labels") or []
        return set(labels)
    except Exception as exc:
        log.debug("Could not fetch benchmark runs from API: %s", exc)
        return None


# ── File pickers ───────────────────────────────────────────────────────

_TUI_UNAVAILABLE = object()  # sentinel: TUI could not run, fall back to text picker


def _tui_file_picker(
    root: pathlib.Path,
    already_uploaded: Optional[set] = None,
    force: bool = False,
):
    """Curses-based file picker with checkbox selection and folder navigation.

    Returns:
      List[pathlib.Path]  -- files selected by the user
      None                -- user explicitly quit (q / ESC) → abort upload
      _TUI_UNAVAILABLE    -- non-TTY or curses error → fall back to text picker
    """
    import curses as _curses

    already = already_uploaded or set()
    selected: set = set()
    result: Optional[List[pathlib.Path]] = [None]

    def _dir_files(d: pathlib.Path) -> List[pathlib.Path]:
        try:
            return sorted(
                [f for f in d.iterdir() if f.is_file() and _is_real_csv(f)],
                key=lambda p: p.name,
            )
        except OSError:
            return []

    def _dir_subdirs(d: pathlib.Path) -> List[pathlib.Path]:
        try:
            return sorted(
                [p for p in d.iterdir() if p.is_dir()
                 and any(_is_real_csv(f) for f in p.iterdir() if f.is_file())],
                key=lambda p: p.name,
            )
        except OSError:
            return []

    def _build_items(d: pathlib.Path) -> list:
        return _dir_subdirs(d) + _dir_files(d)

    def _run(stdscr) -> None:
        _curses.curs_set(0)
        try:
            _curses.use_default_colors()
            _curses.init_pair(1, _curses.COLOR_CYAN, -1)
            _curses.init_pair(2, _curses.COLOR_GREEN, -1)
            _curses.init_pair(3, _curses.COLOR_YELLOW, -1)
            _curses.init_pair(4, -1, _curses.COLOR_BLUE)
        except Exception:
            pass

        nav_stack: list = []
        cur_dir = root
        items = _build_items(root)
        cursor = 0
        scroll = 0

        while True:
            h, w = stdscr.getmaxyx()
            stdscr.erase()

            display: list = ([None] if nav_stack else []) + items
            cursor = max(0, min(cursor, len(display) - 1))

            list_h = max(1, h - 5)
            if cursor >= scroll + list_h:
                scroll = cursor - list_h + 1
            if cursor < scroll:
                scroll = cursor

            rel = str(cur_dir).replace(str(pathlib.Path.home()), "~")
            n_sel = len(selected)
            right = f" [{n_sel} selected] "
            left = f" {rel}/ "
            pad = max(0, w - 1 - len(left) - len(right))
            try:
                stdscr.addstr(0, 0, (left + " " * pad + right)[:w - 1], _curses.A_BOLD)
                stdscr.addstr(1, 0, "─" * (w - 1))
            except _curses.error:
                pass

            for row in range(list_h):
                idx = scroll + row
                if idx >= len(display):
                    break
                y = row + 2
                item = display[idx]
                is_cur = idx == cursor

                if item is None:
                    line = "  [↑] .."
                    attr = _curses.color_pair(1)
                elif item.is_dir():
                    files = _dir_files(item)
                    n = len(files)
                    n_s = sum(1 for f in files if f in selected)
                    box = "[*]" if (n_s == n and n > 0) else ("[-]" if n_s > 0 else "[ ]")
                    line = f"  {box} {item.name}/  ({n} file{'s' if n != 1 else ''})"
                    attr = _curses.color_pair(1)
                else:
                    is_sel = item in selected
                    is_old = item.stem in already
                    box = "[*]" if is_sel else "[ ]"
                    kb = item.stat().st_size / 1024
                    tag = "  ↑" if is_old else ""
                    line = f"  {box} {item.name}  ({kb:.1f} KB){tag}"
                    attr = (
                        _curses.color_pair(2) if is_sel
                        else _curses.color_pair(3) if is_old
                        else 0
                    )

                try:
                    if is_cur:
                        padded = (line + " " * w)[:w - 1]
                        stdscr.addstr(y, 0, padded, _curses.color_pair(4) | _curses.A_BOLD)
                    else:
                        stdscr.addstr(y, 0, line[:w - 1], attr)
                except _curses.error:
                    pass

            if selected and already is None:
                game_names = sorted({
                    _extract_game_name(c.parent.name) if c.parent != root
                    else _extract_game_name(c.stem)
                    for c in selected
                })
                preview = " Benchmark title: " + (", ".join(game_names) or "(unknown)") + " "
            elif selected and already is not None:
                preview = f" Appending {len(selected)} run(s) to existing benchmark "
            else:
                preview = " (no files selected) "
            try:
                stdscr.addstr(h - 2, 0, preview[:w - 1], _curses.A_BOLD)
            except _curses.error:
                pass

            footer = " ↑↓:move  SPC:toggle  ENTER:open folder  ←/BKSP:back  u:upload  q:quit "
            try:
                stdscr.addstr(h - 1, 0, footer[:w - 1], _curses.A_DIM)
            except _curses.error:
                pass

            stdscr.refresh()
            key = stdscr.getch()

            if key == _curses.KEY_UP:
                cursor = max(0, cursor - 1)
            elif key == _curses.KEY_DOWN:
                cursor = min(len(display) - 1, cursor + 1)
            elif key in (_curses.KEY_BACKSPACE, 127, _curses.KEY_LEFT):
                if nav_stack:
                    cur_dir, items, cursor, scroll = nav_stack.pop()
            elif key in (27, ord('q')):
                result[0] = None
                return
            elif key == ord('u'):
                sel = list(selected)
                if already and not force:
                    sel = [p for p in sel if p.stem not in already]
                result[0] = sel
                return
            elif key in (10, 13, ord(' ')):
                if not display:
                    continue
                item = display[cursor]
                if item is None:
                    if nav_stack:
                        cur_dir, items, cursor, scroll = nav_stack.pop()
                elif item.is_dir():
                    if key in (10, 13):
                        nav_stack.append((cur_dir, items, cursor, scroll))
                        cur_dir = item
                        items = _build_items(item)
                        cursor = 0
                        scroll = 0
                    else:
                        files = _dir_files(item)
                        if files and all(f in selected for f in files):
                            for f in files:
                                selected.discard(f)
                        else:
                            for f in files:
                                selected.add(f)
                else:
                    if item in selected:
                        selected.discard(item)
                    else:
                        selected.add(item)

    if not sys.stdout.isatty():
        return _TUI_UNAVAILABLE
    try:
        _curses.wrapper(_run)
    except Exception as exc:
        log.debug("TUI picker error: %s", exc)
        return _TUI_UNAVAILABLE
    return result[0]


def _collect_csvs_for_upload(args: argparse.Namespace) -> List[pathlib.Path]:
    """Collect CSV files based on --game, --input, or organized folders."""
    game = getattr(args, "game", None)
    src_dir = pathlib.Path(args.source) if args.source else BENCH_LOG_DIR
    inputs = getattr(args, "input", None)

    csvs: List[pathlib.Path] = []

    if inputs:
        for p in inputs:
            pp = pathlib.Path(p)
            if pp.is_file() and pp.suffix == ".csv":
                csvs.append(pp)
            elif pp.is_dir():
                csvs.extend(sorted(pp.glob("*.csv")))
        return csvs

    if game:
        game_dir = src_dir / game
        if game_dir.is_dir():
            csvs = sorted(
                [f for f in game_dir.glob("*.csv") if _is_real_csv(f)],
                key=lambda p: p.stat().st_mtime,
            )
        else:
            csvs = [f for f in find_logs(src_dir, game=game) if _is_real_csv(f)]
    else:
        if src_dir.is_dir():
            for gd in sorted(src_dir.iterdir()):
                if not gd.is_dir():
                    continue
                gn = gd.name
                cur = gd / f"{gn}-current-mangohud.csv"
                if not cur.exists():
                    cur = gd / "current.csv"
                if cur.is_symlink() or cur.exists():
                    resolved = cur.resolve()
                    if resolved.exists() and _is_real_csv(resolved):
                        csvs.append(resolved)
                else:
                    real = sorted(
                        [f for f in gd.glob("*.csv") if _is_real_csv(f)],
                        key=lambda p: p.stat().st_mtime,
                    )
                    if real:
                        csvs.append(real[-1])
    return csvs


def _pick_csvs(
    csvs: List[pathlib.Path],
    already: Optional[set] = None,
    force: bool = False,
) -> List[pathlib.Path]:
    """Interactive text-based CSV picker."""

    def _is_already(p: pathlib.Path) -> bool:
        return already is not None and p.stem in already

    print()
    print("  Available CSVs (* = already uploaded):")
    print()
    for i, p in enumerate(csvs, 1):
        marker = "* " if _is_already(p) else "  "
        print(f"    {i:>3}.  {marker}{p.name}  ({p.stat().st_size/1024:.1f} KB)")
    print()

    if already is not None:
        unuploaded = [p for p in csvs if not _is_already(p)]
        default_label = f"all {len(unuploaded)} not yet uploaded" if unuploaded else "none (all already uploaded)"
    else:
        unuploaded = csvs
        default_label = f"all {len(csvs)}"

    print(f"  Select CSVs to upload (e.g. 1,3 or 1-3), or ENTER for {default_label}:")

    while True:
        try:
            raw = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return []
        if not raw:
            return unuploaded

        selected: List[pathlib.Path] = []
        valid = True
        for part in raw.replace(" ", "").split(","):
            if "-" in part:
                lo_s, _, hi_s = part.partition("-")
                if lo_s.isdigit() and hi_s.isdigit():
                    lo, hi = int(lo_s) - 1, int(hi_s) - 1
                    if 0 <= lo <= hi < len(csvs):
                        selected.extend(csvs[lo:hi + 1])
                        continue
                valid = False
                break
            elif part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(csvs):
                    selected.append(csvs[idx])
                    continue
                valid = False
                break
            else:
                valid = False
                break

        if valid and selected:
            dupes = [p for p in selected if _is_already(p)]
            if dupes and not force:
                print(f"  Already uploaded: {', '.join(p.name for p in dupes)}")
                print("  Use --force to re-upload existing runs.")
                continue
            return selected
        print(f"  Enter numbers between 1 and {len(csvs)}, e.g. 1,2 or 1-3.")


def _select_benchmark(
    benchmarks: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Display a numbered benchmark list and prompt the user to pick one."""
    if not benchmarks:
        print("  No benchmarks found in your account.")
        return None

    print()
    print("  Your benchmarks:")
    print()
    for i, b in enumerate(benchmarks, 1):
        runs = b.get("run_count", "?")
        ts = (b.get("CreatedAt") or b.get("created_at") or "")[:10]
        title = b.get("Title") or b.get("title") or "(untitled)"
        bid = b.get("ID") or b.get("id")
        print(f"    {i:>3}.  {title}  [{runs} run(s), {ts}]  (id:{bid})")
    print()

    while True:
        try:
            raw = input(f"  Select benchmark to append to [1-{len(benchmarks)}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if not raw:
            return None
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(benchmarks):
                return benchmarks[idx]
        print(f"  Enter a number between 1 and {len(benchmarks)}.")


# ── Subcommand handler ─────────────────────────────────────────────────


def cmd_upload(args: argparse.Namespace) -> int:
    """Upload MangoHud CSV logs to FlightlessSomething via their API."""
    import urllib.error
    import urllib.request

    token = args.token or os.environ.get("FLIGHTLESS_TOKEN", "")
    if token:
        print("  Token: from argument/environment")
    else:
        token = _load_token_file()
        if token:
            print(f"  Token: loaded from {FLIGHTLESS_TOKEN_FILE}")
        else:
            token = _prompt_and_save_token()
    if not token:
        log.error("No API token available.")
        return 1

    base_url = args.url or FLIGHTLESS_BASE
    append_mode = getattr(args, "append", False)

    benchmarks = _fetch_benchmarks(token, base_url)
    append_benchmark: Optional[Dict[str, Any]] = None
    if append_mode:
        append_benchmark = _select_benchmark(benchmarks)
        if not append_benchmark:
            print("  No benchmark selected. Cancelled.")
            return 0
        bid = append_benchmark.get("ID") or append_benchmark.get("id")
        endpoint = f"{base_url}/api/benchmarks/{bid}/runs"
    else:
        endpoint = f"{base_url}/api/benchmarks"

    force = getattr(args, "force", False)
    src_dir = pathlib.Path(args.source) if args.source else BENCH_LOG_DIR
    inputs = getattr(args, "input", None)

    already_set: Optional[set] = None
    if append_mode and append_benchmark:
        bid_str = str(append_benchmark.get("ID") or append_benchmark.get("id"))
        print(f"  Checking existing runs in benchmark {bid_str} ...", end="", flush=True)
        api_names = _fetch_benchmark_run_names(token, base_url, bid_str)
        if api_names is not None:
            print(f" {len(api_names)} run(s) found")
            already_set = {pathlib.Path(n).stem for n in api_names}
            _mark_uploaded(bid_str, list(api_names))
        else:
            print(" (API unavailable, using local history)")
            history = _load_upload_history()
            already_set = {pathlib.Path(n).stem for n in history.get(bid_str, [])}

    if inputs:
        csvs = _collect_csvs_for_upload(args)
        if not csvs:
            print("  No CSV files found to upload.")
            return 1
        csvs = _pick_csvs(csvs, already=already_set, force=force) or []
    else:
        tui_result = _tui_file_picker(src_dir, already_uploaded=already_set, force=force)
        if tui_result is None:
            print("  Cancelled.")
            return 0
        elif tui_result is _TUI_UNAVAILABLE:
            csvs = _collect_csvs_for_upload(args)
            if not csvs:
                print("  No CSV files found to upload.")
                print(f"  Run '{PROG_NAME} organize' first, or specify --input files.")
                return 1
            csvs = _pick_csvs(csvs, already=already_set, force=force) or []
        else:
            csvs = tui_result

    limit = args.limit
    if limit and len(csvs) > limit:
        csvs = csvs[-limit:]

    if not csvs:
        print("  No files selected. Cancelled.")
        return 0

    game = getattr(args, "game", None)

    print()
    if append_benchmark:
        bid = append_benchmark.get("ID") or append_benchmark.get("id")
        btitle = append_benchmark.get("Title") or append_benchmark.get("title") or "(untitled)"
        print(f"  Appending runs to: \"{btitle}\"")
        print(f"    Benchmark ID : {bid}")
        print(f"    URL          : {base_url}/benchmarks/{bid}")
    else:
        if args.title:
            title = args.title
        else:
            game_names = sorted({
                _extract_game_name(c.parent.name) if c.parent != src_dir
                else _extract_game_name(c.stem)
                for c in csvs
            })
            title = ", ".join(game_names) if game_names else (game or "All Games")
        description = args.description or f"Uploaded via {PROG_NAME} v{VERSION} (SteamOS-Tools)"
        existing_titles = {
            (b.get("Title") or b.get("title") or "").strip().lower()
            for b in benchmarks
        }
        if title.strip().lower() in existing_titles:
            if not force:
                log.error(
                    "Benchmark \"%s\" already exists. Use --force to append the date and create new.",
                    title,
                )
                return 1
            log.warning("Benchmark \"%s\" already exists.", title)
            title = f"{title} - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
            print(f"  Benchmark title (date appended): {title}")
        elif not args.yes and not args.title:
            try:
                edit = input(f"\n  Benchmark title: {title}\n  Edit title? [y/N] ").strip().lower()
                if edit in ("y", "yes"):
                    new_title = input("  Title: ").strip()
                    if new_title:
                        title = new_title
            except (EOFError, KeyboardInterrupt):
                print("\n  Cancelled.")
                return 0
        print("  Uploading to FlightlessSomething:")
        print(f"    Title    : {title}")

    print(f"    Files    : {len(csvs)} CSV(s)")
    for c in csvs:
        print(f"      {c.name}  ({c.stat().st_size/1024:.1f} KB)")

    if not args.yes:
        action = "Append runs?" if append_benchmark else "Create new benchmark?"
        try:
            answer = input(f"\n  {action} [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("  Cancelled.")
                return 0
        except (EOFError, KeyboardInterrupt):
            print("\n  Cancelled.")
            return 0

    boundary = f"----MHPBoundary{int(time.time()*1000)}"
    body_parts: List[bytes] = []

    def _add_field(name: str, value: str) -> None:
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        )
        body_parts.append(f"{value}\r\n".encode())

    def _add_file(filepath: pathlib.Path) -> None:
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(
            f'Content-Disposition: form-data; name="files"; filename="{filepath.name}"\r\n'.encode()
        )
        body_parts.append(b"Content-Type: text/csv\r\n\r\n")
        body_parts.append(_normalize_csv_for_flightless(filepath).encode("utf-8"))
        body_parts.append(b"\r\n")

    if not append_benchmark:
        _add_field("title", title)
        _add_field("description", description)
    for csv_file in csvs:
        _add_file(csv_file)
    body_parts.append(f"--{boundary}--\r\n".encode())

    body = b"".join(body_parts)
    content_type = f"multipart/form-data; boundary={boundary}"

    req = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Content-Type": content_type,
            "Authorization": f"Bearer {token}",
        },
    )

    print(f"\n  Uploading {len(csvs)} file(s) ...", end="", flush=True)
    log.info("POST %s (%d bytes, %d files)", endpoint, len(body), len(csvs))

    try:
        response = urllib.request.urlopen(req)
        status = response.status
        resp_body = response.read().decode("utf-8", errors="replace")
        print(f" HTTP {status}")
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            resp_body = e.read().decode("utf-8", errors="replace")
        except OSError:
            resp_body = ""
        print(f" HTTP {status}")
        log.error("Upload failed: HTTP %d", status)
        if resp_body:
            log.error("Response: %s", resp_body[:500])
        return 1
    except urllib.error.URLError as e:
        log.error("Connection failed: %s", e.reason)
        return 1

    if status in (200, 201):
        data = {}
        try:
            data = json.loads(resp_body)
        except json.JSONDecodeError:
            pass

        print("\n  Success!")
        if append_benchmark:
            bid_str = str(append_benchmark.get("ID") or append_benchmark.get("id"))
            _mark_uploaded(bid_str, [c.name for c in csvs])
            runs_added = data.get("runs_added", len(csvs))
            total = data.get("total_run_count", "?")
            print(f"    Runs added   : {runs_added}")
            print(f"    Total runs   : {total}")
            print(f"    Benchmark URL: {base_url}/benchmarks/{bid}")
        else:
            benchmark_id = data.get("id")
            if benchmark_id:
                print(f"    Benchmark URL: {base_url}/benchmarks/{benchmark_id}")
            print(f"    {len(csvs)} CSV(s) uploaded as separate runs.")
        return 0
    else:
        log.warning("Unexpected status: HTTP %d", status)
        if resp_body:
            log.warning("Response: %s", resp_body[:300])
        return 1
