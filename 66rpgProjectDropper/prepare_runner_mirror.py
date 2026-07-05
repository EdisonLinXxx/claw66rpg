import argparse
import json
import re
import struct
from pathlib import Path
from urllib.parse import urlparse

import urllib3

from dry_run_probe import fetch_versions, fetch_bytes, resolve_guid, resource_url


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


def mirror_entry(http, entry, cdn_host, root):
    name, expected_size, md5, _ = entry
    target = root / "shareres" / md5[:2].lower() / md5
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        actual_size = target.stat().st_size
    else:
        data = fetch_bytes(http, resource_url(md5, cdn_host))
        target.write_bytes(data)
        actual_size = len(data)
    return {
        "name": name,
        "path": str(target),
        "expected_size": expected_size,
        "actual_size": actual_size,
        "md5": md5,
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
    api_path = write_api_map(entries, root)
    by_name = {entry[0].lower(): entry for entry in entries}
    by_md5 = {entry[2].lower(): entry for entry in entries}
    log_md5s = []
    for log_path in args.mirror_log:
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")
        log_md5s.extend(re.findall(r"/shareres/[0-9a-fA-F]{2}/([0-9a-fA-F]{32})", text))

    mirror_names = args.mirror_name or ([] if args.mirror_md5 or log_md5s else ["data/game.bin"])
    selected = []
    seen = set()
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
    mirrored_items = [mirror_entry(http, entry, args.cdn_host, root) for entry in selected]

    print(f"guid: {guid}")
    print(f"version: {version}")
    print(f"map_kind: {args.map_kind}")
    print(f"map_url: {map_url}")
    print(f"api_map: {api_path} entries={len(entries)}")
    for mirrored in mirrored_items:
        print(
            f"mirrored: {mirrored['name']} expected={mirrored['expected_size']} "
            f"actual={mirrored['actual_size']} path={mirrored['path']}"
        )


if __name__ == "__main__":
    main()
