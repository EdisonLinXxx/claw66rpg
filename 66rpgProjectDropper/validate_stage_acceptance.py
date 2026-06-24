import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")

DEFAULT_OUT = Path("C:/tmp/claw_stage_acceptance")
DEFAULT_MAIN_BUTTONS = "0,1,2,3,4,5,6,7,9,10,11"


def read_json(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def state_label(state):
    if not state:
        return "none"
    return f"{state.get('storyId')}:{state.get('pos')}:{state.get('code')}"


def kill_process_tree(process):
    if process.poll() is not None:
        return
    if sys.platform.startswith("win"):
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.kill()


def run_command(name, command, cwd, log_path, timeout_seconds):
    started = time.time()
    print(f"[{name}] running: {' '.join(str(part) for part in command)}", flush=True)
    child_env = os.environ.copy()
    timed_out = False
    log_path.write_text("stdout/stderr inherited by validate_stage_acceptance.py\n", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=child_env,
    )
    try:
        returncode = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_process_tree(process)
        returncode = -9
    duration = round(time.time() - started, 3)
    timeout_text = " timedOut=true" if timed_out else ""
    print(f"[{name}] exit={returncode} duration={duration}s{timeout_text} log={log_path}", flush=True)
    return {
        "name": name,
        "command": [str(part) for part in command],
        "returnCode": returncode,
        "durationSeconds": duration,
        "timeoutSeconds": timeout_seconds,
        "timedOut": timed_out,
        "log": str(log_path),
    }


def summarize_main(result, summary):
    if not summary:
        return {
            "name": "mainButtons",
            "status": "failed",
            "ok": False,
            "reason": "timed out" if result.get("timedOut") else "missing main_buttons_summary.json",
            "returnCode": result["returnCode"],
            "timedOut": result.get("timedOut", False),
        }
    errors = summary.get("errors") or []
    missing = summary.get("missingMd5s") or []
    buttons = summary.get("buttons") or []
    ok = result["returnCode"] == 0 and not errors and not missing and bool(summary.get("allLocalResourcesPresent"))
    return {
        "name": "mainButtons",
        "status": "ok" if ok else "failed",
        "ok": ok,
        "returnCode": result["returnCode"],
        "timedOut": result.get("timedOut", False),
        "selectedButtons": summary.get("selectedButtons") or [],
        "validatedButtonCount": len(buttons),
        "errors": errors,
        "missingMd5s": missing,
        "reports": [item.get("report") for item in buttons if item.get("report")],
    }


def summarize_autoplay(result, summary):
    if not summary:
        return {
            "name": "storyAutoplay",
            "status": "failed",
            "ok": False,
            "reason": "timed out" if result.get("timedOut") else "missing story_autoplay_summary.json",
            "returnCode": result["returnCode"],
            "timedOut": result.get("timedOut", False),
        }
    missing = summary.get("missingMd5s") or []
    status = summary.get("status")
    ok = result["returnCode"] == 0 and status in ("duration_reached", "step_limit_reached") and not missing
    return {
        "name": "storyAutoplay",
        "status": "ok" if ok else "failed",
        "ok": ok,
        "returnCode": result["returnCode"],
        "timedOut": result.get("timedOut", False),
        "autoplayStatus": status,
        "error": summary.get("error"),
        "durationSeconds": summary.get("durationSeconds"),
        "traceCount": summary.get("traceCount"),
        "uniqueStateCount": summary.get("uniqueStateCount"),
        "lastState": summary.get("lastState"),
        "missingMd5s": missing,
        "trace": summary.get("trace"),
        "finalScreenshot": summary.get("finalScreenshot"),
    }


def summarize_save_load(result, summary):
    if not summary:
        return {
            "name": "saveLoad",
            "status": "failed",
            "ok": False,
            "reason": "timed out" if result.get("timedOut") else "missing save_load_summary.json",
            "returnCode": result["returnCode"],
            "timedOut": result.get("timedOut", False),
        }
    missing = summary.get("missingMd5s") or []
    ok = (
        result["returnCode"] == 0
        and summary.get("status") == "ok"
        and bool(summary.get("restoredMatchesSaved"))
        and not missing
    )
    return {
        "name": "saveLoad",
        "status": "ok" if ok else "failed",
        "ok": ok,
        "returnCode": result["returnCode"],
        "timedOut": result.get("timedOut", False),
        "savedState": summary.get("savedState"),
        "advancedState": summary.get("advancedState"),
        "restoredState": summary.get("restoredState"),
        "continuedState": summary.get("continuedState"),
        "restoreMatch": summary.get("restoreMatch"),
        "missingMd5s": missing,
        "trace": summary.get("trace"),
        "screenshots": summary.get("screenshots"),
    }


def markdown_report(summary):
    checks = summary["checks"]
    lines = [
        "# First Game Stage Acceptance Report",
        "",
        f"- Generated: {summary['generatedAt']}",
        f"- Root: `{summary['root']}`",
        f"- Overall status: **{summary['status']}**",
        f"- Output: `{summary['out']}`",
        "",
        "## Check Results",
        "",
        "| Check | Status | Key evidence |",
        "| --- | --- | --- |",
    ]

    main = checks.get("mainButtons") or {}
    lines.append(
        "| Main buttons | {status} | {count}/{selected} buttons, errors={errors}, missingMd5s={missing} |".format(
            status=main.get("status", "skipped"),
            count=main.get("validatedButtonCount", 0),
            selected=len(main.get("selectedButtons") or []),
            errors=len(main.get("errors") or []),
            missing=len(main.get("missingMd5s") or []),
        )
    )

    autoplay = checks.get("storyAutoplay") or {}
    lines.append(
        "| Story autoplay | {status} | status={autoplay_status}, traceCount={trace_count}, uniqueStates={unique_states}, last={last} |".format(
            status=autoplay.get("status", "skipped"),
            autoplay_status=autoplay.get("autoplayStatus"),
            trace_count=autoplay.get("traceCount"),
            unique_states=autoplay.get("uniqueStateCount"),
            last=state_label(autoplay.get("lastState")),
        )
    )

    save_load = checks.get("saveLoad") or {}
    lines.append(
        "| Save/load | {status} | saved={saved}, restored={restored}, continued={continued}, restoredMatchesSaved={matched} |".format(
            status=save_load.get("status", "skipped"),
            saved=state_label(save_load.get("savedState")),
            restored=state_label(save_load.get("restoredState")),
            continued=state_label(save_load.get("continuedState")),
            matched=bool((save_load.get("restoreMatch") or {}).get("ok")),
        )
    )

    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Main buttons summary: `{summary['artifacts'].get('mainButtonsSummary')}`",
            f"- Story autoplay summary: `{summary['artifacts'].get('storyAutoplaySummary')}`",
            f"- Save/load summary: `{summary['artifacts'].get('saveLoadSummary')}`",
            f"- Machine summary: `{summary['artifacts'].get('summaryJson')}`",
        ]
    )

    failures = [check for check in checks.values() if not check.get("ok")]
    if failures:
        lines.extend(["", "## Failures", ""])
        for check in failures:
            lines.append(f"- {check.get('name')}: {check.get('reason') or check.get('error') or check.get('status')}")

    return "\n".join(lines) + "\n"


def maybe_add(arguments, flag, value):
    if value is not None and value != "":
        arguments.extend([flag, str(value)])


def add_switch(arguments, enabled, flag):
    if enabled:
        arguments.append(flag)


def use_powershell_wrappers(args):
    return sys.platform.startswith("win") and not args.direct_python_validators


def powershell_script_command(args, root, script_name):
    return [
        args.powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(root / "scripts" / script_name),
    ]


def run_acceptance(args):
    args.out.mkdir(parents=True, exist_ok=True)
    root = args.root.resolve()
    python = args.python
    run_results = {}
    checks = {}

    main_out = args.out / "main_buttons"
    autoplay_out = args.out / "story_autoplay"
    save_load_out = args.out / "save_load"

    if not args.skip_save_load:
        if use_powershell_wrappers(args):
            command = powershell_script_command(args, root, "validate-save-load.ps1")
            command.extend(
                [
                    "-Python",
                    python,
                    "-Out",
                    str(save_load_out),
                    "-Port",
                    str(args.save_load_port),
                    "-Slot",
                    str(args.slot),
                    "-SaveAfterSteps",
                    str(args.save_after_steps),
                    "-AdvanceSteps",
                    str(args.advance_steps),
                    "-ContinueSteps",
                    str(args.continue_steps),
                    "-DebugJumpStoryId",
                    str(args.debug_jump_story_id),
                    "-DebugJumpIndex",
                    str(args.debug_jump_index),
                    "-RestoreSettleSteps",
                    str(args.restore_settle_steps),
                    "-MaxNoStateSteps",
                    str(args.max_no_state_steps),
                    "-ChoicePolicy",
                    args.choice_policy,
                    "-MainButtons",
                    args.main_buttons,
                ]
            )
            add_switch(command, args.headed, "-Headed")
            add_switch(command, args.mirror_missing, "-MirrorMissing")
        else:
            command = [
                python,
                str(root / "66rpgProjectDropper" / "validate_save_load.py"),
                "--root",
                str(root),
                "--out",
                str(save_load_out),
                "--port",
                str(args.save_load_port),
                "--slot",
                str(args.slot),
                "--save-after-steps",
                str(args.save_after_steps),
                "--advance-steps",
                str(args.advance_steps),
                "--continue-steps",
                str(args.continue_steps),
                "--debug-jump-story-id",
                str(args.debug_jump_story_id),
                "--debug-jump-index",
                str(args.debug_jump_index),
                "--restore-settle-steps",
                str(args.restore_settle_steps),
                "--max-no-state-steps",
                str(args.max_no_state_steps),
                "--choice-policy",
                args.choice_policy,
                "--main-buttons",
                args.main_buttons,
            ]
            add_switch(command, args.headed, "--headed")
            add_switch(command, args.mirror_missing, "--mirror-missing")
        run_results["saveLoad"] = run_command(
            "saveLoad",
            command,
            root,
            args.out / "save_load.log",
            args.save_load_timeout_seconds,
        )
        checks["saveLoad"] = summarize_save_load(
            run_results["saveLoad"],
            read_json(save_load_out / "save_load_summary.json"),
        )

    if not args.skip_main_buttons:
        if use_powershell_wrappers(args):
            command = powershell_script_command(args, root, "validate-main-buttons.ps1")
            command.extend(
                [
                    "-Python",
                    python,
                    "-Out",
                    str(main_out),
                    "-Port",
                    str(args.main_port),
                    "-RouteMode",
                    args.route_mode,
                ]
            )
            maybe_add(command, "-Buttons", args.buttons)
            add_switch(command, args.headed, "-Headed")
            add_switch(command, args.mirror_missing, "-MirrorMissing")
        else:
            command = [
                python,
                str(root / "66rpgProjectDropper" / "validate_main_buttons.py"),
                "--root",
                str(root),
                "--out",
                str(main_out),
                "--port",
                str(args.main_port),
                "--route-mode",
                args.route_mode,
            ]
            maybe_add(command, "--buttons", args.buttons)
            add_switch(command, args.headed, "--headed")
            add_switch(command, args.mirror_missing, "--mirror-missing")
        run_results["mainButtons"] = run_command(
            "mainButtons",
            command,
            root,
            args.out / "main_buttons.log",
            args.main_timeout_seconds,
        )
        checks["mainButtons"] = summarize_main(
            run_results["mainButtons"],
            read_json(main_out / "main_buttons_summary.json"),
        )

    if not args.skip_autoplay:
        if use_powershell_wrappers(args):
            command = powershell_script_command(args, root, "autoplay-story.ps1")
            command.extend(
                [
                    "-Python",
                    python,
                    "-Out",
                    str(autoplay_out),
                    "-Port",
                    str(args.autoplay_port),
                    "-DurationSeconds",
                    str(args.autoplay_duration_seconds),
                    "-MaxSteps",
                    str(args.autoplay_max_steps),
                    "-ChoicePolicy",
                    args.choice_policy,
                    "-MainButtons",
                    args.main_buttons,
                ]
            )
            add_switch(command, args.headed, "-Headed")
            add_switch(command, args.mirror_missing, "-MirrorMissing")
        else:
            command = [
                python,
                str(root / "66rpgProjectDropper" / "auto_play_story.py"),
                "--root",
                str(root),
                "--out",
                str(autoplay_out),
                "--port",
                str(args.autoplay_port),
                "--duration-seconds",
                str(args.autoplay_duration_seconds),
                "--max-steps",
                str(args.autoplay_max_steps),
                "--choice-policy",
                args.choice_policy,
                "--main-buttons",
                args.main_buttons,
            ]
            add_switch(command, args.headed, "--headed")
            add_switch(command, args.mirror_missing, "--mirror-missing")
        autoplay_timeout = args.autoplay_timeout_seconds or args.autoplay_duration_seconds + 180
        run_results["storyAutoplay"] = run_command(
            "storyAutoplay",
            command,
            root,
            args.out / "story_autoplay.log",
            autoplay_timeout,
        )
        checks["storyAutoplay"] = summarize_autoplay(
            run_results["storyAutoplay"],
            read_json(autoplay_out / "story_autoplay_summary.json"),
        )

    overall_ok = bool(checks) and all(check.get("ok") for check in checks.values())
    summary_path = args.out / "stage_acceptance_summary.json"
    report_path = args.out / "stage_acceptance_report.md"
    summary = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "out": str(args.out),
        "status": "ok" if overall_ok else "failed",
        "checks": checks,
        "runs": run_results,
        "artifacts": {
            "mainButtonsSummary": str(main_out / "main_buttons_summary.json"),
            "storyAutoplaySummary": str(autoplay_out / "story_autoplay_summary.json"),
            "saveLoadSummary": str(save_load_out / "save_load_summary.json"),
            "summaryJson": str(summary_path),
            "reportMarkdown": str(report_path),
        },
    }
    write_json(summary_path, summary)
    report_path.write_text(markdown_report(summary), encoding="utf-8")
    print(f"summary: {summary_path}", flush=True)
    print(f"report: {report_path}", flush=True)
    return summary


def summarize_existing(args):
    args.out.mkdir(parents=True, exist_ok=True)
    root = args.root.resolve()
    main_out = args.out / "main_buttons"
    autoplay_out = args.out / "story_autoplay"
    save_load_out = args.out / "save_load"
    checks = {}

    if not args.skip_save_load:
        checks["saveLoad"] = summarize_save_load(
            {"returnCode": 0, "timedOut": False},
            read_json(save_load_out / "save_load_summary.json"),
        )
    if not args.skip_main_buttons:
        checks["mainButtons"] = summarize_main(
            {"returnCode": 0, "timedOut": False},
            read_json(main_out / "main_buttons_summary.json"),
        )
    if not args.skip_autoplay:
        checks["storyAutoplay"] = summarize_autoplay(
            {"returnCode": 0, "timedOut": False},
            read_json(autoplay_out / "story_autoplay_summary.json"),
        )

    overall_ok = bool(checks) and all(check.get("ok") for check in checks.values())
    summary_path = args.out / "stage_acceptance_summary.json"
    report_path = args.out / "stage_acceptance_report.md"
    summary = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "out": str(args.out),
        "status": "ok" if overall_ok else "failed",
        "checks": checks,
        "runs": {},
        "artifacts": {
            "mainButtonsSummary": str(main_out / "main_buttons_summary.json"),
            "storyAutoplaySummary": str(autoplay_out / "story_autoplay_summary.json"),
            "saveLoadSummary": str(save_load_out / "save_load_summary.json"),
            "summaryJson": str(summary_path),
            "reportMarkdown": str(report_path),
        },
    }
    write_json(summary_path, summary)
    report_path.write_text(markdown_report(summary), encoding="utf-8")
    print(f"summary: {summary_path}", flush=True)
    print(f"report: {report_path}", flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Run first-game stage acceptance checks and write a combined report.")
    parser.add_argument("--root", default=".", help="runner repository root")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="combined report output directory")
    parser.add_argument("--python", default=sys.executable, help="Python executable used for child validators")
    parser.add_argument("--powershell", default="powershell", help="PowerShell executable used for wrapper scripts on Windows")
    parser.add_argument("--direct-python-validators", action="store_true", help="call validator Python files directly instead of Windows wrapper scripts")
    parser.add_argument("--buttons", default="", help="main-screen button indices for main-button validation")
    parser.add_argument("--route-mode", choices=("full", "debug-jump"), default="debug-jump")
    parser.add_argument("--main-port", type=int, default=8765)
    parser.add_argument("--autoplay-port", type=int, default=8865)
    parser.add_argument("--save-load-port", type=int, default=8765)
    parser.add_argument("--main-timeout-seconds", type=int, default=900)
    parser.add_argument("--autoplay-timeout-seconds", type=int, default=0, help="0 means duration + 180 seconds")
    parser.add_argument("--save-load-timeout-seconds", type=int, default=420)
    parser.add_argument("--autoplay-duration-seconds", type=int, default=300)
    parser.add_argument("--autoplay-max-steps", type=int, default=250)
    parser.add_argument("--choice-policy", choices=("round-robin", "first", "last"), default="round-robin")
    parser.add_argument("--main-buttons", default=DEFAULT_MAIN_BUTTONS)
    parser.add_argument("--slot", type=int, default=0)
    parser.add_argument("--save-after-steps", type=int, default=24)
    parser.add_argument("--advance-steps", type=int, default=8)
    parser.add_argument("--continue-steps", type=int, default=5)
    parser.add_argument("--debug-jump-story-id", type=int, default=44)
    parser.add_argument("--debug-jump-index", type=int, default=5)
    parser.add_argument("--restore-settle-steps", type=int, default=8)
    parser.add_argument("--max-no-state-steps", type=int, default=60)
    parser.add_argument("--skip-main-buttons", action="store_true")
    parser.add_argument("--skip-autoplay", action="store_true")
    parser.add_argument("--skip-save-load", action="store_true")
    parser.add_argument("--summarize-only", action="store_true", help="read existing child summaries and write combined report")
    parser.add_argument("--headed", action="store_true", help="show browser windows")
    parser.add_argument("--mirror-missing", action="store_true", help="mirror all missing MD5s after each check")
    args = parser.parse_args()

    args.root = Path(args.root)
    args.out = Path(args.out)
    summary = summarize_existing(args) if args.summarize_only else run_acceptance(args)
    if summary["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
