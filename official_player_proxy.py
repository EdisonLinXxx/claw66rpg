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
DEFAULT_GINDEX = "1569947"
DEFAULT_CDN_HOSTS = (
    "https://dlcdn1.cgyouxi.com",
    "https://c2.cgyouxi.com",
    "https://c3.cgyouxi.com",
    "https://c4.cgyouxi.com",
)
LOCAL_API_PREFIXES = ("engine/", "PropShop/", "game/", "task/", "pay/", "flower/", "account/", "user/")
DEV_FREE_UNLOCK_AMOUNT = 999999
DEV_FLOWER_AMOUNT = 9999
DEV_FLOWER_COIN_AMOUNT = DEV_FLOWER_AMOUNT * 100
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


def dev_flower_state():
    return {
        "fresh_flower_num": DEV_FLOWER_AMOUNT,
        "wild_flower_num": 0,
        "wild_flower": 0,
        "tanhua_flower_num": DEV_FLOWER_AMOUNT,
        "tanHuaPlayFowerStr": DEV_FLOWER_AMOUNT,
        "flower_num": DEV_FLOWER_AMOUNT,
        "num": DEV_FLOWER_AMOUNT,
        "sum": DEV_FLOWER_AMOUNT,
        "payFlowerNumStr": str(DEV_FLOWER_AMOUNT),
    }


def dev_user_flower_account():
    return {
        "coin1": {"coin_count": DEV_FLOWER_COIN_AMOUNT},
        "coin2": {"coin_count": DEV_FLOWER_COIN_AMOUNT},
        "coin_count": DEV_FLOWER_COIN_AMOUNT,
        "gold_count": DEV_FLOWER_COIN_AMOUNT,
        "flower_count": DEV_FLOWER_AMOUNT,
        "fresh_flower_num": DEV_FLOWER_AMOUNT,
        "wild_flower_num": 0,
        "tanhua_flower_num": DEV_FLOWER_AMOUNT,
        "num": DEV_FLOWER_AMOUNT,
        "sum": DEV_FLOWER_AMOUNT,
    }


def dev_award_payload():
    return {
        "is_receive": 0,
        "is_received": 0,
        "received": 0,
        "can_receive": 1,
        "can_get": 1,
        "status": 1,
        "flower_num": DEV_FLOWER_AMOUNT,
        "need_flower": 0,
        "award_flower": DEV_FLOWER_AMOUNT,
        "coin_count": DEV_FLOWER_COIN_AMOUNT,
        "data": dev_flower_state(),
    }


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
        body_query = self._read_request_query()
        for key, values in body_query.items():
            query.setdefault(key, []).extend(values)
        platform_unlock = self._platform_unlock_enabled(query)
        if platform_unlock and self._is_stub_route(route, platform_unlock):
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
                self._send_bytes(self._map_api_payload(query), "application/json; charset=utf-8")
                return
            platform_unlock = self._platform_unlock_enabled(query)
            if self._is_stub_route(route, platform_unlock):
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
                self._serve_web_bin(web_match.group(1), web_match.group(2), web_match.group(3))
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

    def _read_request_query(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "")
        text = raw.decode("utf-8", errors="replace")
        if "application/json" in content_type:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                return {}
            if isinstance(payload, dict):
                return {str(key): [str(value)] for key, value in payload.items()}
            return {}
        return urllib.parse.parse_qs(text)

    def _is_stub_route(self, route, platform_unlock=None):
        if route.startswith("shareres/"):
            return False
        if route.startswith(LOCAL_API_PREFIXES):
            return True
        if platform_unlock is None:
            platform_unlock = self.server.platform_unlock
        if not platform_unlock:
            return False
        route_lower = route.lower()
        return any(
            keyword in route_lower
            for keyword in ("propshop", "pay", "unlock", "buy", "flower", "accountmoney", "ajax/share", "award", "welfare")
        )

    def _serve_web_bin(self, guid, version, name):
        target = self._game_bundle_dir(guid, version) / name
        if not target.exists():
            target = self.server.downloads / name
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
        platform_unlock = self._platform_unlock_enabled(query)
        route_lower = route.lower()
        amount = DEV_FREE_UNLOCK_AMOUNT if platform_unlock else 0
        goods_id = self._int_param(query, ("goods_id", "goodsId", "goodsid", "item_id", "itemId", "id"), 0)
        buy_num = self._int_param(query, ("buy_num", "buyNum", "buynum", "num", "count"), 1)

        if platform_unlock and "game_flower_by_me" in route_lower:
            payload = {"status": 1, "msg": "local platform flower state", "data": dev_flower_state()}
        elif platform_unlock and "get_flower" in route_lower:
            payload = {"status": 1, "msg": "local platform flower account", "data": dev_user_flower_account()}
        elif platform_unlock and any(
            keyword in route_lower for keyword in ("contains/flower", "share_game", "pay/flower")
        ):
            payload = {"status": 1, "msg": "local platform flower ok", "data": dev_flower_state()}
        elif platform_unlock and any(keyword in route_lower for keyword in ("all_share_award_conf", "share_award_conf")):
            payload = {"status": 1, "msg": "local platform award ok", "data": dev_award_payload()}
        elif "getmyaccountmoney" in route_lower or "accountmoney" in route_lower or "balance" in route_lower:
            if platform_unlock:
                payload = {
                    "status": 1,
                    "data": {
                        "coin_count": DEV_FLOWER_COIN_AMOUNT,
                        "gold_count": DEV_FLOWER_COIN_AMOUNT,
                        "flower_count": DEV_FLOWER_AMOUNT,
                        "diamond_count": DEV_FLOWER_AMOUNT,
                        "acoin": DEV_FLOWER_AMOUNT,
                    },
                }
            else:
                payload = {"status": 1, "data": {"coin_count": 0}}
        elif platform_unlock and "createbuyorder" in route_lower:
            item = self._add_dev_inventory(goods_id, buy_num)
            payload = {
                "status": 1,
                "msg": "local platform unlock",
                "data": {
                    "ok": 1,
                    "success": 1,
                    "is_buy": 1,
                    "is_unlock": 1,
                    "unlock": 1,
                    "goods_id": item["goods_id"] if item else goods_id,
                    "buy_num": buy_num,
                    "using_num": item["using_num"] if item else buy_num,
                    "order_id": "local-platform-unlock",
                },
            }
        elif "getUserHavePropNum" in route:
            if platform_unlock:
                item = self._ensure_dev_inventory(goods_id)
                payload = {"status": 1, "data": [item] if item else self._dev_inventory_array()}
            else:
                payload = {"status": 1, "data": []}
        elif "getUserHaveAllPropNum" in route:
            payload = {"status": 1, "data": self._dev_inventory_array() if platform_unlock else []}
        elif "get_user_hp" in route or "init_user_hp" in route:
            payload = {"status": 1, "data": {"hp": amount, "max_hp": amount}}
        elif "getLimitFreeTime" in route or "getOldLimitFreeTime" in route:
            payload = {"status": 1, "data": {"is_free": 1, "time": 0}}
        elif "get_sys_time" in route:
            payload = {"status": 1, "data": int(__import__("time").time())}
        elif platform_unlock and any(keyword in route_lower for keyword in ("unlock", "buy", "pay", "consume", "charge", "flower", "award")):
            payload = {
                "status": 1,
                "msg": "local platform unlock",
                "data": {"ok": 1, "success": 1, "is_buy": 1, "is_unlock": 1, "unlock": 1, "flower": dev_flower_state()},
            }
        else:
            payload = {"status": 1, "data": []}
        self._send_jsonp(query, payload)

    def _query_flag(self, query, name):
        return any(value in ("1", "true", "True", "yes", "on") for value in query.get(name, []))

    def _query_flag_false(self, query, name):
        return any(value in ("0", "false", "False", "no", "off") for value in query.get(name, []))

    def _cookie_value(self, name):
        cookies = self.headers.get("Cookie", "")
        for part in cookies.split(";"):
            key, _, value = part.strip().partition("=")
            if key == name:
                return urllib.parse.unquote(value)
        return None

    def _query_value(self, query, names, default=""):
        for name in names:
            values = query.get(name)
            if values and values[0]:
                return str(values[0])
        return default

    def _game_context(self, query):
        gindex = self._query_value(query, ("gameId", "gindex"), "") or self._cookie_value("officialProxyGameId") or DEFAULT_GINDEX
        guid = self._query_value(query, ("guid",), "") or self._cookie_value("officialProxyGuid") or DEFAULT_GUID
        version = self._query_value(query, ("version", "ver"), "") or self._cookie_value("officialProxyVersion") or DEFAULT_VERSION
        return str(gindex), str(guid), str(version)

    def _game_bundle_dir(self, guid, version):
        return self.server.downloads / "games" / str(guid) / str(version)

    def _map_path(self, query):
        _, guid, version = self._game_context(query)
        bundled = self._game_bundle_dir(guid, version) / "Map_32.bin"
        if bundled.exists():
            return bundled
        return self.server.downloads / "Map_32.bin"

    def _map_api_payload(self, query):
        map_path = self._map_path(query).resolve()
        cached = self.server.map_payload_cache.get(map_path)
        if cached is None:
            cached = make_api_payload(parse_map_bin(map_path))
            self.server.map_payload_cache[map_path] = cached
        return cached

    def _platform_unlock_enabled(self, query):
        if self._query_flag_false(query, "platformUnlock") or self._query_flag_false(query, "devFreeUnlock"):
            return False
        if self._query_flag(query, "platformUnlock") or self._query_flag(query, "devFreeUnlock"):
            return True
        cookie_value = self._cookie_value("officialProxyPlatformUnlock")
        if cookie_value in ("0", "false", "False", "no", "off"):
            return False
        if cookie_value in ("1", "true", "True", "yes", "on"):
            return True
        return self.server.platform_unlock

    def _int_param(self, query, names, default):
        for name in names:
            for value in query.get(name, []):
                try:
                    return int(value)
                except (TypeError, ValueError):
                    continue
        return default

    def _dev_inventory_array(self):
        return [
            {"goods_id": int(goods_id), "using_num": int(using_num)}
            for goods_id, using_num in sorted(self.server.dev_inventory.items())
            if int(goods_id) > 0
        ]

    def _add_dev_inventory(self, goods_id, buy_num):
        if goods_id <= 0:
            return None
        current = int(self.server.dev_inventory.get(goods_id, 0))
        next_num = current + max(1, int(buy_num or 1))
        self.server.dev_inventory[goods_id] = next_num
        return {"goods_id": goods_id, "using_num": next_num}

    def _ensure_dev_inventory(self, goods_id):
        if goods_id <= 0:
            return None
        if goods_id not in self.server.dev_inventory:
            self.server.dev_inventory[goods_id] = 1
        return {"goods_id": goods_id, "using_num": int(self.server.dev_inventory[goods_id])}

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
    def __init__(self, server_address, handler_class, root, downloads, cdn_hosts, download_missing, download_timeout, platform_unlock):
        super().__init__(server_address, handler_class)
        self.root = root.resolve()
        self.downloads = downloads.resolve()
        self.cdn_hosts = tuple(cdn_hosts)
        self.download_missing = download_missing
        self.download_timeout = download_timeout
        self.platform_unlock = platform_unlock
        self.dev_inventory = {}
        self.map_payload_cache = {}


def main():
    parser = argparse.ArgumentParser(description="Serve the official 66RPG H5 player with local resource/API proxying.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--root", default=".")
    parser.add_argument("--downloads", default=".dry-run-downloads")
    parser.add_argument("--cdn-host", action="append", default=[], help="CDN host used to fill missing /shareres resources.")
    parser.add_argument("--no-download-missing", action="store_true")
    parser.add_argument("--download-timeout", type=float, default=30.0)
    parser.set_defaults(platform_unlock=True)
    parser.add_argument("--platform-unlock", dest="platform_unlock", action="store_true", help="Enable platform entitlement stubs for one-time-paid play.")
    parser.add_argument("--no-platform-unlock", dest="platform_unlock", action="store_false", help="Disable platform entitlement stubs for comparison.")
    parser.add_argument("--dev-free-unlock", dest="platform_unlock", action="store_true", help=argparse.SUPPRESS)
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
        args.platform_unlock,
    )
    print(f"serving official player proxy at http://{args.host}:{args.port}/official_player_proxy.html")
    if args.platform_unlock:
        print(f"platform unlock URL: http://{args.host}:{args.port}/official_player_proxy.html")
    else:
        print(f"platform unlock disabled; compare at http://{args.host}:{args.port}/official_player_proxy.html?platformUnlock=0")
    print(f"root={server.root}")
    default_map = server.downloads / "Map_32.bin"
    default_entries = len(parse_map_bin(default_map)) if default_map.exists() else 0
    print(f"default map={default_map} entries={default_entries}")
    print(f"game bundles={server.downloads / 'games'}")
    server.serve_forever()


if __name__ == "__main__":
    main()
