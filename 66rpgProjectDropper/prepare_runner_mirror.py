import argparse
import hashlib
import json
import os
import re
import struct
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import urllib3

from dry_run_probe import fetch_versions, fetch_bytes, resolve_guid, resource_url


def file_md5(path):
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_map_bin(map_bin):
    entries = []
    offset = 4
    total = len(map_bin)
    while offset + 4 <= total:
        name_len = struct.unpack_from("<I", map_bin, offset)[0]
        offset += 4
        if name_len <= 0 or offset + name_len + 8 > total:
            break

        name = map_bin[offset : offset + name_len].decode("utf-8", errors="replace")
        offset += name_len

        file_size = struct.unpack_from("<I", map_bin, offset)[0]
        offset += 4

        md5_len = struct.unpack_from("<I", map_bin, offset)[0]
        offset += 4
        if md5_len <= 0 or offset + md5_len > total:
            break

        md5 = map_bin[offset : offset + md5_len].decode("ascii", errors="replace")
        offset += md5_len
        entries.append((name, file_size, md5, ""))
    return entries


def write_api_map(entries, root):
    api_path = root / "api" / "oapi_map.php"
    api_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"status": 1, "msg": "local runner map proxy", "data": entries}
    api_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return api_path


def mirror_entry(http, entry, cdn_host, root, retries=3):
    name, expected_size, md5, _ = entry
    expected_md5 = md5[:32].lower()
    target = root / "shareres" / md5[:2].lower() / md5
    target.parent.mkdir(parents=True, exist_ok=True)
    if (
        target.exists()
        and target.stat().st_size == expected_size
        and file_md5(target) == expected_md5
    ):
        return {
            "name": name,
            "path": str(target),
            "expected_size": expected_size,
            "actual_size": expected_size,
            "md5": md5,
            "cached": True,
        }

    url = resource_url(md5, cdn_host)
    temp_target = target.with_name(f"{target.name}.part-{os.getpid()}")
    last_error = None
    for attempt in range(1, retries + 1):
        response = None
        try:
            response = http.request("GET", url, preload_content=False, timeout=60.0)
            if response.status != 200:
                raise RuntimeError(f"GET failed {response.status}: {url}")
            actual_size = 0
            actual_md5 = hashlib.md5()
            with temp_target.open("wb") as stream:
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    stream.write(chunk)
                    actual_size += len(chunk)
                    actual_md5.update(chunk)
            if actual_size != expected_size:
                raise RuntimeError(
                    f"size mismatch for {name}: expected={expected_size} actual={actual_size}"
                )
            if actual_md5.hexdigest() != expected_md5:
                raise RuntimeError(
                    f"md5 mismatch for {name}: expected={expected_md5} actual={actual_md5.hexdigest()}"
                )
            temp_target.replace(target)
            break
        except Exception as exc:
            last_error = exc
            temp_target.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(min(2**attempt, 8))
        finally:
            if response is not None:
                response.release_conn()
    else:
        raise RuntimeError(f"failed after {retries} attempts: {name}: {last_error}")

    return {
        "name": name,
        "path": str(target),
        "expected_size": expected_size,
        "actual_size": actual_size,
        "md5": md5,
        "cached": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Prepare local files needed by h5_runner_experiment.html.")
    parser.add_argument("game", help="66rpg game URL, gindex, or guid")
    parser.add_argument("--version", help="specific version; default is latest")
    parser.add_argument("--cdn-host", default="https://dlcdn1.cgyouxi.com", help="resource CDN host")
    parser.add_argument(
        "--map-kind",
        choices=("h5", "legacy"),
        default="h5",
        help="resource map source: h5 uses official H5 Map_32.bin; legacy uses older Map.bin",
    )
    parser.add_argument("--root", default=".", help="runner web root")
    parser.add_argument(
        "--mirror-name",
        action="append",
        default=[],
        help="mapped filename to mirror locally; may be repeated. Defaults to data/game.bin when no mirror selector is provided.",
    )
    parser.add_argument(
        "--mirror-md5",
        action="append",
        default=[],
        help="mapped MD5 to mirror locally; may be repeated.",
    )
    parser.add_argument(
        "--mirror-log",
        action="append",
        default=[],
        help="runner log file to scan for /shareres/xx/<md5> URLs and mirror missing mapped resources.",
    )
    parser.add_argument(
        "--mirror-all",
        action="store_true",
        help="mirror every unique resource from the selected map into the local shareres cache.",
    )
    parser.add_argument("--workers", type=int, default=8, help="parallel downloads used with --mirror-all")
    parser.add_argument("--retries", type=int, default=3, help="download attempts per resource")
    parser.add_argument(
        "--skip-api-map",
        action="store_true",
        help="do not replace api/oapi_map.php when only populating the shareres cache",
    )
    args = parser.parse_args()

    http = urllib3.PoolManager()
    guid, _ = resolve_guid(http, args.game)
    versions = fetch_versions(http, guid)
    version = str(args.version or versions[-1]["version"])
    root = Path(args.root)

    if args.map_kind == "h5":
        map_url = f"{args.cdn_host.rstrip('/')}/web/{guid}/{version}/Map_32.bin"
    else:
        map_url = f"https://wcdn1.cgyouxi.com/web/{guid}/{version}/Map.bin"
    entries = parse_map_bin(fetch_bytes(http, map_url))
    api_path = None if args.skip_api_map else write_api_map(entries, root)
    by_name = {entry[0].lower(): entry for entry in entries}
    by_md5 = {entry[2].lower(): entry for entry in entries}
    log_md5s = []
    for log_path in args.mirror_log:
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")
        log_md5s.extend(re.findall(r"/shareres/[0-9a-fA-F]{2}/([0-9a-fA-F]{32}(?:\.[A-Za-z0-9]+)?)", text))

    mirror_names = args.mirror_name or (
        [] if args.mirror_all or args.mirror_md5 or log_md5s else ["data/game.bin"]
    )
    selected = []
    seen = set()
    if args.mirror_all:
        for entry in entries:
            if entry[2].lower() not in seen:
                selected.append(entry)
                seen.add(entry[2].lower())
    for mirror_name in mirror_names:
        entry = by_name.get(mirror_name.lower())
        if not entry:
            raise SystemExit(f"mapped file not found: {mirror_name}")
        if entry[2].lower() not in seen:
            selected.append(entry)
            seen.add(entry[2].lower())
    for mirror_md5 in args.mirror_md5 + log_md5s:
        entry = by_md5.get(mirror_md5.lower())
        if not entry:
            raise SystemExit(f"mapped md5 not found: {mirror_md5}")
        if entry[2].lower() not in seen:
            selected.append(entry)
            seen.add(entry[2].lower())
    print(f"guid: {guid}")
    print(f"version: {version}")
    print(f"map_kind: {args.map_kind}")
    print(f"map_url: {map_url}")
    print(f"api_map: {api_path or 'skipped'} entries={len(entries)}")
    print(
        f"selected: resources={len(selected)} "
        f"declared_bytes={sum(entry[1] for entry in selected)} workers={args.workers}"
    )

    mirrored_items = []
    failures = []
    started_at = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(mirror_entry, http, entry, args.cdn_host, root, args.retries): entry
            for entry in selected
        }
        for completed, future in enumerate(as_completed(futures), 1):
            entry = futures[future]
            try:
                mirrored_items.append(future.result())
            except Exception as exc:
                failures.append({"name": entry[0], "md5": entry[2], "error": str(exc)})
            if completed % 100 == 0 or completed == len(selected):
                elapsed = max(time.monotonic() - started_at, 0.001)
                downloaded = sum(not item["cached"] for item in mirrored_items)
                cached = sum(item["cached"] for item in mirrored_items)
                print(
                    f"progress: completed={completed}/{len(selected)} downloaded={downloaded} "
                    f"cached={cached} failed={len(failures)} rate={completed / elapsed:.1f}/s",
                    flush=True,
                )

    print(
        f"mirror complete: ok={len(mirrored_items)} failed={len(failures)} "
        f"downloaded_bytes={sum(item['actual_size'] for item in mirrored_items if not item['cached'])}"
    )
    for failure in failures[:20]:
        print(f"failed: {failure['name']} md5={failure['md5']} error={failure['error']}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
