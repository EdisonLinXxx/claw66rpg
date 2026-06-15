import argparse
import json
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
    data = fetch_bytes(http, resource_url(md5, cdn_host))
    target = root / "shareres" / md5[:2].lower() / md5
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {
        "name": name,
        "path": str(target),
        "expected_size": expected_size,
        "actual_size": len(data),
        "md5": md5,
    }


def main():
    parser = argparse.ArgumentParser(description="Prepare local files needed by h5_runner_experiment.html.")
    parser.add_argument("game", help="66rpg game URL, gindex, or guid")
    parser.add_argument("--version", help="specific version; default is latest")
    parser.add_argument("--cdn-host", default="https://dlcdn1.cgyouxi.com", help="resource CDN host")
    parser.add_argument("--root", default=".", help="runner web root")
    parser.add_argument(
        "--mirror-name",
        default="data/game.bin",
        help="mapped filename to mirror locally; default mirrors only the main game bin",
    )
    args = parser.parse_args()

    http = urllib3.PoolManager()
    guid, _ = resolve_guid(http, args.game)
    versions = fetch_versions(http, guid)
    version = str(args.version or versions[-1]["version"])
    root = Path(args.root)

    map_url = f"https://wcdn1.cgyouxi.com/web/{guid}/{version}/Map.bin"
    entries = parse_map_bin(fetch_bytes(http, map_url))
    api_path = write_api_map(entries, root)
    by_name = {entry[0].lower(): entry for entry in entries}
    entry = by_name.get(args.mirror_name.lower())
    if not entry:
        raise SystemExit(f"mapped file not found: {args.mirror_name}")
    mirrored = mirror_entry(http, entry, args.cdn_host, root)

    print(f"guid: {guid}")
    print(f"version: {version}")
    print(f"api_map: {api_path} entries={len(entries)}")
    print(
        f"mirrored: {mirrored['name']} expected={mirrored['expected_size']} "
        f"actual={mirrored['actual_size']} path={mirrored['path']}"
    )


if __name__ == "__main__":
    main()
