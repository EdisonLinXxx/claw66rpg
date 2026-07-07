import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")

DEFAULT_OUT = Path("C:/tmp/official_proxy_main_pages")
GAME_WIDTH = 960
GAME_HEIGHT = 540

STATE_JS = r"""
() => {
  const gd = window.GloableData && GloableData.getInstance ? GloableData.getInstance() : null;
  const line = gd && (gd.currentLine || gd.iMain);
  const story = line && line.story;
  const eventAtPos = story && line.pos !== undefined ? story.events[line.pos] : null;
  const event = (line && line.currentEvent) || eventAtPos || null;
  const showEvent = line && line.currentShowEvent;
  const buttons = showEvent && showEvent.buttons
    ? Array.prototype.slice.call(showEvent.buttons).map((button, index) => ({
        index,
        systemIndex: button && button.index,
        x: button && button.x,
        y: button && button.y,
        width: button && button.width,
        height: button && button.height
      }))
    : [];
  const ui = window.UIManager && UIManager.getInstance ? UIManager.getInstance() : null;
  const saveView = ui && window.view && view.SaveFileUIMediator
    ? ui.getViewByName(view.SaveFileUIMediator.NAME)
    : null;
  const localSaveKeys = [];
  for (let index = 0; index < localStorage.length; index++) {
    const key = localStorage.key(index);
    if (/save|local-player|0a235c54/i.test(key)) localSaveKeys.push(key);
  }
  localSaveKeys.sort();
  return {
    href: location.href,
    ready: !!gd,
    storyId: line ? line.storyId : null,
    pos: line ? line.pos : null,
    code: event ? event.Code : null,
    argv: event && event.Argv ? Array.prototype.slice.call(event.Argv) : [],
    storyName: story ? story.Name : null,
    hasShowEvent: !!showEvent,
    buttonsLength: buttons.length,
    buttons,
    currentViewName: ui ? ui.currentViewName : null,
    isSCUIShow: ui ? ui.isSCUIShow : null,
    hasSaveView: !!saveView,
    saveViewIsSave: saveView ? saveView.isSave : null,
    localSaveKeys
  };
}
"""

FINISH_CHOICE_JS = r"""
(choiceIndex) => {
  const gd = GloableData.getInstance();
  const line = gd.currentLine || gd.iMain;
  const showEvent = line && line.currentShowEvent;
  if (!showEvent || typeof showEvent.finish !== "function") return { ok: false, reason: "no showEvent" };
  showEvent.finish(choiceIndex);
  return { ok: true, method: "showEvent.finish", choiceIndex };
}
"""

FINISH_CODE214_JS = r"""
() => {
  const gd = GloableData.getInstance();
  const line = gd.currentLine || gd.iMain;
  if (!line) return { ok: false, reason: "no line" };
  const eventAtPos = line.story && line.pos !== undefined ? line.story.events[line.pos] : null;
  const event = eventAtPos && eventAtPos.Code === 214 ? eventAtPos : (line.currentEvent || eventAtPos);
  if (!event || event.Code !== 214) return { ok: false, reason: "not code214" };

  const strings = gd.dGameSystem && gd.dGameSystem.dGameString;
  if (strings && strings.setVar) {
    try {
      strings.setVar(0, "苏");
      strings.setVar(1, "缘");
      strings.setVar(3, "苏缘");
      strings.setVar(6, "颜灵客栈");
    } catch (_) {}
  }

  const vars = gd.dGameSystem && gd.dGameSystem.vars;
  if (vars && vars.setVar) {
    try {
      if (!parseInt(vars.getVar && vars.getVar(9), 10)) vars.setVar(9, 1);
      if (!parseInt(vars.getVar && vars.getVar(10), 10)) vars.setVar(10, 1);
      if (!parseInt(vars.getVar && vars.getVar(50), 10)) vars.setVar(50, 100);
      if (!parseInt(vars.getVar && vars.getVar(52), 10)) vars.setVar(52, 100);
    } catch (_) {}
  }

  try {
    if (window.view && view.SCustomUI && view.SCustomUI.getInstance) view.SCustomUI.getInstance().hideUI();
  } catch (_) {}
  try {
    const ui = UIManager.getInstance();
    ui.isSCUIShow = false;
    if (ui.gameSystemUILayer && ui.gameSystemUILayer.setMenuVisible) ui.gameSystemUILayer.setMenuVisible(true);
  } catch (_) {}

  gd.CUIFromIndex = -1;
  line.isPause = false;
  line.eventRunFinish = true;
  if (line.currentEvent === event) line.currentEvent = null;
  if (line.currentShowEvent) line.currentShowEvent.isSuiFinish = true;
  if (typeof line.eventFinish === "function") {
    line.eventFinish();
    return { ok: true, method: "code214 eventFinish", argv: event.Argv };
  }
  return { ok: true, method: "code214 flags", argv: event.Argv };
}
"""

FINISH_LINE_JS = r"""
() => {
  const gd = GloableData.getInstance();
  const line = gd.currentLine || gd.iMain;
  if (!line) return { ok: false, reason: "no line" };
  try {
    if (typeof line.eventFinish === "function") {
      line.eventFinish();
      return { ok: true, method: "eventFinish" };
    }
  } catch (error) {
    return { ok: false, error: String(error && (error.stack || error.message) || error) };
  }
  return { ok: false, reason: "no eventFinish" };
}
"""

JUMP_MAIN_JS = r"""
() => {
  const gd = GloableData.getInstance();
  const line = gd.currentLine || gd.iMain;
  if (!line) return { ok: false, reason: "no line" };
  try {
    if (window.view && view.SCustomUI && view.SCustomUI.getInstance) view.SCustomUI.getInstance().hideUI();
  } catch (_) {}
  try {
    const ui = UIManager.getInstance();
    if (window.view && view.SaveFileUIMediator) ui.closeView(view.SaveFileUIMediator.NAME, false);
    ui.isSCUIShow = false;
  } catch (_) {}
  const jump = () => {
    line.isPause = false;
    line.jumpToIndex(648);
    if (typeof line.eventFinish === "function") line.eventFinish();
  };
  if (typeof line.jumpStoryCallBack === "function" && typeof line.jumpToIndex === "function") {
    line.jumpStoryCallBack(15, jump);
    return { ok: true, method: "jumpStoryCallBack(15)->648" };
  }
  return { ok: false, reason: "missing jump methods" };
}
"""

OPEN_SAVE_UI_JS = r"""
() => {
  const ui = UIManager.getInstance();
  if (window.view && view.SaveFileUIMediator) ui.closeView(view.SaveFileUIMediator.NAME, false);
  ui.showView(new view.SaveFileUI(false, true), view.SaveFileUIMediator.NAME);
  return true;
}
"""

OPEN_LOAD_UI_JS = r"""
() => {
  const ui = UIManager.getInstance();
  if (window.view && view.SaveFileUIMediator) ui.closeView(view.SaveFileUIMediator.NAME, false);
  ui.showView(new view.SaveFileUI(false, false), view.SaveFileUIMediator.NAME);
  return true;
}
"""

KNOWN_CHOICES = {
    (1, 7): 0,
    (1, 47): 1,
    (1, 231): 3,
    (1, 1328): 2,
    (1, 2101): 0,
    (1, 1316): 2,
    (1, 2075): 1,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Validate the primary official-player proxy UI path.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--no-start-server", action="store_true")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=240)
    return parser.parse_args()


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def state_label(state):
    if not state:
        return "none"
    return f"{state.get('storyId')}:{state.get('pos')}:{state.get('code')}"


def is_server_ready(base_url):
    try:
        with urllib.request.urlopen(base_url, timeout=1.5) as response:
            return 200 <= response.status < 500
    except (OSError, urllib.error.URLError):
        return False


def start_proxy_server(args, base_url):
    if is_server_ready(base_url):
        return None
    if args.no_start_server:
        raise RuntimeError(f"official proxy is not reachable: {base_url}")

    command = [
        args.python,
        str(args.root / "official_player_proxy.py"),
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--root",
        str(args.root),
    ]
    process = subprocess.Popen(
        command,
        cwd=str(args.root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"official proxy exited early with code {process.returncode}")
        if is_server_ready(base_url):
            return process
        time.sleep(0.3)
    stop_process(process)
    raise RuntimeError(f"official proxy did not start: {base_url}")


def stop_process(process):
    if not process or process.poll() is not None:
        return
    if sys.platform.startswith("win"):
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def stage_to_viewport(page, x, y):
    rect = page.evaluate(
        """
        () => {
          const canvas = document.querySelector("canvas");
          if (!canvas) return null;
          const rect = canvas.getBoundingClientRect();
          return { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
        }
        """
    )
    if not rect:
        raise RuntimeError("game canvas not found")
    return (
        rect["left"] + x * rect["width"] / GAME_WIDTH,
        rect["top"] + y * rect["height"] / GAME_HEIGHT,
    )


def click_stage(page, x, y):
    view_x, view_y = stage_to_viewport(page, x, y)
    page.mouse.click(view_x, view_y)


def wait_for_runtime(page, timeout_seconds):
    deadline = time.time() + timeout_seconds
    last_state = None
    while time.time() < deadline:
        try:
            last_state = page.evaluate(STATE_JS)
            if last_state.get("ready"):
                return last_state
        except Exception as error:
            last_state = {"error": str(error)}
        page.wait_for_timeout(300)
    raise RuntimeError(f"runtime not ready; last_state={last_state}")


def enter_title_menu(page):
    states = []
    for _ in range(16):
        state = page.evaluate(STATE_JS)
        states.append(state)
        if state.get("storyId") == 1 and state.get("pos") == 7 and state.get("code") == 204:
            return states
        page.mouse.click(640, 360)
        page.wait_for_timeout(700)
    return states


def choose_index(state, visits):
    known = KNOWN_CHOICES.get((state.get("storyId"), state.get("pos")))
    if known is not None:
        return known
    count = state.get("buttonsLength") or len(state.get("argv") or []) or 1
    count = max(1, count)
    return (visits.get(state_label(state), 0) - 1) % count


def drive_to_main(page, timeout_seconds):
    deadline = time.time() + timeout_seconds
    visits = {}
    trace = []
    while time.time() < deadline:
        state = page.evaluate(STATE_JS)
        key = state_label(state)
        visits[key] = visits.get(key, 0) + 1

        if state.get("storyId") == 15 and state.get("pos") == 648 and state.get("code") == 204:
            page.wait_for_timeout(1800)
            trace.append({"state": state, "action": {"ok": True, "method": "reached-main"}})
            return trace

        code = state.get("code")
        if code == 210:
            action = {"ok": True, "method": "wait-transition"}
            page.wait_for_timeout(650)
        elif code in (204, 101, 1010):
            action = page.evaluate(FINISH_CHOICE_JS, choose_index(state, visits))
            page.wait_for_timeout(120)
        elif code == 214:
            action = page.evaluate(FINISH_CODE214_JS)
            page.wait_for_timeout(120)
        else:
            action = page.evaluate(FINISH_LINE_JS)
            if not action.get("ok"):
                page.mouse.click(640, 360)
                action = {"ok": True, "method": "center-click fallback", "previous": action}
            page.wait_for_timeout(60)
        trace.append({"state": state, "action": action})
    raise RuntimeError(f"failed to reach main; last_state={page.evaluate(STATE_JS)}")


def ensure_main(page):
    state = page.evaluate(STATE_JS)
    if state.get("storyId") == 15 and state.get("pos") == 648 and state.get("code") == 204:
        page.wait_for_timeout(700)
        return {"ok": True, "method": "already-main"}
    result = page.evaluate(JUMP_MAIN_JS)
    page.wait_for_timeout(1800)
    return result


def screenshot_record(page, out_dir, label):
    path = out_dir / f"{label}.png"
    page.screenshot(path=str(path), full_page=True)
    return {"label": label, "path": str(path), "state": page.evaluate(STATE_JS)}


def click_main_button(page, index):
    state = page.evaluate(STATE_JS)
    buttons = state.get("buttons") or []
    if index >= len(buttons):
        raise RuntimeError(f"main button {index} not available; state={state}")
    button = buttons[index]
    click_stage(page, float(button["x"]) + 50, float(button["y"]) + 50)


def click_menu_bar(page, bar_index):
    # Menu bars are rendered at stable stage coordinates by the official UI.
    y_positions = [207, 270, 333]
    if bar_index >= len(y_positions):
        raise ValueError(f"unsupported menu bar index: {bar_index}")
    click_stage(page, 480, y_positions[bar_index])


def run_save_load_smoke(page, out_dir, records):
    ensure_main(page)
    page.evaluate(OPEN_SAVE_UI_JS)
    page.wait_for_timeout(1500)
    records.append(screenshot_record(page, out_dir, "08_save_ui_open"))

    # Dismiss the official local-save guide if this browser context has not seen it before.
    page.mouse.click(1220, 84)
    page.wait_for_timeout(500)
    page.mouse.click(640, 360)
    page.wait_for_timeout(500)
    page.mouse.click(1220, 84)
    page.wait_for_timeout(500)
    page.mouse.click(355, 190)
    page.wait_for_timeout(2200)
    after_save = page.evaluate(STATE_JS)
    records.append(screenshot_record(page, out_dir, "09_save_ui_after_slot"))

    page.evaluate(OPEN_LOAD_UI_JS)
    page.wait_for_timeout(1500)
    records.append(screenshot_record(page, out_dir, "10_load_ui_open"))
    page.mouse.click(355, 190)
    page.wait_for_timeout(2200)
    after_load = page.evaluate(STATE_JS)

    return {
        "afterSaveKeys": after_save.get("localSaveKeys", []),
        "afterLoadState": after_load,
        "manualSlotKeyPresent": any(key.endswith("local-player1") for key in after_save.get("localSaveKeys", [])),
    }


def run_validation(args, base_url):
    from playwright.sync_api import sync_playwright

    args.out.mkdir(parents=True, exist_ok=True)
    records = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=not args.headed,
            args=["--mute-audio", "--disable-gpu", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()
        bad_responses = []
        request_failures = []

        page.on(
            "response",
            lambda response: bad_responses.append({"status": response.status, "url": response.url})
            if response.status >= 400
            else None,
        )
        page.on(
            "requestfailed",
            lambda request: request_failures.append({"url": request.url, "failure": request.failure}),
        )

        page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
        runtime_state = wait_for_runtime(page, args.timeout_seconds)
        title_states = enter_title_menu(page)
        main_trace = drive_to_main(page, args.timeout_seconds)

        records.append(screenshot_record(page, args.out, "00_main"))

        click_main_button(page, 2)
        page.wait_for_timeout(1000)
        records.append(screenshot_record(page, args.out, "01_overview_menu"))

        click_menu_bar(page, 0)
        page.wait_for_timeout(1800)
        records.append(screenshot_record(page, args.out, "02_overview_detail"))

        ensure_main(page)
        click_main_button(page, 2)
        page.wait_for_timeout(1000)
        click_menu_bar(page, 1)
        page.wait_for_timeout(2200)
        records.append(screenshot_record(page, args.out, "03_ranking"))

        ensure_main(page)
        click_main_button(page, 1)
        page.wait_for_timeout(1000)
        records.append(screenshot_record(page, args.out, "04_order_menu"))

        click_menu_bar(page, 0)
        page.wait_for_timeout(1800)
        records.append(screenshot_record(page, args.out, "05_daily_order"))

        ensure_main(page)
        click_main_button(page, 1)
        page.wait_for_timeout(1000)
        click_menu_bar(page, 1)
        page.wait_for_timeout(1800)
        records.append(screenshot_record(page, args.out, "06_banquet_order"))

        ensure_main(page)
        click_stage(page, 925, 55)
        page.wait_for_timeout(1200)
        records.append(screenshot_record(page, args.out, "07_top_menu"))

        save_load = run_save_load_smoke(page, args.out, records)

        context.close()
        browser.close()

    local_bad = [item for item in bad_responses if f"{args.host}:{args.port}" in item["url"]]
    remote_bad = [item for item in bad_responses if f"{args.host}:{args.port}" not in item["url"]]
    summary = {
        "status": "ok" if not local_bad and save_load["manualSlotKeyPresent"] else "failed",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "baseUrl": base_url,
        "runtimeState": runtime_state,
        "titleStates": title_states,
        "mainTraceLength": len(main_trace),
        "records": records,
        "saveLoad": save_load,
        "badLocal": local_bad,
        "badRemoteSample": remote_bad[:20],
        "requestFailuresSample": request_failures[:20],
    }
    write_json(args.out / "summary.json", summary)
    return summary


def main():
    args = parse_args()
    args.root = args.root.resolve()
    args.out = args.out.resolve()
    base_url = args.base_url or f"http://{args.host}:{args.port}/"
    server_process = None
    try:
        server_process = start_proxy_server(args, base_url)
        summary = run_validation(args, base_url)
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "out": str(args.out / "summary.json"),
                    "screenshots": [record["path"] for record in summary["records"]],
                    "badLocalCount": len(summary["badLocal"]),
                    "manualSlotKeyPresent": summary["saveLoad"]["manualSlotKeyPresent"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        return 0 if summary["status"] == "ok" else 1
    finally:
        stop_process(server_process)


if __name__ == "__main__":
    raise SystemExit(main())
