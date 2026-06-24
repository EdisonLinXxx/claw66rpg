import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from validate_main_buttons import (
    DEFAULT_GAME,
    DEFAULT_VERSION,
    build_runner_url,
    click_stage,
    extract_missing_md5s,
    finish_show_event,
    load_playwright,
    mirror_missing,
    start_server,
    summarize_state,
)


DEFAULT_OUT = Path("C:/tmp/claw_autoplay")
DEFAULT_MAIN_BUTTONS = "0,1,2,3,4,5,6,7,9,10,11"
KNOWN_SHOW_EVENT_CHOICES = {
    (1, 47): [1],
    (1, 231): [3],
    (1, 1316): [2, 3],
    (1, 1328): [0, 2],
}


def parse_int_list(value):
    if not value:
        return []
    return [int(item.strip()) for item in value.replace(" ", ",").split(",") if item.strip()]


def state_key(state):
    if not state:
        return "none"
    return f"{state.get('storyId')}:{state.get('pos')}:{state.get('code')}"


def read_live_state(page, timeout_ms):
    try:
        text = page.locator("#runner-story-state").text_content(timeout=timeout_ms)
    except Exception:
        return None
    return json.loads(text) if text else None


def finish_line_event(page):
    return page.evaluate(
        """
        () => {
          const gd = window.GloableData && GloableData.getInstance ? GloableData.getInstance() : null;
          const line = gd && gd.currentLine;
          if (!line) return { ok: false, method: '', reason: 'no current line' };
          if (typeof line.eventFinish === 'function') {
            line.eventFinish();
            return { ok: true, method: 'eventFinish()' };
          }
          return { ok: false, method: '', reason: 'no eventFinish method' };
        }
        """
    )


def finish_code214(page):
    return page.evaluate(
        """
        () => {
          const gd = window.GloableData && GloableData.getInstance ? GloableData.getInstance() : null;
          const line = gd && gd.currentLine;
          if (!line) return { ok: false, method: '', reason: 'no current line' };
          const eventAtPos = line.story && line.story.events && line.pos !== undefined ? line.story.events[line.pos] : null;
          const event = eventAtPos && eventAtPos.Code === 214 ? eventAtPos : line.currentEvent || eventAtPos;
          if (!event || event.Code !== 214) return { ok: false, method: '', reason: 'not code 214' };
          const strings = gd && gd.dGameSystem && gd.dGameSystem.dGameString;
          if (strings && strings.setVar) {
            try {
              strings.setVar(0, 'Auto');
              strings.setVar(1, 'Player');
              strings.setVar(3, 'AutoPlayer');
              strings.setVar(6, 'AutoInn');
            } catch (stringError) {}
          }
          const vars = gd && gd.dGameSystem && gd.dGameSystem.vars;
          if (vars && vars.setVar) {
            try {
              if (!parseInt(vars.getVar && vars.getVar(9), 10)) vars.setVar(9, 1);
              if (!parseInt(vars.getVar && vars.getVar(10), 10)) vars.setVar(10, 1);
            } catch (varError) {}
          }
          try {
            if (window.view && view.SCustomUI && view.SCustomUI.getInstance) view.SCustomUI.getInstance().hideUI();
          } catch (hideError) {}
          if (window.UIManager && UIManager.getInstance) {
            try {
              UIManager.getInstance().isSCUIShow = false;
              if (UIManager.getInstance().gameSystemUILayer && UIManager.getInstance().gameSystemUILayer.setMenuVisible) {
                UIManager.getInstance().gameSystemUILayer.setMenuVisible(true);
              }
            } catch (uiError) {}
          }
          if (gd) gd.CUIFromIndex = -1;
          line.isPause = false;
          line.eventRunFinish = true;
          if (line.currentEvent === event) line.currentEvent = null;
          if (line.currentShowEvent) line.currentShowEvent.isSuiFinish = true;
          if (typeof line.eventFinish === 'function') {
            line.eventFinish();
            return { ok: true, method: 'code214 eventFinish()' };
          }
          return { ok: true, method: 'code214 flags' };
        }
        """
    )


def choice_count_for_state(state):
    show_event = state.get("showEvent") or {}
    buttons = show_event.get("buttons") or []
    if buttons:
        return len(buttons)
    argv = state.get("argv") or []
    links = state.get("currentLinks") or []
    return max(len(argv), len(links), 1)


def choose_index(args, state, context):
    key = state_key(state)
    visit = context["state_visits"].get(key, 0)
    context["state_visits"][key] = visit + 1

    known_sequence = KNOWN_SHOW_EVENT_CHOICES.get((state.get("storyId"), state.get("pos")))
    if known_sequence:
        known_choice = known_sequence[min(visit, len(known_sequence) - 1)]
        return known_choice, "known-state"

    if is_main_state_like(state):
        buttons = ((state.get("showEvent") or {}).get("buttons") or [])
        if not buttons:
            return 0, "main-empty"
        for _ in range(len(context["main_buttons"])):
            selected = context["main_buttons"][context["main_cursor"] % len(context["main_buttons"])]
            context["main_cursor"] += 1
            if 0 <= selected < len(buttons):
                return selected, "main-sequence"
        return 0, "main-fallback"

    count = choice_count_for_state(state)
    if args.choice_policy == "first":
        return 0, "first"
    if args.choice_policy == "last":
        return count - 1, "last"
    return visit % count, "round-robin"


def is_main_state_like(state):
    return bool(state and state.get("storyId") == 15 and state.get("pos") == 648 and state.get("code") == 204)


def drive_state(page, args, state, context):
    if not state:
        page.wait_for_timeout(args.idle_wait_ms)
        return {"acted": False, "method": "wait:no-state"}

    code = state.get("code")
    action = {
        "acted": False,
        "method": "",
        "choiceIndex": None,
        "choiceReason": "",
        "stateKey": state_key(state),
    }

    if code in (101, 1010, 204):
        choice_index, reason = choose_index(args, state, context)
        action.update({"choiceIndex": choice_index, "choiceReason": reason})
        if finish_show_event(page, choice_index):
            action.update({"acted": True, "method": f"showEvent.finish({choice_index})"})
            return action
        buttons = ((state.get("showEvent") or {}).get("buttons") or [])
        if buttons and choice_index < len(buttons):
            button = buttons[choice_index]
            click_stage(page, float(button.get("x") or 0) + args.button_center_x, float(button.get("y") or 0) + args.button_center_y)
            action.update({"acted": True, "method": "click-button-fallback"})
            return action

    if code == 214:
        result = finish_code214(page)
        action.update({"acted": bool(result.get("ok")), "method": result.get("method") or result.get("reason") or "code214"})
        return action

    if code == 100:
        result = finish_line_event(page)
        action.update({"acted": bool(result.get("ok")), "method": result.get("method") or result.get("reason") or "code100"})
        return action

    click_stage(page, 480, 500)
    action.update({"acted": True, "method": "stage-click"})
    return action


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_screenshot(page, path):
    try:
        page.screenshot(path=str(path), full_page=False)
        return {"path": str(path), "error": None}
    except Exception as error:
        return {"path": str(path), "error": str(error)}


def build_context(args):
    main_buttons = parse_int_list(args.main_buttons)
    if not main_buttons:
        main_buttons = parse_int_list(DEFAULT_MAIN_BUTTONS)
    return {
        "state_visits": {},
        "main_buttons": main_buttons,
        "main_cursor": 0,
    }


def run_autoplay(page, httpd, base_url, args):
    run_id = f"autoplay_{int(time.time() * 1000)}"
    url = build_runner_url(base_url, args.runner, run_id, "full", 0)
    context = build_context(args)
    trace_path = args.out / "story_autoplay_trace.jsonl"
    start_404 = len(httpd.not_found)
    started = time.time()
    deadline = started + args.duration_seconds
    trace_count = 0
    last_key = None
    same_key_actions = 0
    no_state_steps = 0
    final_status = "duration_reached"
    final_error = None
    unique_states = {}
    last_state = None

    print(f"loading: {url}", flush=True)
    page.goto(url, wait_until="domcontentloaded", timeout=args.page_timeout_ms)
    if args.initial_wait_ms:
        print(f"waiting for runner init: {args.initial_wait_ms}ms", flush=True)
        page.wait_for_timeout(args.initial_wait_ms)
    with trace_path.open("w", encoding="utf-8") as trace:
        for step in range(args.max_steps):
            now = time.time()
            if now >= deadline:
                final_status = "duration_reached"
                break

            state = read_live_state(page, args.evaluate_timeout_ms)
            last_state = state
            key = state_key(state)
            unique_states[key] = summarize_state(state) if state else None

            if state is None:
                no_state_steps += 1
            else:
                no_state_steps = 0

            if key != last_key:
                last_key = key
                same_key_actions = 0

            action = drive_state(page, args, state, context)
            if action.get("acted"):
                same_key_actions += 1

            entry = {
                "step": step,
                "elapsedSeconds": round(now - started, 3),
                "state": summarize_state(state) if state else None,
                "action": action,
                "local404Count": len(httpd.not_found) - start_404,
            }
            trace.write(json.dumps(entry, ensure_ascii=False) + "\n")
            trace.flush()
            trace_count += 1

            print(
                f"[step {step:04d}] {key} action={action.get('method')} "
                f"choice={action.get('choiceIndex')} 404={entry['local404Count']}",
                flush=True,
            )

            if args.screenshot_every and step and step % args.screenshot_every == 0:
                safe_screenshot(page, args.out / f"step_{step:04d}.png")

            if same_key_actions > args.max_same_state_actions:
                final_status = "blocked"
                final_error = f"state {key} did not change after {same_key_actions} actions"
                break
            if no_state_steps > args.max_no_state_steps:
                final_status = "blocked"
                final_error = f"no story state for {no_state_steps} consecutive steps"
                break

            page.wait_for_timeout(args.action_wait_ms if action.get("acted") else args.idle_wait_ms)
        else:
            final_status = "step_limit_reached"

    final_screenshot = safe_screenshot(page, args.out / "final.png")
    local_404 = httpd.not_found[start_404:]
    missing_md5s = extract_missing_md5s(local_404)
    mirror_report = mirror_missing(args.root, args.game, args.version, missing_md5s) if args.mirror_missing else None
    summary = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "runId": run_id,
        "status": final_status,
        "error": final_error,
        "durationSeconds": round(time.time() - started, 3),
        "traceCount": trace_count,
        "uniqueStateCount": len(unique_states),
        "uniqueStates": unique_states,
        "lastState": summarize_state(last_state) if last_state else None,
        "local404": local_404,
        "missingMd5s": missing_md5s,
        "mirrorReport": mirror_report,
        "trace": str(trace_path),
        "finalScreenshot": final_screenshot,
        "url": url,
    }
    write_json(args.out / "story_autoplay_summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Autoplay the h5 runner story flow and record trace, blockers, and missing resources.")
    parser.add_argument("--root", default=".", help="runner repository root")
    parser.add_argument("--runner", default="h5_runner_experiment.html", help="runner HTML file")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="report output directory")
    parser.add_argument("--port", type=int, default=8865, help="preferred local HTTP port")
    parser.add_argument("--duration-seconds", type=int, default=300)
    parser.add_argument("--max-steps", type=int, default=250)
    parser.add_argument("--max-same-state-actions", type=int, default=6)
    parser.add_argument("--max-no-state-steps", type=int, default=8)
    parser.add_argument("--choice-policy", choices=("round-robin", "first", "last"), default="round-robin")
    parser.add_argument("--main-buttons", default=DEFAULT_MAIN_BUTTONS, help="comma separated main-screen button indices to cycle")
    parser.add_argument("--headed", action="store_true", help="show the browser window")
    parser.add_argument("--page-timeout-ms", type=int, default=15000)
    parser.add_argument("--initial-wait-ms", type=int, default=8000)
    parser.add_argument("--evaluate-timeout-ms", type=int, default=3000)
    parser.add_argument("--action-wait-ms", type=int, default=2200)
    parser.add_argument("--idle-wait-ms", type=int, default=500)
    parser.add_argument("--button-center-x", type=float, default=50)
    parser.add_argument("--button-center-y", type=float, default=40)
    parser.add_argument("--screenshot-every", type=int, default=0)
    parser.add_argument("--game", default=DEFAULT_GAME, help="game URL, gindex, or guid for --mirror-missing")
    parser.add_argument("--version", default=DEFAULT_VERSION, help="game version for --mirror-missing")
    parser.add_argument("--mirror-missing", action="store_true", help="mirror all missing MD5s after autoplay")
    args = parser.parse_args()

    args.root = Path(args.root).resolve()
    args.out = Path(args.out)
    if not (args.root / args.runner).exists():
        raise SystemExit(f"runner not found: {args.root / args.runner}")
    args.out.mkdir(parents=True, exist_ok=True)

    sync_playwright, PlaywrightError = load_playwright()
    httpd, port = start_server(args.root, args.port)
    base_url = f"http://127.0.0.1:{port}"
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
            page.set_default_timeout(args.evaluate_timeout_ms)
            summary = run_autoplay(page, httpd, base_url, args)
            browser.close()
    finally:
        httpd.shutdown()
        httpd.server_close()

    print(f"summary: {args.out / 'story_autoplay_summary.json'}")
    if summary["missingMd5s"]:
        print("missing md5s:")
        for md5 in summary["missingMd5s"]:
            print(f"  {md5}")
    if summary["status"] == "blocked":
        raise SystemExit(1)
    if summary["missingMd5s"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
