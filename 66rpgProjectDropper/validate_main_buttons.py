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
MD5_RE = re.compile(r"/shareres/[0-9a-fA-F]{2}/([0-9a-fA-F]{32}(?:\.[A-Za-z0-9]+)?)")

BUTTON_SLUGS = {
    0: "kitchen",
    1: "order",
    2: "overview",
    3: "backyard",
    4: "manage",
    5: "room",
    6: "upgrade",
    7: "sell",
    8: "staff",
    9: "appearance",
    10: "outing",
    11: "branch",
}
EXPECTED_UNCHANGED_BUTTONS = set()
BUTTON_FALLBACKS = {
    0: {"idx": 0, "index": 296, "name": "kitchen", "x": 800, "y": 100},
    1: {"idx": 1, "index": 297, "name": "order", "x": 30, "y": 210},
    2: {"idx": 2, "index": 298, "name": "overview", "x": 30, "y": 100},
    3: {"idx": 3, "index": 299, "name": "backyard", "x": 800, "y": 320},
    4: {"idx": 4, "index": 300, "name": "manage", "x": 30, "y": 430},
    5: {"idx": 5, "index": 302, "name": "room", "x": 800, "y": 210},
    6: {"idx": 6, "index": 303, "name": "upgrade", "x": 680, "y": 380},
    7: {"idx": 7, "index": 304, "name": "sell", "x": 30, "y": 320},
    8: {"idx": 8, "index": 307, "name": "staff", "x": 680, "y": 150},
    9: {"idx": 9, "index": 306, "name": "appearance", "x": 680, "y": 265},
    10: {"idx": 10, "index": 305, "name": "outing", "x": 800, "y": 430},
    11: {"idx": 11, "index": 449, "name": "branch", "x": 140, "y": 150},
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
        return list(range(11))
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


def mark_progress(args, label):
    try:
        with (args.out / "main_buttons_progress.log").open("a", encoding="utf-8") as progress:
            progress.write(f"{datetime.now(timezone.utc).isoformat()} {label}\n")
    except Exception:
        pass


def read_state(page, timeout_ms=1000):
    try:
        text = page.locator("#runner-story-state").text_content(timeout=timeout_ms)
    except Exception:
        return None
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


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
    return story_id in (None, 1, 44, 118) or (story_id == 15 and state.get("code") == 101)


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


def finish_show_event(page, choice_index):
    return page.evaluate(
        """
        (choiceIndex) => {
          const gd = window.GloableData && GloableData.getInstance ? GloableData.getInstance() : null;
          const line = gd && gd.currentLine;
          const showEvent = line && line.currentShowEvent;
          if (!showEvent || typeof showEvent.finish !== 'function') return false;
          showEvent.finish(choiceIndex);
          return true;
        }
        """,
        choice_index,
    )


def activate_button(page, args, idx, click_x, click_y):
    if args.activation_mode == "finish" and finish_show_event(page, idx):
        return "showEvent.finish"
    click_stage(page, click_x, click_y)
    return "stage-click"


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
    story_id = state.get("storyId")
    pos = state.get("pos")
    show_event = state.get("showEvent") or {}
    buttons = show_event.get("buttons") or []
    if code == 204 and buttons:
        known_choices = {
            (1, 47): 1,
            (1, 231): 3,
            (1, 1328): 2,
        }
        known_choice = known_choices.get((story_id, pos))
        if known_choice is not None and finish_show_event(page, known_choice):
            return
        button = buttons[0]
        if button.get("index") == 10:
            click_stage(page, 34, 41)
        else:
            click_stage(page, float(button.get("x") or 0) + 50, float(button.get("y") or 0) + 40)
    elif code == 101:
        argv = state.get("argv") or []
        choice_index = 1 if len(argv) == 2 else max(len(argv) - 1, 0)
        if finish_show_event(page, choice_index):
            return
        click_stage(page, 480, choice_y_for_index(len(argv), choice_index))
    elif code == 214:
        argv = state.get("argv") or []
        if story_id == 118 and argv and str(argv[0]) == "479":
            click_stage(page, 480, 315)
            return
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


def attach_page_event_recording(page):
    events = {
        "console": [],
        "pageErrors": [],
        "requestFailures": [],
    }

    def trim(value, limit=1000):
        text = str(value or "")
        return text if len(text) <= limit else text[:limit] + "...<truncated>"

    def on_console(message):
        try:
            message_type = message.type
            if message_type not in ("error", "warning"):
                return
            events["console"].append(
                {
                    "time": time.time(),
                    "type": message_type,
                    "text": trim(message.text),
                    "location": message.location,
                }
            )
        except Exception as error:
            events["console"].append({"time": time.time(), "type": "recorder-error", "text": trim(error)})

    def on_page_error(error):
        events["pageErrors"].append({"time": time.time(), "message": trim(error)})

    def on_request_failed(request):
        try:
            failure = request.failure
            events["requestFailures"].append(
                {
                    "time": time.time(),
                    "method": request.method,
                    "url": request.url,
                    "resourceType": request.resource_type,
                    "failure": failure.get("errorText") if isinstance(failure, dict) else str(failure),
                }
            )
        except Exception as error:
            events["requestFailures"].append({"time": time.time(), "error": trim(error)})

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("requestfailed", on_request_failed)
    setattr(page, "_main_button_events", events)
    return events


def target_link_for(main_state, idx):
    links = (main_state or {}).get("currentLinks") or []
    return links[idx] if len(links) > idx else None


def safe_screenshot(page, path, timeout_ms):
    try:
        page.screenshot(path=str(path), full_page=False, timeout=timeout_ms)
        return {"path": str(path), "error": None}
    except Exception as error:
        return {"path": str(path), "error": str(error)}


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
    mark_progress(args, f"button:{idx}:debug-goto:start")
    page.set_default_navigation_timeout(args.page_timeout_ms)
    page.goto(url, wait_until="commit", timeout=args.page_timeout_ms)
    mark_progress(args, f"button:{idx}:debug-goto:done")
    main_state = wait_for_state(
        page,
        lambda state: is_main_state(state)
        and (state.get("showEvent") or {}).get("buttons")
        and len((state.get("showEvent") or {}).get("buttons") or []) >= idx + 1,
        args.main_timeout_ms,
    )
    if not main_state:
        raise RuntimeError(f"main screen did not become ready for button index {idx}")
    mark_progress(args, f"button:{idx}:debug-main:ready")

    buttons = (main_state.get("showEvent") or {}).get("buttons") or []
    button = buttons[idx]
    click_x = float(button.get("x") or 0) + args.button_center_x
    click_y = float(button.get("y") or 0) + args.button_center_y
    mark_progress(args, f"button:{idx}:click:start")
    activation_method = activate_button(page, args, idx, click_x, click_y)
    mark_progress(args, f"button:{idx}:click:done")
    result_state = wait_for_state(page, lambda state: state and not is_main_state(state), args.result_timeout_ms)
    return main_state, button, {"x": click_x, "y": click_y, "method": activation_method}, result_state


def validate_button_full_route(page, base_url, args, idx, run_id):
    url = build_runner_url(base_url, args.runner, run_id, "full", idx)
    mark_progress(args, f"button:{idx}:full-goto:start")
    page.set_default_navigation_timeout(args.page_timeout_ms)
    page.goto(url, wait_until="commit", timeout=args.page_timeout_ms)
    mark_progress(args, f"button:{idx}:full-goto:done")
    main_state = drive_to_main(page, idx, args.main_timeout_ms)
    if not main_state:
        current_state = summarize_state(read_state(page))
        raise RuntimeError(f"full route did not reach the main screen for button index {idx}; last_state={current_state}")
    buttons = ((main_state or {}).get("showEvent") or {}).get("buttons") or []
    button = buttons[idx] if len(buttons) > idx else BUTTON_FALLBACKS[idx]
    click_x = float(button.get("x") or 0) + args.button_center_x
    click_y = float(button.get("y") or 0) + args.button_center_y
    mark_progress(args, f"button:{idx}:click:start")
    activation_method = activate_button(page, args, idx, click_x, click_y)
    mark_progress(args, f"button:{idx}:click:done")
    if idx in EXPECTED_UNCHANGED_BUTTONS:
        page.wait_for_timeout(1500)
        result_state = read_state(page)
    else:
        result_state = wait_for_state(page, lambda state: state and not is_main_state(state), args.result_timeout_ms)
    return main_state, button, {"x": click_x, "y": click_y, "method": activation_method}, result_state


def validate_button(page, httpd, base_url, args, idx):
    run_id = f"validate_main_button_{idx:02d}_{int(time.time() * 1000)}"
    start_404 = len(httpd.not_found)
    page_events = attach_page_event_recording(page)

    if args.route_mode == "debug-jump":
        main_state, button, click_point, result_state = validate_button_debug_jump(page, httpd, base_url, args, idx, run_id)
    else:
        main_state, button, click_point, result_state = validate_button_full_route(page, base_url, args, idx, run_id)

    page.wait_for_timeout(args.settle_ms)
    stable_state = read_state(page)
    changed_state = bool(result_state and not is_main_state(result_state))
    ui_transition = result_state is None and stable_state is None
    if changed_state:
        status = "ok"
    elif ui_transition:
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
        "targetLink": target_link_for(main_state, idx),
        "clickPoint": click_point,
        "mainState": main_state,
        "resultState": result_state,
        "stableState": stable_state,
        "status": status,
        "local404": local_404,
        "missingMd5s": missing_md5s,
        "pageEvents": page_events,
        "screenshot": str(screenshot_path),
    }
    screenshot = safe_screenshot(page, screenshot_path, args.screenshot_timeout_ms)
    report["screenshot"] = screenshot
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "buttonIndex": idx,
        "buttonName": button.get("name"),
        "buttonId": button.get("index"),
        "slug": slug,
        "report": str(report_path),
        "screenshot": screenshot,
        "status": status,
        "targetLink": report["targetLink"],
        "result": summarize_state(stable_state),
        "local404Count": len(local_404),
        "missingMd5s": missing_md5s,
        "pageErrorCount": len(page_events["pageErrors"]),
        "requestFailureCount": len(page_events["requestFailures"]),
        "consoleIssueCount": len(page_events["console"]),
    }


def write_error_report(page, httpd, args, idx, attempt, error):
    report_name = f"main_button_{idx:02d}_error_attempt_{attempt}"
    screenshot_path = args.out / f"{report_name}.png"
    report_path = args.out / f"{report_name}.json"
    local_404 = list(httpd.not_found)
    page_events = getattr(page, "_main_button_events", None) if page else None
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "routeMode": args.route_mode,
        "buttonIndex": idx,
        "attempt": attempt,
        "status": "error",
        "error": str(error),
        "currentState": summarize_state(read_state(page)) if page else None,
        "local404": local_404,
        "missingMd5s": extract_missing_md5s(local_404),
        "pageEvents": page_events,
        "screenshot": safe_screenshot(page, screenshot_path, args.screenshot_timeout_ms) if page else None,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(report_path)


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
    parser.add_argument("--screenshot-timeout-ms", type=int, default=5000)
    parser.add_argument("--activation-mode", choices=("finish", "click"), default="finish")
    parser.add_argument("--button-retries", type=int, default=1, help="retry count for each selected button")
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
    mark_progress(args, "main:start")
    selected_buttons = parse_button_selector(args.buttons)

    sync_playwright, PlaywrightError = load_playwright()
    mark_progress(args, "playwright:loaded")
    httpd, port = start_server(root, args.port)
    mark_progress(args, f"server:started:{port}")
    base_url = f"http://127.0.0.1:{port}"
    summaries = []
    errors = []

    try:
        with sync_playwright() as playwright:
            try:
                mark_progress(args, "browser-launch:start")
                browser = playwright.chromium.launch(headless=not args.headed)
                mark_progress(args, "browser-launch:done")
            except PlaywrightError as error:
                raise SystemExit(
                    "Could not launch Playwright Chromium.\n"
                    "Install browser assets with:\n"
                    "  python -m playwright install chromium"
                ) from error
            for idx in selected_buttons:
                max_attempts = max(args.button_retries, 0) + 1
                for attempt in range(max_attempts):
                    context = None
                    page = None
                    try:
                        context = browser.new_context(viewport={"width": 1280, "height": 720})
                        page = context.new_page()
                        mark_progress(args, f"button:{idx}:attempt:{attempt}:page:new")
                        mark_progress(args, f"button:{idx}:attempt:{attempt}:start")
                        summary = validate_button(page, httpd, base_url, args, idx)
                        summaries.append(summary)
                        if summary["status"] == "unchanged":
                            errors.append(
                                {
                                    "buttonIndex": idx,
                                    "error": "button click did not leave the main screen",
                                    "report": summary["report"],
                                }
                            )
                        print(
                            f"[ok] button {idx:02d} {summary['buttonName']} "
                            f"status={summary['status']} 404={summary['local404Count']}",
                            flush=True,
                        )
                        break
                    except Exception as error:
                        mark_progress(args, f"button:{idx}:attempt:{attempt}:error:{error}")
                        error_report = None
                        with contextlib.suppress(Exception):
                            error_report = write_error_report(page, httpd, args, idx, attempt, error)
                        if attempt + 1 >= max_attempts:
                            errors.append({"buttonIndex": idx, "error": str(error), "report": error_report})
                            print(f"[error] button {idx:02d}: {error}", file=sys.stderr, flush=True)
                        else:
                            print(
                                f"[retry] button {idx:02d}: {error}",
                                file=sys.stderr,
                                flush=True,
                            )
                    finally:
                        if context:
                            with contextlib.suppress(Exception):
                                context.close()
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
