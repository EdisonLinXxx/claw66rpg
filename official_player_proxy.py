import argparse
import json
import mimetypes
import re
import shutil
import struct
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


DEFAULT_GUID = "0a235c54f16c431ab5736c92997edb47"
DEFAULT_VERSION = "364"
DEFAULT_CDN_HOSTS = (
    "https://dlcdn1.cgyouxi.com",
    "https://c2.cgyouxi.com",
    "https://c3.cgyouxi.com",
    "https://c4.cgyouxi.com",
)
LOCAL_API_PREFIXES = ("engine/", "PropShop/", "game/", "task/", "pay/", "flower/", "account/", "user/")
DEV_FREE_UNLOCK_AMOUNT = 999999
TRANSPARENT_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6360000002000150a0f64500000000"
    "49454e44ae426082"
)

SHARERES_RE = re.compile(r"^shareres/([0-9a-fA-F]{2})/([0-9a-fA-F]{32}(?:\.[A-Za-z0-9]+)?)$")
WEB_BIN_RE = re.compile(r"^web/([0-9a-fA-F]{32})/([^/]+)/(Map(?:_32)?\.bin|Game_mini\.bin)$")


def parse_map_bin(path):
    data = path.read_bytes()
    offset = 4
    entries = []
    total = len(data)
    while offset + 4 <= total:
        name_len = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if name_len <= 0 or offset + name_len + 8 > total:
            break

        name = data[offset : offset + name_len].decode("utf-8", errors="replace")
        offset += name_len

        file_size = struct.unpack_from("<I", data, offset)[0]
        offset += 4

        md5_len = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if md5_len <= 0 or offset + md5_len > total:
            break

        md5 = data[offset : offset + md5_len].decode("ascii", errors="replace")
        offset += md5_len
        entries.append([name, file_size, md5, ""])
    return entries


def make_api_payload(entries):
    return json.dumps(
        {"status": 1, "msg": "official player local proxy", "data": entries},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def safe_join(root, relative):
    target = (root / relative).resolve()
    root = root.resolve()
    if root == target or root in target.parents:
        return target
    raise ValueError(f"path escapes root: {relative}")


class OfficialPlayerProxyHandler(SimpleHTTPRequestHandler):
    server_version = "OfficialPlayerProxy/1.0"

    def __init__(self, *args, directory=None, **kwargs):
        server = args[2] if len(args) >= 3 else None
        root = getattr(server, "root", Path.cwd())
        super().__init__(*args, directory=str(root), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        route = urllib.parse.unquote(parsed.path).lstrip("/")
        query = urllib.parse.parse_qs(parsed.query)
        route, query = self._normalize_absolute_route(route, query)
        if (self.server.dev_free_unlock or self._query_flag(query, "devFreeUnlock")) and self._is_stub_route(route):
            self._send_stub(route, query)
            return
        self._send_json({"status": 1, "msg": "ok", "data": {}})

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        route = urllib.parse.unquote(parsed.path).lstrip("/")
        query = urllib.parse.parse_qs(parsed.query)
        route, query = self._normalize_absolute_route(route, query)

        try:
            if route in ("favicon.ico", "null path"):
                self._send_bytes(TRANSPARENT_PNG, "image/png")
                return
            if route == "api/oapi_map.php":
                self._send_bytes(self.server.map_api_payload, "application/json; charset=utf-8")
                return
            if self._is_stub_route(route):
                self._send_stub(route, query)
                return
            if "ajax/LightText/get_status" in route:
                self._send_jsonp(
                    query,
                    {"status": 1, "msg": "local light text bypass", "data": {"type": 0, "expire_time": 0, "head_msg": "", "md5": ""}},
                )
                return
            if route.endswith("ad/new_get_game_ad_list.json"):
                self._send_jsonp(query, {"status": 0, "msg": "no local ad", "data": {}})
                return
            if "investigate/get_investigate_image" in route:
                self._send_jsonp(query, {"status": 0, "msg": "no local investigate image", "data": {}})
                return

            web_match = WEB_BIN_RE.match(route)
            if web_match:
                self._serve_web_bin(web_match.group(3))
                return

            if SHARERES_RE.match(route):
                self._serve_shareres(route)
                return
        except Exception as error:
            self.log_error("proxy route failed for %s: %s", route, error)
            self.send_error(502, str(error))
            return

        super().do_GET()

    def _normalize_absolute_route(self, route, query):
        if route.startswith("http://") or route.startswith("https://"):
            parsed = urllib.parse.urlparse(route)
            normalized = parsed.path.lstrip("/")
            merged_query = urllib.parse.parse_qs(parsed.query)
            merged_query.update(query)
            return normalized, merged_query
        return route, query

    def _is_stub_route(self, route):
        if route.startswith(LOCAL_API_PREFIXES):
            return True
        if not self.server.dev_free_unlock:
            return False
        route_lower = route.lower()
        return any(keyword in route_lower for keyword in ("propshop", "pay", "unlock", "buy", "flower", "accountmoney"))

    def _serve_web_bin(self, name):
        if name == "Game_mini.bin":
            target = self.server.downloads / "Game_mini.bin"
        else:
            target = self.server.downloads / "Map_32.bin"
        self._serve_file(target, "application/octet-stream")

    def _serve_shareres(self, route):
        target = safe_join(self.server.root, route)
        if not target.exists() and self.server.download_missing:
            self._download_shareres(route, target)
        self._serve_file(target, self._guess_type(target))

    def _download_shareres(self, route, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        last_error = None
        for host in self.server.cdn_hosts:
            url = f"{host.rstrip('/')}/{route}"
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 OfficialPlayerProxy/1.0",
                        "Referer": "https://www.66rpg.com/",
                    },
                )
                with urllib.request.urlopen(req, timeout=self.server.download_timeout) as response:
                    with tempfile.NamedTemporaryFile(delete=False, dir=str(target.parent)) as tmp:
                        shutil.copyfileobj(response, tmp)
                        tmp_path = Path(tmp.name)
                tmp_path.replace(target)
                self.log_message("cached %s from %s", route, url)
                return
            except (OSError, urllib.error.URLError, urllib.error.HTTPError) as error:
                last_error = error
        raise FileNotFoundError(f"resource unavailable: {route}; last_error={last_error}")

    def _serve_file(self, target, content_type):
        if not target.exists() or not target.is_file():
            self.send_error(404, "File not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(target.stat().st_size))
        self.end_headers()
        with target.open("rb") as source:
            shutil.copyfileobj(source, self.wfile)

    def _send_stub(self, route, query):
        dev_free_unlock = self.server.dev_free_unlock or self._query_flag(query, "devFreeUnlock")
        route_lower = route.lower()
        amount = DEV_FREE_UNLOCK_AMOUNT if dev_free_unlock else 0

        if "getMyAccountMoney" in route or "accountmoney" in route_lower or "balance" in route_lower:
            if dev_free_unlock:
                payload = {
                    "status": 1,
                    "data": {
                        "coin_count": amount,
                        "gold_count": amount,
                        "flower_count": amount,
                        "diamond_count": amount,
                        "acoin": amount,
                    },
                }
            else:
                payload = {"status": 1, "data": {"coin_count": 0}}
        elif "getUserHavePropNum" in route:
            if dev_free_unlock:
                payload = {"status": 1, "data": {"num": amount, "count": amount, "prop_num": amount}}
            else:
                payload = {"status": 1, "data": []}
        elif "getUserHaveAllPropNum" in route:
            payload = {"status": 1, "data": []}
        elif "get_user_hp" in route or "init_user_hp" in route:
            payload = {"status": 1, "data": {"hp": amount, "max_hp": amount}}
        elif "getLimitFreeTime" in route or "getOldLimitFreeTime" in route:
            payload = {"status": 1, "data": {"is_free": 1, "time": 0}}
        elif "get_sys_time" in route:
            payload = {"status": 1, "data": int(__import__("time").time())}
        elif dev_free_unlock and any(keyword in route_lower for keyword in ("unlock", "buy", "pay", "consume", "charge", "flower")):
            payload = {
                "status": 1,
                "msg": "local dev free unlock",
                "data": {"ok": 1, "success": 1, "is_buy": 1, "is_unlock": 1, "unlock": 1},
            }
        else:
            payload = {"status": 1, "data": []}
        self._send_jsonp(query, payload)

    def _query_flag(self, query, name):
        return any(value in ("1", "true", "True", "yes", "on") for value in query.get(name, []))

    def _send_jsonp(self, query, payload):
        callback = ""
        for key in ("jsonCallBack", "callback", "cb"):
            values = query.get(key)
            if values:
                callback = values[0]
                break
        if callback:
            body = f"{callback}({json.dumps(payload, ensure_ascii=False)});".encode("utf-8")
            self._send_bytes(body, "application/javascript; charset=utf-8")
        else:
            self._send_json(payload)

    def _send_json(self, payload):
        self._send_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _send_bytes(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _guess_type(self, target):
        guessed, _ = mimetypes.guess_type(str(target))
        return guessed or "application/octet-stream"


class OfficialPlayerProxyServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler_class, root, downloads, cdn_hosts, download_missing, download_timeout, dev_free_unlock):
        super().__init__(server_address, handler_class)
        self.root = root.resolve()
        self.downloads = downloads.resolve()
        self.cdn_hosts = tuple(cdn_hosts)
        self.download_missing = download_missing
        self.download_timeout = download_timeout
        self.dev_free_unlock = dev_free_unlock
        self.map_path = self.downloads / "Map_32.bin"
        self.map_entries = parse_map_bin(self.map_path)
        self.map_api_payload = make_api_payload(self.map_entries)


def main():
    parser = argparse.ArgumentParser(description="Serve the official 66RPG H5 player with local resource/API proxying.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--root", default=".")
    parser.add_argument("--downloads", default=".dry-run-downloads")
    parser.add_argument("--cdn-host", action="append", default=[], help="CDN host used to fill missing /shareres resources.")
    parser.add_argument("--no-download-missing", action="store_true")
    parser.add_argument("--download-timeout", type=float, default=30.0)
    parser.add_argument("--dev-free-unlock", action="store_true", help="Enable local-only developer stubs for paid unlock flows.")
    args = parser.parse_args()

    root = Path(args.root)
    downloads = root / args.downloads
    cdn_hosts = args.cdn_host or DEFAULT_CDN_HOSTS

    server = OfficialPlayerProxyServer(
        (args.host, args.port),
        OfficialPlayerProxyHandler,
        root,
        downloads,
        cdn_hosts,
        not args.no_download_missing,
        args.download_timeout,
        args.dev_free_unlock,
    )
    print(f"serving official player proxy at http://{args.host}:{args.port}/official_player_proxy.html")
    if args.dev_free_unlock:
        print(f"dev free unlock URL: http://{args.host}:{args.port}/official_player_proxy.html?devFreeUnlock=1")
    print(f"root={server.root}")
    print(f"map={server.map_path} entries={len(server.map_entries)}")
    server.serve_forever()


if __name__ == "__main__":
    main()
