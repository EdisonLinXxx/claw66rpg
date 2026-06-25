import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_OUT = Path("C:/tmp/claw_story_coverage")
DEFAULT_POLICIES = "round-robin,first,last"
DEFAULT_MAIN_BUTTONS = "0,1,2,3,4,5,6,7,9,10,11"
OK_AUTOPLAY_STATUSES = {"duration_reached", "step_limit_reached"}


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")


def read_json(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_csv(value):
    return [item.strip() for item in (value or "").replace(";", ",").split(",") if item.strip()]


def safe_slug(value):
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value).strip("_") or "run"


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


def run_autoplay_policy(args, policy, index):
    policy_out = args.out / safe_slug(policy)
    policy_out.mkdir(parents=True, exist_ok=True)
    log_path = policy_out / "autoplay.log"
    summary_path = policy_out / "story_autoplay_summary.json"
    checkpoint_path = policy_out / "story_autoplay_checkpoint.json"
    port = args.start_port + index * args.port_step
    command = [
        args.python,
        str(args.root / "66rpgProjectDropper" / "auto_play_story.py"),
        "--root",
        str(args.root),
        "--out",
        str(policy_out),
        "--port",
        str(port),
        "--duration-seconds",
        str(args.duration_seconds),
        "--max-steps",
        str(args.max_steps),
        "--choice-policy",
        policy,
        "--choice-loop-escape-after",
        str(args.choice_loop_escape_after),
        "--main-buttons",
        args.main_buttons,
    ]
    if args.headed:
        command.append("--headed")
    if args.mirror_missing:
        command.append("--mirror-missing")

    timeout_seconds = args.timeout_seconds or args.duration_seconds + 180
    started = time.time()
    timed_out = False
    print(f"[coverage:{policy}] running on port {port}", flush=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        log.write(" ".join(command) + "\n\n")
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=str(args.root),
            stdout=log,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
        )
        try:
            returncode = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            kill_process_tree(process)
            returncode = -9

    duration = round(time.time() - started, 3)
    summary = read_json(summary_path)
    summary_source = "summary"
    if not summary:
        summary = read_json(checkpoint_path)
        summary_source = "checkpoint" if summary else "missing"
    missing = (summary or {}).get("missingMd5s") or []
    autoplay_status = (summary or {}).get("status")
    if summary_source == "checkpoint" and timed_out and autoplay_status == "running":
        autoplay_status = "timeout_checkpoint"
    ok = returncode == 0 and not timed_out and autoplay_status in OK_AUTOPLAY_STATUSES and not missing
    result = {
        "policy": policy,
        "ok": ok,
        "returnCode": returncode,
        "timedOut": timed_out,
        "summarySource": summary_source,
        "durationSeconds": duration,
        "autoplayStatus": autoplay_status,
        "error": (summary or {}).get("error"),
        "traceCount": (summary or {}).get("traceCount"),
        "uniqueStateCount": (summary or {}).get("uniqueStateCount"),
        "lastState": (summary or {}).get("lastState"),
        "missingMd5s": missing,
        "out": str(policy_out),
        "summary": str(summary_path),
        "checkpoint": str(checkpoint_path),
        "log": str(log_path),
    }
    print(
        "[coverage:{policy}] status={status} ok={ok} states={states} trace={trace} missing={missing}".format(
            policy=policy,
            status=autoplay_status or "missing-summary",
            ok=ok,
            states=result["uniqueStateCount"],
            trace=result["traceCount"],
            missing=len(missing),
        ),
        flush=True,
    )
    return result, summary


def merge_summaries(summaries):
    unique_states = {}
    missing_md5s = set()
    trace_count = 0
    duration_seconds = 0.0

    for summary in summaries:
        if not summary:
            continue
        trace_count += int(summary.get("traceCount") or 0)
        duration_seconds += float(summary.get("durationSeconds") or 0)
        missing_md5s.update(summary.get("missingMd5s") or [])
        for key, state in (summary.get("uniqueStates") or {}).items():
            if key == "none":
                continue
            unique_states.setdefault(key, state)

    states_by_story = {}
    for key, state in unique_states.items():
        story_id = str((state or {}).get("storyId") or key.split(":", 1)[0])
        states_by_story[story_id] = states_by_story.get(story_id, 0) + 1

    return {
        "traceCount": trace_count,
        "durationSeconds": round(duration_seconds, 3),
        "uniqueStateCount": len(unique_states),
        "uniqueStates": unique_states,
        "statesByStory": dict(sorted(states_by_story.items(), key=lambda item: item[0])),
        "missingMd5s": sorted(missing_md5s),
    }


def markdown_report(summary):
    lines = [
        "# Story Coverage Collection Report",
        "",
        f"- Generated: {summary['generatedAt']}",
        f"- Root: `{summary['root']}`",
        f"- Overall status: **{summary['status']}**",
        f"- Output: `{summary['out']}`",
        f"- Policies: `{', '.join(summary['policies'])}`",
        "",
        "## Run Results",
        "",
        "| Policy | Status | OK | Trace | Unique states | Missing MD5s | Last state |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for run in summary["runs"]:
        lines.append(
            "| {policy} | {status} | {ok} | {trace} | {states} | {missing} | {last} |".format(
                policy=run["policy"],
                status=run.get("autoplayStatus") or "missing-summary",
                ok="yes" if run.get("ok") else "no",
                trace=run.get("traceCount") or 0,
                states=run.get("uniqueStateCount") or 0,
                missing=len(run.get("missingMd5s") or []),
                last=state_label(run.get("lastState")),
            )
        )

    merged = summary["merged"]
    lines.extend(
        [
            "",
            "## Merged Coverage",
            "",
            f"- Total trace entries: {merged['traceCount']}",
            f"- Total runtime seconds: {merged['durationSeconds']}",
            f"- Unique story states: {merged['uniqueStateCount']}",
            f"- Missing MD5s: {len(merged['missingMd5s'])}",
            "",
            "### States By Story",
            "",
            "| Story ID | Unique state keys |",
            "| --- | ---: |",
        ]
    )
    for story_id, count in merged["statesByStory"].items():
        lines.append(f"| {story_id} | {count} |")

    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Machine summary: `{summary['artifacts']['summaryJson']}`",
            f"- Report: `{summary['artifacts']['reportMarkdown']}`",
        ]
    )
    for run in summary["runs"]:
        lines.append(f"- {run['policy']} summary: `{run['summary']}`")
        lines.append(f"- {run['policy']} checkpoint: `{run['checkpoint']}`")
        lines.append(f"- {run['policy']} log: `{run['log']}`")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Run multiple autoplay policies and merge story coverage evidence.")
    parser.add_argument("--root", default=".", help="runner repository root")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="coverage output directory")
    parser.add_argument("--python", default=sys.executable, help="Python executable for autoplay child runs")
    parser.add_argument("--policies", default=DEFAULT_POLICIES, help="comma separated autoplay choice policies")
    parser.add_argument("--duration-seconds", type=int, default=120)
    parser.add_argument("--max-steps", type=int, default=120)
    parser.add_argument("--timeout-seconds", type=int, default=0, help="0 means duration + 180 seconds per policy")
    parser.add_argument("--start-port", type=int, default=8895)
    parser.add_argument("--port-step", type=int, default=10)
    parser.add_argument("--main-buttons", default=DEFAULT_MAIN_BUTTONS)
    parser.add_argument("--choice-loop-escape-after", type=int, default=4)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--mirror-missing", action="store_true")
    args = parser.parse_args()

    args.root = Path(args.root).resolve()
    args.out = Path(args.out)
    if not (args.root / "66rpgProjectDropper" / "auto_play_story.py").exists():
        raise SystemExit(f"auto_play_story.py not found under {args.root}")
    args.out.mkdir(parents=True, exist_ok=True)

    policies = parse_csv(args.policies)
    if not policies:
        raise SystemExit("at least one policy is required")

    runs = []
    summaries = []
    for index, policy in enumerate(policies):
        result, child_summary = run_autoplay_policy(args, policy, index)
        runs.append(result)
        summaries.append(child_summary)

    merged = merge_summaries(summaries)
    overall_ok = bool(runs) and all(run["ok"] for run in runs) and not merged["missingMd5s"]
    summary_path = args.out / "story_coverage_summary.json"
    report_path = args.out / "story_coverage_report.md"
    summary = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "root": str(args.root),
        "out": str(args.out),
        "status": "ok" if overall_ok else "failed",
        "policies": policies,
        "durationSecondsPerPolicy": args.duration_seconds,
        "maxStepsPerPolicy": args.max_steps,
        "runs": runs,
        "merged": merged,
        "artifacts": {
            "summaryJson": str(summary_path),
            "reportMarkdown": str(report_path),
        },
    }
    write_json(summary_path, summary)
    report_path.write_text(markdown_report(summary), encoding="utf-8")
    print(f"summary: {summary_path}", flush=True)
    print(f"report: {report_path}", flush=True)
    if summary["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
