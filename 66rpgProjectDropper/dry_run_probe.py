import argparse
import hashlib
import json
import os
import re
import struct
from pathlib import Path
from urllib.parse import urlparse

import urllib3


def resolve_guid(http, game_ref):
    game_ref = game_ref.strip()
    if re.fullmatch(r"[0-9a-fA-F]{32}", game_ref):
        return game_ref.lower(), None

    if "66rpg.com" in game_ref:
        path = urlparse(game_ref).path.rstrip("/")
        gindex = path.rsplit("/", 1)[-1]
    elif re.fullmatch(r"\d+", game_ref):
        gindex = game_ref
    else:
        raise ValueError("input must be a 66rpg game URL, gindex, or 32-char guid")

    player_url = f"https://www.66rpg.com/f/{gindex}/ref/d3d3LjY2cnBnLmNvbQ=="
    final_url = http.request("GET", player_url, redirect=True).geturl()
    match = re.search(r"[?&]guid=([0-9a-fA-F]{32})", final_url)
    if not match:
        raise RuntimeError(f"could not resolve guid from redirect: {final_url}")
    return match.group(1).lower(), gindex


def fetch_versions(http, guid):
    url = f"https://www.66rpg.com/api/common/versions?guid={guid}"
    response = http.request("GET", url)
    data = json.loads(response.data.decode("utf-8"))
    if data.get("status") != 1 or not data.get("data"):
        raise RuntimeError(f"versions API failed: {data}")
    return data["data"]


def parse_map_bin(map_bin):
    pairs = []
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
        pairs.append((name, md5, file_size))
    return pairs


def resource_url(md5, cdn_host):
    return f"{cdn_host.rstrip('/')}/shareres/{md5[:2]}/{md5}"


def validate_entries(pairs):
    issues = []
    seen_names = set()
    seen_md5 = set()
    for index, (name, md5, file_size) in enumerate(pairs):
        if not name or "/" not in name:
            issues.append(f"entry {index}: suspicious name {name!r}")
        if not re.fullmatch(r"[0-9a-f]{32}", md5):
            issues.append(f"entry {index}: invalid md5 {md5!r}")
        if file_size < 0:
            issues.append(f"entry {index}: invalid size {file_size}")
        if name in seen_names:
            issues.append(f"entry {index}: duplicate filename {name!r}")
        seen_names.add(name)
        seen_md5.add(md5)
    return {
        "issues": issues,
        "unique_names": len(seen_names),
        "unique_md5": len(seen_md5),
        "total_declared_size": sum(file_size for _, _, file_size in pairs),
    }


def check_head(http, pairs, count, cdn_host):
    results = []
    items = pairs if count < 0 else pairs[:count]
    for name, md5, file_size in items:
        url = resource_url(md5, cdn_host)
        try:
            response = http.request("HEAD", url)
            length = response.headers.get("Content-Length")
            results.append(
                {
                    "name": name,
                    "md5": md5,
                    "expected_size": file_size,
                    "status": response.status,
                    "content_length": int(length) if length and length.isdigit() else None,
                    "url": url,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "name": name,
                    "md5": md5,
                    "expected_size": file_size,
                    "status": "ERROR",
                    "error": str(exc),
                    "url": url,
                }
            )
    return results


def summarize_head_results(results):
    ok = 0
    mismatches = []
    errors = []
    for item in results:
        if item["status"] == 200:
            ok += 1
        else:
            errors.append(item)
        if item.get("content_length") is not None and item["content_length"] != item["expected_size"]:
            mismatches.append(item)
    return ok, mismatches, errors


def download_small(http, pairs, max_files, max_size, cdn_host, output_dir):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for name, md5, file_size in pairs:
        if len(downloaded) >= max_files:
            break
        if file_size > max_size:
            continue
        url = resource_url(md5, cdn_host)
        response = http.request("GET", url)
        target = output_path / name.replace("/", "__")
        target.write_bytes(response.data)
        downloaded.append(
            {
                "name": name,
                "md5": md5,
                "expected_size": file_size,
                "actual_size": len(response.data),
                "status": response.status,
                "path": str(target),
            }
        )
    return downloaded


def download_named(http, pairs, names, cdn_host, output_dir):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    by_name = {name.lower(): (name, md5, file_size) for name, md5, file_size in pairs}
    downloaded = []
    for raw_name in names:
        key = raw_name.strip().lower()
        if not key:
            continue
        item = by_name.get(key)
        if not item:
            downloaded.append({"name": raw_name, "status": "NOT_FOUND"})
            continue
        name, md5, file_size = item
        url = resource_url(md5, cdn_host)
        response = http.request("GET", url)
        target = output_path / name.replace("/", "__")
        target.write_bytes(response.data)
        digest = hashlib.md5(response.data).hexdigest()
        downloaded.append(
            {
                "name": name,
                "md5": md5,
                "expected_size": file_size,
                "actual_size": len(response.data),
                "actual_md5": digest,
                "status": response.status,
                "path": str(target),
            }
        )
    return downloaded


def describe_local_bin(path):
    data = Path(path).read_bytes()
    prefix = data[:64]
    ascii_hint = "".join(chr(b) if 32 <= b < 127 else "." for b in prefix)
    return {
        "path": str(path),
        "size": len(data),
        "md5": hashlib.md5(data).hexdigest(),
        "first_16_hex": prefix[:16].hex(" "),
        "first_64_ascii": ascii_hint,
        "contains_orgdat_at_start": data[:6] == b"ORGDAT",
        "contains_orgdat_near_start": data[:32].find(b"ORGDAT"),
    }


def fetch_bytes(http, url):
    response = http.request("GET", url)
    if response.status != 200:
        raise RuntimeError(f"GET failed {response.status}: {url}")
    return response.data


def h5_fragment_sort_key(item):
    name = item[0].lower()
    if name == "game00.bin":
        return 0
    match = re.fullmatch(r"game(\d+)\.bin", name)
    if match:
        return int(match.group(1))
    return 1_000_000


def concat_h5_fragments(http, mini_pairs, cdn_host, output_dir, order):
    if order == "numeric":
        ordered = sorted(mini_pairs, key=h5_fragment_sort_key)
    elif order == "map":
        ordered = mini_pairs
    else:
        raise ValueError(f"unsupported fragment order: {order}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    target = output_path / f"h5_game_concat_{order}.bin"
    digest = hashlib.md5()
    total = 0
    with target.open("wb") as fp:
        for name, md5, file_size in ordered:
            data = fetch_bytes(http, resource_url(md5, cdn_host))
            digest.update(data)
            fp.write(data)
            total += len(data)
            if len(data) != file_size:
                raise RuntimeError(f"size mismatch for {name}: expected={file_size} actual={len(data)}")
    return {
        "order": order,
        "path": str(target),
        "size": total,
        "md5": digest.hexdigest(),
        "first": ordered[0][0] if ordered else None,
        "last": ordered[-1][0] if ordered else None,
    }


def main():
    parser = argparse.ArgumentParser(description="Dry-run probe for 66rpg public metadata and Map.bin.")
    parser.add_argument("game", help="66rpg game URL, gindex, or guid")
    parser.add_argument("--version", help="specific version; default is latest")
    parser.add_argument("--sample", type=int, default=10, help="number of map entries to print")
    parser.add_argument("--check-head", type=int, default=0, help="HEAD-check the first N mapped resources")
    parser.add_argument("--download-small", type=int, default=0, help="download up to N small mapped resources")
    parser.add_argument("--download-names", default="", help="comma-separated mapped filenames to download")
    parser.add_argument("--max-size", type=int, default=10_000, help="max bytes for --download-small")
    parser.add_argument("--cdn-host", default="https://dlcdn1.cgyouxi.com", help="resource CDN host")
    parser.add_argument("--output-dir", default=".dry-run-downloads", help="directory for small downloads")
    parser.add_argument("--probe-h5", action="store_true", help="probe H5 static Map_32.bin and Game_mini.bin")
    parser.add_argument(
        "--probe-h5-fragments",
        action="store_true",
        help="HEAD-check every Game_mini.bin fragment without downloading fragment bodies",
    )
    parser.add_argument(
        "--concat-h5-fragments",
        action="store_true",
        help="download and concatenate all Game_mini.bin fragments in map and numeric order",
    )
    args = parser.parse_args()

    http = urllib3.PoolManager()
    guid, gindex = resolve_guid(http, args.game)
    versions = fetch_versions(http, guid)
    latest = versions[-1]
    version = str(args.version or latest["version"])
    if gindex is None:
        gindex = str(latest.get("gindex", ""))

    map_url = f"https://wcdn1.cgyouxi.com/web/{guid}/{version}/Map.bin"
    head = http.request("HEAD", map_url)
    map_response = http.request("GET", map_url)
    pairs = parse_map_bin(map_response.data)
    validation = validate_entries(pairs)

    print(f"gindex: {gindex}")
    print(f"guid: {guid}")
    print(f"name: {latest.get('name')}")
    print(f"latest_version: {latest.get('version')}")
    print(f"tested_version: {version}")
    print(f"map_url: {map_url}")
    print(f"map_head_status: {head.status}")
    print(f"map_content_length: {head.headers.get('Content-Length')}")
    print(f"map_entries: {len(pairs)}")
    print(f"unique_names: {validation['unique_names']}")
    print(f"unique_md5: {validation['unique_md5']}")
    print(f"total_declared_size: {validation['total_declared_size']}")
    print(f"validation_issues: {len(validation['issues'])}")
    for issue in validation["issues"][:10]:
        print(f"  issue: {issue}")
    print("sample_entries:")
    for name, md5, file_size in pairs[: args.sample]:
        print(f"  {name} ({file_size} bytes) -> {md5}")

    if args.check_head:
        print(f"head_check: first {args.check_head} resources via {args.cdn_host}")
        head_results = check_head(http, pairs, args.check_head, args.cdn_host)
        ok = 0
        mismatches = []
        for item in head_results:
            if item["status"] == 200:
                ok += 1
            if item.get("content_length") is not None and item["content_length"] != item["expected_size"]:
                mismatches.append(item)
        print(f"head_ok: {ok}/{len(head_results)}")
        print(f"head_size_mismatches: {len(mismatches)}")
        for item in head_results[:10]:
            print(
                f"  {item['status']} {item['name']} expected={item['expected_size']} "
                f"content_length={item.get('content_length')}"
            )

    if args.download_small:
        print(
            f"download_small: up to {args.download_small} files <= {args.max_size} bytes "
            f"into {os.path.abspath(args.output_dir)}"
        )
        downloaded = download_small(
            http,
            pairs,
            args.download_small,
            args.max_size,
            args.cdn_host,
            args.output_dir,
        )
        for item in downloaded:
            print(
                f"  {item['status']} {item['name']} expected={item['expected_size']} "
                f"actual={item['actual_size']} path={item['path']}"
            )

    if args.download_names:
        names = [name.strip() for name in args.download_names.split(",") if name.strip()]
        print(f"download_names: {', '.join(names)} into {os.path.abspath(args.output_dir)}")
        downloaded = download_named(http, pairs, names, args.cdn_host, args.output_dir)
        for item in downloaded:
            if item["status"] == "NOT_FOUND":
                print(f"  NOT_FOUND {item['name']}")
                continue
            print(
                f"  {item['status']} {item['name']} expected={item['expected_size']} "
                f"actual={item['actual_size']} expected_md5={item['md5']} actual_md5={item['actual_md5']} "
                f"path={item['path']}"
            )
            desc = describe_local_bin(item["path"])
            print(f"    first_16_hex: {desc['first_16_hex']}")
            print(f"    first_64_ascii: {desc['first_64_ascii']}")
            print(f"    orgdat_start: {desc['contains_orgdat_at_start']}")
            print(f"    orgdat_offset_near_start: {desc['contains_orgdat_near_start']}")

    if args.probe_h5:
        h5_base = f"{args.cdn_host.rstrip('/')}/web/{guid}/{version}"
        h5_map_url = f"{h5_base}/Map_32.bin"
        game_mini_url = f"{h5_base}/Game_mini.bin"
        print(f"h5_map_url: {h5_map_url}")
        h5_map = fetch_bytes(http, h5_map_url)
        h5_pairs = parse_map_bin(h5_map)
        print(f"h5_map_size: {len(h5_map)}")
        print(f"h5_map_entries: {len(h5_pairs)}")
        print(f"h5_map_first_entry: {h5_pairs[0] if h5_pairs else None}")
        h5_data_game = next((item for item in h5_pairs if item[0].lower() == "data/game.bin"), None)
        print(f"h5_data_game_entry: {h5_data_game}")
        print(f"game_mini_url: {game_mini_url}")
        game_mini = fetch_bytes(http, game_mini_url)
        mini_pairs = parse_map_bin(game_mini)
        print(f"game_mini_size: {len(game_mini)}")
        print(f"game_mini_entries: {len(mini_pairs)}")
        print(f"game_mini_total_declared_size: {sum(size for _, _, size in mini_pairs)}")
        for name, md5, file_size in mini_pairs[:10]:
            print(f"  mini {name} ({file_size} bytes) -> {md5}")
        if args.probe_h5_fragments:
            print(f"h5_fragment_head_check: {len(mini_pairs)} fragments via {args.cdn_host}")
            fragment_results = check_head(http, mini_pairs, -1, args.cdn_host)
            ok, mismatches, errors = summarize_head_results(fragment_results)
            print(f"h5_fragment_head_ok: {ok}/{len(fragment_results)}")
            print(f"h5_fragment_size_mismatches: {len(mismatches)}")
            print(f"h5_fragment_errors: {len(errors)}")
            for item in errors[:10]:
                print(f"  error {item['status']} {item['name']} {item.get('error', '')}")
            for item in mismatches[:10]:
                print(
                    f"  mismatch {item['name']} expected={item['expected_size']} "
                    f"content_length={item.get('content_length')}"
                )
        if args.concat_h5_fragments:
            print(f"h5_fragment_concat: {len(mini_pairs)} fragments into {os.path.abspath(args.output_dir)}")
            for order in ("map", "numeric"):
                result = concat_h5_fragments(http, mini_pairs, args.cdn_host, args.output_dir, order)
                matches_h5_game = bool(h5_data_game and result["md5"] == h5_data_game[1])
                print(
                    f"  order={result['order']} size={result['size']} md5={result['md5']} "
                    f"matches_h5_data_game={matches_h5_game} first={result['first']} last={result['last']} "
                    f"path={result['path']}"
                )
                desc = describe_local_bin(result["path"])
                print(f"    first_16_hex: {desc['first_16_hex']}")
                print(f"    first_64_ascii: {desc['first_64_ascii']}")
                print(f"    orgdat_start: {desc['contains_orgdat_at_start']}")


if __name__ == "__main__":
    main()
