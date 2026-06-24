import argparse
import contextlib
import json
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


GAME_WIDTH = 960
GAME_HEIGHT = 540
DEFAULT_GAME = "1569947"
DEFAULT_VERSION = "364"
DEFAULT_OUT = Path("C:/tmp/claw_verify")
MD5_RE = re.compile(r"/shareres/[0-9a-fA-F]{2}/([0-9a-fA-F]{32})")

BUTTON_SLUGS = {
    0: "order",
    1: "overview",
    2: "backyard",
    3: "manage",
    4: "banquet",
    5: "upgrade",
    6: "sell",
    7: "outing",
    8: "affection",
    9: "staff",
    10: "appearance",
    11: "sidequest",
}
EXPECTED_UNCHANGED_BUTTONS = {8}
BUTTON_FALLBACKS = {
    0: {"idx": 0, "index": 297, "name": "order", "x": 800, "y": 100},
    1: {"idx": 1, "index": 298, "name": "overview", "x": 30, "y": 210},
    2: {"idx": 2, "index": 299, "name": "backyard", "x": 30, "y": 100},
    3: {"idx": 3, "index": 300, "name": "manage", "x": 800, "y": 320},
    4: {"idx": 4, "index": 301, "name": "banquet", "x": 30, "y": 430},
    5: {"idx": 5, "index": 303, "name": "upgrade", "x": 800, "y": 210},
    6: {"idx": 6, "index": 304, "name": "sell", "x": 680, "y": 380},
    7: {"idx": 7, "index": 305, "name": "outing", "x": 30, "y": 320},
    8: {"idx": 8, "index": 308, "name": "affection", "x": 680, "y": 150},
    9: {"idx": 9, "index": 307, "name": "staff", "x": 680, "y": 265},
    10: {"idx": 10, "index": 306, "name": "appearance", "x": 800, "y": 430},
    11: {"idx": 11, "index": 450, "name": "sidequest", "x": 140, "y": 150},
}


class RecordingHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler_class):
        super().__init__(server_address, handler_class)
        self.not_found = []
        self.request_log = []


class RecordingHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        self.server.request_log.append(
            {
                "time": time.time(),
                "client": self.client_address[0],
                "message": fmt % args,
            }
        )

    def send_error(self, code, message=None, explain=None):
        if code == 404:
            self.server.not_found.append(
                {
                    "time": time.time(),
                    "method": self.command,
                    "path": unquote(urlparse(self.path).path),
                    "raw_path": self.path,
                }
            )
        return super().send_error(code, message, explain)


def parse_button_selector(value):
    if not value:
        return list(range(12))
    selected = []
    for item in re.split(r"[\s,]+", value.strip()):
        if not item:
            continue
        selected.append(int(item))
    return selected


def start_server(root, requested_port):
    handler = partial(RecordingHandler, directory=str(root))
    last_error = None
    for port in range(requested_port, requested_port + 50):
        try:
            httpd = RecordingHTTPServer(("127.0.0.1", port), handler)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            return httpd, port
        except OSError as error:
            last_error = error
    raise RuntimeError(f"could not bind local HTTP server near port {requested_port}: {last_error}")


def build_runner_url(base_url, runner, run_id, route_mode, button_index, extra_params=None):
    params = {
        "localRes": "1",
        "patchNewDSystem": "1",
        "traceRuntime": "1",
        "traceTitle": "1",
        "traceBranchChoice": "1",
        "traceNullPath": "1",
        "quietOafEvents": "1",
        "patchTitleClick": "1",
        "hideDebug": "1",
        "traceStoryState": "1",
        "storyTraceLimit": "0",
        "autoStartTitle": "1",
        "stubInitialVitals": "1",
        "stubPropShop": "1",
        "runId": run_id,
    }
    if route_mode == "full":
        params.update(
            {
                "patchFirstSceneLobbyButtons": "1",
                "clearStorage": "1",
                "traceAutoNameChoice": "1",
                "stubCode214Name": "1",
                "stubCode214Birthday": "1",
                "autoFirstSceneChoice": "0",
                "autoCreateCharacterConfirm": "1",
                "autoNameChoice": "1",
                "autoInnNameChoice": "1",
                "autoCode1010Choice": "last",
                "autoDailyRandomText": "1",
                "autoCode100Text": "1",
                "autoCode100StoryId": "1,44,118",
            }
        )
    elif route_mode == "debug-jump":
        params["debugJumpMain"] = "1"
    else:
        raise ValueError(f"unsupported route mode: {route_mode}")
    if extra_params:
        params.update(extra_params)
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return f"{base_url}/{runner}?{query}"


def load_playwright():
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise SystemExit(
            "Python Playwright is required.\n"
            "Install it with:\n"
            "  python -m pip install playwright\n"
            "  python -m playwright install chromium"
        ) from error
    return sync_playwright, PlaywrightError


def read_state(page):
    text = page.evaluate(
        """
        () => {
          const el = document.getElementById('runner-story-state');
          return el ? el.textContent : '';
        }
        """
    )
    return json.loads(text) if text else None


def wait_for_state(page, predicate, timeout_ms, interval_ms=150):
    deadline = time.time() + timeout_ms / 1000
    last_state = None
    while time.time() < deadline:
        with contextlib.suppress(Exception):
            last_state = read_state(page)
            if predicate(last_state):
                return last_state
        page.wait_for_timeout(interval_ms)
    return last_state


def is_main_state(state):
    return bool(state and state.get("storyId") == 15 and state.get("pos") == 648 and state.get("code") == 204)


def is_pre_main_state(state):
    if not state:
        return True
    story_id = state.get("storyId")
    return story_id in (None, 1, 44, 118)


def stage_to_viewport(page, x, y):
    rect = page.evaluate(
        """
        () => {
          const canvas = document.querySelector('canvas');
          if (!canvas) return null;
          const r = canvas.getBoundingClientRect();
          return { left: r.left, top: r.top, width: r.width, height: r.height };
        }
        """
    )
    if not rect:
        raise RuntimeError("runner canvas not found")
    return (
        rect["left"] + x * rect["width"] / GAME_WIDTH,
        rect["top"] + y * rect["height"] / GAME_HEIGHT,
    )


def click_stage(page, x, y):
    view_x, view_y = stage_to_viewport(page, x, y)
    page.mouse.click(view_x, view_y)


def choice_y_for_index(count, idx):
    if count == 2:
        return [235, 315][idx] if idx < 2 else 315
    if count == 3:
        return [205, 270, 335][idx] if idx < 3 else 335
    return 205 + idx * 65


def drive_pre_main_state(page, state):
    if not state:
        page.wait_for_timeout(150)
        return
    code = state.get("code")
    show_event = state.get("showEvent") or {}
    buttons = show_event.get("buttons") or []
    if code == 204 and buttons:
        button = buttons[0]
        if button.get("index") == 10:
            click_stage(page, 34, 41)
        else:
            click_stage(page, float(button.get("x") or 0) + 50, float(button.get("y") or 0) + 40)
    elif code == 101:
        argv = state.get("argv") or []
        choice_index = 1 if len(argv) == 2 else max(len(argv) - 1, 0)
        click_stage(page, 480, choice_y_for_index(len(argv), choice_index))
    else:
        click_stage(page, 480, 500)


def missing_since(httpd, start_index):
    return httpd.not_found[start_index:]


def extract_missing_md5s(items):
    md5s = []
    for item in items:
        match = MD5_RE.search(item["path"])
        if match:
            md5s.append(match.group(1).lower())
    return sorted(set(md5s))


def safe_name(text):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_") or "button"


def summarize_state(state):
    if not state:
        return None
    show_event = state.get("showEvent") or {}
    return {
        "storyId": state.get("storyId"),
        "storyName": state.get("storyName"),
        "pos": state.get("pos"),
        "code": state.get("code"),
        "argv": state.get("argv"),
        "currentLinks": state.get("currentLinks"),
        "buttonsLength": show_event.get("buttonsLength"),
        "buttons": show_event.get("buttons"),
    }


def drive_to_main(page, idx, timeout_ms):
    deadline = time.time() + timeout_ms / 1000
    last_state = None
    while time.time() < deadline:
        with contextlib.suppress(Exception):
            last_state = read_state(page)
            show_event = (last_state or {}).get("showEvent") or {}
            if is_main_state(last_state) and len(show_event.get("buttons") or []) > idx:
                return last_state
            if is_pre_main_state(last_state):
                drive_pre_main_state(page, last_state)
        page.wait_for_timeout(150)
    return None


def validate_button_debug_jump(page, httpd, base_url, args, idx, run_id):
    url = build_runner_url(base_url, args.runner, run_id, "debug-jump", idx)
    page.goto(url, wait_until="domcontentloaded", timeout=args.page_timeout_ms)
    main_state = wait_for_state(
        page,
        lambda state: is_main_state(state)
        and (state.get("showEvent") or {}).get("buttons")
        and len((state.get("showEvent") or {}).get("buttons") or []) >= idx + 1,
        args.main_timeout_ms,
    )
    if not main_state:
        raise RuntimeError(f"main screen did not become ready for button index {idx}")

    buttons = (main_state.get("showEvent") or {}).get("buttons") or []
    button = buttons[idx]
    click_x = float(button.get("x") or 0) + args.button_center_x
    click_y = float(button.get("y") or 0) + args.button_center_y
    click_stage(page, click_x, click_y)
    result_state = wait_for_state(page, lambda state: state and not is_main_state(state), args.result_timeout_ms)
    return main_state, button, {"x": click_x, "y": click_y}, result_state


def validate_button_full_route(page, base_url, args, idx, run_id):
    url = build_runner_url(base_url, args.runner, run_id, "full", idx)
    page.goto(url, wait_until="domcontentloaded", timeout=args.page_timeout_ms)
    main_state = drive_to_main(page, idx, args.main_timeout_ms)
    if not main_state:
        current_state = summarize_state(read_state(page))
        raise RuntimeError(f"full route did not reach the main screen for button index {idx}; last_state={current_state}")
    buttons = ((main_state or {}).get("showEvent") or {}).get("buttons") or []
    button = buttons[idx] if len(buttons) > idx else BUTTON_FALLBACKS[idx]
    click_x = float(button.get("x") or 0) + args.button_center_x
    click_y = float(button.get("y") or 0) + args.button_center_y
    click_stage(page, click_x, click_y)
    if idx in EXPECTED_UNCHANGED_BUTTONS:
        page.wait_for_timeout(1500)
        result_state = read_state(page)
    else:
        result_state = wait_for_state(page, lambda state: state and not is_main_state(state), args.result_timeout_ms)
    return main_state, button, {"x": click_x, "y": click_y}, result_state


def validate_button(page, httpd, base_url, args, idx):
    run_id = f"validate_main_button_{idx:02d}_{int(time.time() * 1000)}"
    start_404 = len(httpd.not_found)

    if args.route_mode == "debug-jump":
        main_state, button, click_point, result_state = validate_button_debug_jump(page, httpd, base_url, args, idx, run_id)
    else:
        main_state, button, click_point, result_state = validate_button_full_route(page, base_url, args, idx, run_id)

    page.wait_for_timeout(args.settle_ms)
    stable_state = read_state(page)
    changed_state = bool(result_state and not is_main_state(result_state))
    if changed_state:
        status = "ok"
    elif idx in EXPECTED_UNCHANGED_BUTTONS:
        status = "expected_unchanged"
    else:
        status = "unchanged"

    slug = BUTTON_SLUGS.get(idx, safe_name(button.get("name") or f"button_{idx}"))
    report_name = f"main_button_{idx:02d}_{slug}"
    screenshot_path = args.out / f"{report_name}.png"
    report_path = args.out / f"{report_name}.json"
    local_404 = missing_since(httpd, start_404)
    missing_md5s = extract_missing_md5s(local_404)
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "runId": run_id,
        "routeMode": args.route_mode,
        "buttonIndex": idx,
        "button": button,
        "clickPoint": click_point,
        "mainState": main_state,
        "resultState": result_state,
        "stableState": stable_state,
        "status": status,
        "local404": local_404,
        "missingMd5s": missing_md5s,
        "screenshot": str(screenshot_path),
    }
    page.screenshot(path=str(screenshot_path), full_page=False)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "buttonIndex": idx,
        "buttonName": button.get("name"),
        "buttonId": button.get("index"),
        "slug": slug,
        "report": str(report_path),
        "screenshot": str(screenshot_path),
        "status": status,
        "result": summarize_state(stable_state),
        "local404Count": len(local_404),
        "missingMd5s": missing_md5s,
    }


def mirror_missing(root, game, version, md5s):
    if not md5s:
        return None
    command = [
        sys.executable,
        str(root / "66rpgProjectDropper" / "prepare_runner_mirror.py"),
        game,
        "--version",
        str(version),
        "--root",
        str(root),
    ]
    for md5 in md5s:
        command.extend(["--mirror-md5", md5])
    completed = subprocess.run(command, cwd=str(root), text=True, capture_output=True)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate the h5 runner main-screen buttons and report local missing resources."
    )
    parser.add_argument("--root", default=".", help="runner repository root")
    parser.add_argument("--runner", default="h5_runner_experiment.html", help="runner HTML file")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="report output directory")
    parser.add_argument("--port", type=int, default=8765, help="preferred local HTTP port")
    parser.add_argument("--buttons", default="", help="comma or space separated button indices; default: 0..11")
    parser.add_argument("--headed", action="store_true", help="show the browser window")
    parser.add_argument(
        "--route-mode",
        choices=("full", "debug-jump"),
        default="full",
        help="full uses the real opening route and clicks the requested button; debug-jump is faster but less representative",
    )
    parser.add_argument("--page-timeout-ms", type=int, default=15000)
    parser.add_argument("--main-timeout-ms", type=int, default=180000)
    parser.add_argument("--result-timeout-ms", type=int, default=7000)
    parser.add_argument("--settle-ms", type=int, default=1400)
    parser.add_argument("--button-center-x", type=float, default=50)
    parser.add_argument("--button-center-y", type=float, default=40)
    parser.add_argument("--game", default=DEFAULT_GAME, help="game URL, gindex, or guid for --mirror-missing")
    parser.add_argument("--version", default=DEFAULT_VERSION, help="game version for --mirror-missing")
    parser.add_argument("--mirror-missing", action="store_true", help="mirror all missing MD5s after validation")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    args.out = Path(args.out)
    if not (root / args.runner).exists():
        raise SystemExit(f"runner not found: {root / args.runner}")
    args.out.mkdir(parents=True, exist_ok=True)
    selected_buttons = parse_button_selector(args.buttons)

    sync_playwright, PlaywrightError = load_playwright()
    httpd, port = start_server(root, args.port)
    base_url = f"http://127.0.0.1:{port}"
    summaries = []
    errors = []

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=not args.headed)
            except PlaywrightError as error:
                raise SystemExit(
                    "Could not launch Playwright Chromium.\n"
                    "Install browser assets with:\n"
                    "  python -m playwright install chromium"
                ) from error
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            for idx in selected_buttons:
                try:
                    summaries.append(validate_button(page, httpd, base_url, args, idx))
                    if summaries[-1]["status"] == "unchanged":
                        errors.append(
                            {
                                "buttonIndex": idx,
                                "error": "button click did not leave the main screen",
                                "report": summaries[-1]["report"],
                            }
                        )
                    print(
                        f"[ok] button {idx:02d} {summaries[-1]['buttonName']} "
                        f"status={summaries[-1]['status']} 404={summaries[-1]['local404Count']}"
                    )
                except Exception as error:
                    errors.append({"buttonIndex": idx, "error": str(error)})
                    print(f"[error] button {idx:02d}: {error}", file=sys.stderr)
            browser.close()
    finally:
        httpd.shutdown()
        httpd.server_close()

    missing_md5s = sorted({md5 for summary in summaries for md5 in summary["missingMd5s"]})
    mirror_report = mirror_missing(root, args.game, args.version, missing_md5s) if args.mirror_missing else None
    summary = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "runner": args.runner,
        "routeMode": args.route_mode,
        "server": base_url,
        "selectedButtons": selected_buttons,
        "buttons": summaries,
        "errors": errors,
        "missingMd5s": missing_md5s,
        "allLocalResourcesPresent": not missing_md5s and not errors,
        "mirrorReport": mirror_report,
    }
    summary_path = args.out / "main_buttons_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"summary: {summary_path}")
    if missing_md5s:
        print("missing md5s:")
        for md5 in missing_md5s:
            print(f"  {md5}")
    if errors:
        raise SystemExit(1)
    if missing_md5s:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
