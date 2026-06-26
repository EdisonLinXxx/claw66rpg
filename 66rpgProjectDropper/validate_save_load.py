import argparse
import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from auto_play_story import (
    build_context,
    drive_state,
    safe_screenshot,
)
from validate_main_buttons import (
    DEFAULT_GAME,
    DEFAULT_VERSION,
    click_stage,
    extract_missing_md5s,
    finish_show_event,
    load_playwright,
    mirror_missing,
    start_server,
    summarize_state,
)


DEFAULT_OUT = Path("C:/tmp/claw_save_load")
DEFAULT_MAIN_BUTTONS = "1"


def build_runner_url(base_url, runner, run_id, clear_storage, debug_jump_story_id=0, debug_jump_index=1):
    params = {
        "localRes": "1",
        "patchNewDSystem": "1",
        "traceRuntime": "1",
        "traceTitle": "1",
        "traceBranchChoice": "1",
        "traceNullPath": "1",
        "quietOafEvents": "1",
        "patchTitleClick": "1",
        "patchFirstSceneLobbyButtons": "1",
        "hideDebug": "1",
        "traceStoryState": "1",
        "storyTraceLimit": "0",
        "traceAutoNameChoice": "1",
        "autoStartTitle": "1",
        "stubCode214Name": "1",
        "stubCode214Birthday": "1",
        "stubInitialVitals": "1",
        "stubPropShop": "1",
        "autoFirstSceneChoice": "0",
        "autoCreateCharacterConfirm": "1",
        "autoNameChoice": "1",
        "autoInnNameChoice": "1",
        "autoCode1010Choice": "last",
        "autoDailyRandomText": "1",
        "autoCode100Text": "1",
        "autoCode100StoryId": "1,44,118",
        "runId": run_id,
    }
    if clear_storage:
        params["clearStorage"] = "1"
    if debug_jump_story_id:
        params["debugJumpStoryId"] = str(debug_jump_story_id)
        params["debugJumpIndex"] = str(debug_jump_index)
        params["debugJumpNoEventFinish"] = "1"
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return f"{base_url}/{runner}?{query}"


def state_key(state):
    if not state:
        return "none"
    return f"{state.get('storyId')}:{state.get('pos')}:{state.get('code')}"


def mark_progress(args, label):
    try:
        with (args.out / "save_load_progress.log").open("a", encoding="utf-8") as progress:
            progress.write(f"{datetime.now(timezone.utc).isoformat()} {label}\n")
    except Exception:
        pass


def read_live_state(page, timeout_ms):
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


def wait_for_state(page, args, timeout_ms, predicate=None):
    deadline = time.time() + timeout_ms / 1000
    last_state = None
    while time.time() < deadline:
        last_state = read_live_state(page, args.evaluate_timeout_ms)
        if last_state and (predicate is None or predicate(last_state)):
            return last_state
        page.wait_for_timeout(args.idle_wait_ms)
    return last_state


def is_expected_debug_jump_state(args, state):
    if not state:
        return False
    if args.debug_jump_story_id == 15 and args.debug_jump_index == 648:
        return state.get("storyId") == 15 and state.get("pos") == 648 and state.get("code") == 204
    return state.get("storyId") == args.debug_jump_story_id and state.get("pos") == args.debug_jump_index


def wait_for_save_runtime(page, args, timeout_ms):
    deadline = time.time() + timeout_ms / 1000
    last_status = None
    while time.time() < deadline:
        last_status = page.evaluate(
            """
            () => {
              const gd = window.GloableData && GloableData.getInstance ? GloableData.getInstance() : null;
              return {
                hasGloableData: !!gd,
                hasRunnerLocalSave: typeof window.__runnerLocalSave === 'function',
                hasRunnerLocalRestore: typeof window.__runnerLocalRestore === 'function'
              };
            }
            """
        )
        if last_status.get("hasRunnerLocalSave") and last_status.get("hasRunnerLocalRestore"):
            return last_status
        page.wait_for_timeout(args.idle_wait_ms)
    return last_status


def recover_no_state(page, args, context, last_state, last_action):
    recoveries = context.setdefault("recoveries", {})
    if not last_state or not last_action:
        return {"acted": False, "method": "wait:no-state"}

    key = state_key(last_state)
    if key == "1:1316:204" and last_action.get("choiceIndex") == 2 and not recoveries.get("name-confirm"):
        recoveries["name-confirm"] = True
        if finish_show_event(page, 3):
            return {"acted": True, "method": "recovery:showEvent.finish(3)"}
        click_stage(page, 440 + args.button_center_x, 310 + args.button_center_y)
        return {"acted": True, "method": "recovery:click-name-confirm"}

    if key == "1:2075:204" and last_action.get("choiceIndex") in (0, 1) and not recoveries.get("inn-confirm"):
        recoveries["inn-confirm"] = True
        if finish_show_event(page, 2):
            return {"acted": True, "method": "recovery:showEvent.finish(2)"}
        click_stage(page, 530 + args.button_center_x, 300 + args.button_center_y)
        return {"acted": True, "method": "recovery:click-inn-confirm"}

    return {"acted": False, "method": "wait:no-state"}


def drive_steps(page, args, context, count, label, trace):
    records = []
    idx = 0
    no_state_steps = 0
    last_state = None
    last_action = None
    while idx < count:
        state = read_live_state(page, args.evaluate_timeout_ms)
        if not state:
            no_state_steps += 1
            action = {"acted": False, "method": "wait:no-state"}
            if no_state_steps == 2:
                action = recover_no_state(page, args, context, last_state, last_action)
            record = {
                "label": label,
                "step": idx,
                "state": None,
                "action": action,
            }
            records.append(record)
            trace.write(json.dumps(record, ensure_ascii=False) + "\n")
            trace.flush()
            print(f"[{label} {idx:03d}] none action={action.get('method')}", flush=True)
            if no_state_steps > args.max_no_state_steps:
                raise RuntimeError(f"{label} saw no story state for {no_state_steps} consecutive waits")
            page.wait_for_timeout(args.action_wait_ms if action.get("acted") else args.idle_wait_ms)
            continue

        no_state_steps = 0
        action = drive_state(page, args, state, context)
        last_state = state
        last_action = action
        record = {
            "label": label,
            "step": idx,
            "state": summarize_state(state) if state else None,
            "action": action,
        }
        records.append(record)
        trace.write(json.dumps(record, ensure_ascii=False) + "\n")
        trace.flush()
        print(
            f"[{label} {idx:03d}] {state_key(state)} action={action.get('method')} "
            f"choice={action.get('choiceIndex')}",
            flush=True,
        )
        idx += 1
        page.wait_for_timeout(args.action_wait_ms if action.get("acted") else args.idle_wait_ms)
    return records


def storage_summary(page):
    return page.evaluate(
        """
        () => ({
          local: Array.from({ length: localStorage.length }, (_, i) => {
            const key = localStorage.key(i);
            const value = localStorage.getItem(key) || '';
            return { key, len: value.length, preview: value.slice(0, 120) };
          }).sort((a, b) => a.key.localeCompare(b.key)),
          session: Array.from({ length: sessionStorage.length }, (_, i) => {
            const key = sessionStorage.key(i);
            const value = sessionStorage.getItem(key) || '';
            return { key, len: value.length, preview: value.slice(0, 120) };
          }).sort((a, b) => a.key.localeCompare(b.key))
        })
        """
    )


def save_slot_info(page, slot):
    return page.evaluate(
        """
        (slot) => {
          if (typeof window.__runnerLocalSaveInfo !== 'function') return { ok: false, reason: 'runner local save unavailable' };
          return window.__runnerLocalSaveInfo(slot);
        }
        """,
        slot,
    )


def call_save(page, slot):
    return page.evaluate(
        """
        (slot) => {
          if (typeof window.__runnerLocalSave !== 'function') return { ok: false, reason: 'runner local save unavailable' };
          try {
            return window.__runnerLocalSave(slot);
          } catch (error) {
            return { ok: false, error: String(error && (error.stack || error.message) || error) };
          }
        }
        """,
        slot,
    )


def call_restore(page, slot):
    return page.evaluate(
        """
        (slot) => {
          if (typeof window.__runnerLocalRestore !== 'function') return { ok: false, reason: 'runner local restore unavailable' };
          try {
            return window.__runnerLocalRestore(slot);
          } catch (error) {
            return { ok: false, error: String(error && (error.stack || error.message) || error) };
          }
        }
        """,
        slot,
    )


def state_near(saved, restored, tolerance):
    if not saved or not restored:
        return False
    if saved.get("storyId") != restored.get("storyId"):
        return False
    try:
        return abs(int(saved.get("pos")) - int(restored.get("pos"))) <= tolerance
    except Exception:
        return False


def restore_match(saved, advanced, restored, tolerance):
    detail = {
        "ok": False,
        "sameStory": False,
        "nearSaved": False,
        "rolledBackFromAdvanced": False,
    }
    if not saved or not restored:
        return detail

    detail["sameStory"] = saved.get("storyId") == restored.get("storyId")
    if not detail["sameStory"]:
        return detail

    detail["nearSaved"] = state_near(saved, restored, tolerance)
    try:
        saved_pos = int(saved.get("pos"))
        restored_pos = int(restored.get("pos"))
        advanced_pos = int(advanced.get("pos")) if advanced and advanced.get("storyId") == saved.get("storyId") else None
    except Exception:
        advanced_pos = None
        saved_pos = None
        restored_pos = None

    if advanced_pos is not None and saved_pos is not None and restored_pos is not None:
        lower = min(saved_pos, advanced_pos)
        upper = max(saved_pos, advanced_pos)
        detail["rolledBackFromAdvanced"] = lower <= restored_pos <= upper and restored_pos != advanced_pos

    detail["ok"] = detail["nearSaved"] or detail["rolledBackFromAdvanced"]
    return detail


def settle_restored_state(page, args, context, saved_state, advanced_state, restored_state, trace):
    records = []
    matched = restore_match(saved_state, advanced_state, restored_state, args.restore_pos_tolerance)
    idx = 0
    while not matched.get("ok") and idx < args.restore_settle_steps:
        state = read_live_state(page, args.evaluate_timeout_ms)
        current_match = restore_match(saved_state, advanced_state, state, args.restore_pos_tolerance)
        if current_match.get("ok"):
            restored_state = state
            matched = current_match
            break
        action = drive_state(page, args, state, context) if state else {"acted": False, "method": "wait:no-state"}
        record = {
            "label": "restore-settle",
            "step": idx,
            "state": summarize_state(state) if state else None,
            "action": action,
        }
        records.append(record)
        trace.write(json.dumps(record, ensure_ascii=False) + "\n")
        trace.flush()
        print(
            f"[restore-settle {idx:03d}] {state_key(state)} action={action.get('method')} "
            f"choice={action.get('choiceIndex')}",
            flush=True,
        )
        page.wait_for_timeout(args.action_wait_ms if action.get("acted") else args.idle_wait_ms)
        restored_state = wait_for_state(page, args, args.state_timeout_ms)
        matched = restore_match(saved_state, advanced_state, restored_state, args.restore_pos_tolerance)
        idx += 1
    return restored_state, matched, records


def run_validation(browser, httpd, base_url, args):
    run_id = f"save_load_{int(time.time() * 1000)}"
    trace_path = args.out / "save_load_trace.jsonl"
    start_404 = len(httpd.not_found)
    mark_progress(args, "new-context:start")
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    mark_progress(args, "new-context:done")
    page = context.new_page()
    mark_progress(args, "new-page:done")
    page.set_default_timeout(args.evaluate_timeout_ms)
    page.set_default_navigation_timeout(args.page_timeout_ms)

    with trace_path.open("w", encoding="utf-8") as trace:
        url = build_runner_url(
            base_url,
            args.runner,
            run_id,
            clear_storage=True,
            debug_jump_story_id=args.debug_jump_story_id,
            debug_jump_index=args.debug_jump_index,
        )
        print(f"loading initial run: {url}", flush=True)
        mark_progress(args, "initial-goto:start")
        page.goto(url, wait_until="commit", timeout=args.page_timeout_ms)
        mark_progress(args, "initial-goto:done")
        page.wait_for_timeout(args.initial_wait_ms)
        mark_progress(args, "initial-wait:done")
        initial_state = wait_for_state(page, args, args.state_timeout_ms)
        if not initial_state:
            raise RuntimeError("initial run did not expose story state")
        if args.debug_jump_story_id:
            ready_state = wait_for_state(
                page,
                args,
                args.state_timeout_ms,
                lambda state: is_expected_debug_jump_state(args, state),
            )
            if not is_expected_debug_jump_state(args, ready_state):
                raise RuntimeError(f"initial run did not reach requested save state: last_state={summarize_state(ready_state)}")
        mark_progress(args, "initial-state:seen")

        play_context = build_context(args)
        before_save_records = drive_steps(page, args, play_context, args.save_after_steps, "before-save", trace)
        mark_progress(args, "before-save:done")
        saved_state = read_live_state(page, args.evaluate_timeout_ms)
        if not saved_state:
            raise RuntimeError("could not read save-point state")

        before_storage = storage_summary(page)
        mark_progress(args, "save:start")
        save_result = call_save(page, args.slot)
        page.wait_for_timeout(args.save_wait_ms)
        save_info = save_slot_info(page, args.slot)
        after_storage = storage_summary(page)
        mark_progress(args, "save:done")
        if not save_result.get("ok"):
            raise RuntimeError(f"save failed: {save_result}")
        if not save_info.get("exists"):
            raise RuntimeError(f"save slot was not written: {save_info}")

        advanced_records = drive_steps(page, args, play_context, args.advance_steps, "after-save", trace)
        mark_progress(args, "after-save:done")
        advanced_state = read_live_state(page, args.evaluate_timeout_ms)
        saved_page_screenshot = safe_screenshot(page, args.out / "saved_page.png")
        page.close()

        page2 = context.new_page()
        mark_progress(args, "restore-page:new")
        page2.set_default_timeout(args.evaluate_timeout_ms)
        page2.set_default_navigation_timeout(args.page_timeout_ms)
        restore_url = build_runner_url(
            base_url,
            args.runner,
            f"{run_id}_restore",
            clear_storage=False,
        )
        print(f"loading restore run: {restore_url}", flush=True)
        mark_progress(args, "restore-goto:start")
        page2.goto(restore_url, wait_until="commit", timeout=args.page_timeout_ms)
        mark_progress(args, "restore-goto:done")
        page2.wait_for_timeout(args.initial_wait_ms)
        mark_progress(args, "restore-wait:done")

        restore_before_state = read_live_state(page2, args.evaluate_timeout_ms)
        restore_runtime = wait_for_save_runtime(page2, args, args.state_timeout_ms)
        if not (restore_runtime and restore_runtime.get("hasRunnerLocalRestore")):
            raise RuntimeError(f"restore run did not expose save runtime: {restore_runtime}")
        restore_slot_before = save_slot_info(page2, args.slot)
        if not restore_slot_before.get("exists"):
            raise RuntimeError(f"restore run could not see save slot: {restore_slot_before}")
        restore_result = call_restore(page2, args.slot)
        mark_progress(args, "restore-call:done")
        if not restore_result.get("ok"):
            raise RuntimeError(f"restore failed: {restore_result}")
        restored_state = wait_for_state(page2, args, args.state_timeout_ms)
        page2.wait_for_timeout(args.restore_wait_ms)
        mark_progress(args, "restore-state:done")

        settle_context = build_context(args)
        restored_state, restored_matches, restore_settle_records = settle_restored_state(
            page2,
            args,
            settle_context,
            saved_state,
            advanced_state,
            restored_state,
            trace,
        )
        if not restored_matches.get("ok"):
            raise RuntimeError(
                "restored state is not compatible with saved state: "
                f"saved={summarize_state(saved_state)} restored={summarize_state(restored_state)}"
            )

        continue_context = build_context(args)
        continue_records = drive_steps(page2, args, continue_context, args.continue_steps, "continue", trace)
        mark_progress(args, "continue:done")
        continued_state = read_live_state(page2, args.evaluate_timeout_ms)

        screenshots = {
            "saved": saved_page_screenshot,
            "restored": safe_screenshot(page2, args.out / "restored_page.png"),
        }

    local_404 = httpd.not_found[start_404:]
    missing_md5s = extract_missing_md5s(local_404)
    mirror_report = mirror_missing(args.root, args.game, args.version, missing_md5s) if args.mirror_missing else None
    context.close()
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "runId": run_id,
        "status": "ok",
        "slot": args.slot,
        "savedState": summarize_state(saved_state),
        "advancedState": summarize_state(advanced_state) if advanced_state else None,
        "restoreBeforeState": summarize_state(restore_before_state) if restore_before_state else None,
        "restoredState": summarize_state(restored_state) if restored_state else None,
        "continuedState": summarize_state(continued_state) if continued_state else None,
        "restoredMatchesSaved": restored_matches.get("ok"),
        "restoreMatch": restored_matches,
        "saveMethod": "runner-local-save-v1",
        "saveResult": save_result,
        "restoreResult": restore_result,
        "saveInfo": save_info,
        "restoreRuntime": restore_runtime,
        "restoreSlotBefore": restore_slot_before,
        "storageBefore": before_storage,
        "storageAfter": after_storage,
        "beforeSaveRecords": before_save_records,
        "advancedRecords": advanced_records,
        "restoreSettleRecords": restore_settle_records,
        "continueRecords": continue_records,
        "local404": local_404,
        "missingMd5s": missing_md5s,
        "mirrorReport": mirror_report,
        "trace": str(trace_path),
        "screenshots": screenshots,
    }


def main():
    parser = argparse.ArgumentParser(description="Validate save, reload, restore, and continue-play behavior.")
    parser.add_argument("--root", default=".", help="runner repository root")
    parser.add_argument("--runner", default="h5_runner_experiment.html", help="runner HTML file")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="report output directory")
    parser.add_argument("--port", type=int, default=8765, help="preferred local HTTP port")
    parser.add_argument("--slot", type=int, default=0, help="zero-based runner local save slot")
    parser.add_argument("--save-after-steps", type=int, default=0)
    parser.add_argument("--advance-steps", type=int, default=1)
    parser.add_argument("--continue-steps", type=int, default=1)
    parser.add_argument("--debug-jump-story-id", type=int, default=15, help="story id to jump to before save/load validation; 0 disables")
    parser.add_argument("--debug-jump-index", type=int, default=648)
    parser.add_argument("--restore-pos-tolerance", type=int, default=8)
    parser.add_argument("--restore-settle-steps", type=int, default=8)
    parser.add_argument("--choice-policy", choices=("round-robin", "first", "last"), default="round-robin")
    parser.add_argument("--main-buttons", default=DEFAULT_MAIN_BUTTONS)
    parser.add_argument("--headed", action="store_true", help="show the browser window")
    parser.add_argument("--page-timeout-ms", type=int, default=15000)
    parser.add_argument("--initial-wait-ms", type=int, default=8000)
    parser.add_argument("--state-timeout-ms", type=int, default=12000)
    parser.add_argument("--max-no-state-steps", type=int, default=60)
    parser.add_argument("--evaluate-timeout-ms", type=int, default=5000)
    parser.add_argument("--action-wait-ms", type=int, default=2200)
    parser.add_argument("--idle-wait-ms", type=int, default=500)
    parser.add_argument("--save-wait-ms", type=int, default=3000)
    parser.add_argument("--restore-wait-ms", type=int, default=7000)
    parser.add_argument("--button-center-x", type=float, default=50)
    parser.add_argument("--button-center-y", type=float, default=40)
    parser.add_argument("--game", default=DEFAULT_GAME, help="game URL, gindex, or guid for --mirror-missing")
    parser.add_argument("--version", default=DEFAULT_VERSION, help="game version for --mirror-missing")
    parser.add_argument("--mirror-missing", action="store_true", help="mirror all missing MD5s after validation")
    args = parser.parse_args()

    args.root = Path(args.root).resolve()
    args.out = Path(args.out)
    if not (args.root / args.runner).exists():
        raise SystemExit(f"runner not found: {args.root / args.runner}")
    args.out.mkdir(parents=True, exist_ok=True)
    mark_progress(args, "main:start")

    sync_playwright, PlaywrightError = load_playwright()
    mark_progress(args, "playwright:loaded")
    httpd, port = start_server(args.root, args.port)
    mark_progress(args, f"server:started:{port}")
    base_url = f"http://127.0.0.1:{port}"
    summary = None
    exit_code = 0
    try:
        with sync_playwright() as playwright:
            browser = None
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
            try:
                summary = run_validation(browser, httpd, base_url, args)
            except Exception as error:
                exit_code = 1
                local_404 = httpd.not_found[:]
                summary = {
                    "generatedAt": datetime.now(timezone.utc).isoformat(),
                    "status": "failed",
                    "error": str(error),
                    "traceback": traceback.format_exc(),
                    "local404": local_404,
                    "missingMd5s": extract_missing_md5s(local_404),
                }
            finally:
                if browser:
                    browser.close()
    finally:
        httpd.shutdown()
        httpd.server_close()

    summary_path = args.out / "save_load_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"summary: {summary_path}", flush=True)
    if summary["missingMd5s"]:
        print("missing md5s:")
        for md5 in summary["missingMd5s"]:
            print(f"  {md5}")
        raise SystemExit(2)
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
