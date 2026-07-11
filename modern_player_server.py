import argparse
import json
import mimetypes
import re
import struct
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


SHARERES_RE = re.compile(r"^shareres/([0-9a-fA-F]{2})/([0-9a-fA-F]{32}(?:\.[A-Za-z0-9]+)?)$")
WEB_BIN_RE = re.compile(r"^web/([0-9a-fA-F]{32})/([^/]+)/(Map_32\.bin|Game_mini\.bin)$")
MODERN_ROUTE_RE = re.compile(r"^modern/(\d+)$")
CALLBACK_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_.$]*$")


def safe_join(root, relative):
    target = (root / relative).resolve()
    root = root.resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"path escapes root: {relative}")
    return target


def parse_map_bin(path):
    data = path.read_bytes()
    entries = []
    offset = 4
    while offset + 4 <= len(data):
        name_length = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if name_length <= 0 or offset + name_length + 8 > len(data):
            break
        name = data[offset : offset + name_length].decode("utf-8", errors="replace")
        offset += name_length
        file_size = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        hash_length = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if hash_length <= 0 or offset + hash_length > len(data):
            break
        resource_hash = data[offset : offset + hash_length].decode("ascii", errors="replace")
        offset += hash_length
        entries.append([name, file_size, resource_hash, ""])
    return entries


class ModernPlayerHandler(SimpleHTTPRequestHandler):
    server_version = "Modern66RPGPlayer/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(args[2].root), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def _dispatch(self, method):
        request_target = self.path
        if request_target.startswith("//"):
            request_target = "/" + request_target.lstrip("/")
        parsed = urllib.parse.urlsplit(request_target)
        route = urllib.parse.unquote(parsed.path).lstrip("/")
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if not route or route == "modern_player.html" or MODERN_ROUTE_RE.match(route):
                self._serve_file(self.server.root / "modern_player.html", "text/html; charset=utf-8")
                return
            if route == "modern_player_boot.js":
                self._serve_file(self.server.root / "modern_player_boot.js", "application/javascript; charset=utf-8")
                return
            if route == "player_render_refresh.js":
                self._serve_file(self.server.root / "player_render_refresh.js", "application/javascript; charset=utf-8")
                return
            if route == "player_audio_bridge.js":
                self._serve_file(self.server.root / "player_audio_bridge.js", "application/javascript; charset=utf-8")
                return
            if route == "api/oapi_map.php":
                self._serve_map(query)
                return
            web_match = WEB_BIN_RE.match(route)
            if web_match:
                guid, version, name = web_match.groups()
                self._serve_file(self._bundle_dir(guid, version) / name, "application/octet-stream")
                return
            if SHARERES_RE.match(route):
                self._serve_resource(route)
                return
            if route.startswith("res/"):
                self.send_response(302)
                self.send_header(
                    "Location",
                    "https://c2.cgyouxi.com/website/hfplayer/v2/bin/" + urllib.parse.quote(route, safe="/._-?=&"),
                )
                self.end_headers()
                return
            if route == "favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            if self._is_local_api(route):
                body = self._read_body() if method == "POST" else {}
                self._serve_api(route, query, body)
                return
            self.send_error(404, "Not found")
        except (OSError, ValueError, urllib.error.URLError) as error:
            self.log_error("route failed %s: %s", route, error)
            self.send_error(502, str(error))

    def _bundle_dir(self, guid, version):
        return self.server.downloads / "games" / str(guid) / str(version)

    def _serve_map(self, query):
        guid = self._query_value(query, "guid")
        version = self._query_value(query, "version")
        if not re.fullmatch(r"[0-9a-fA-F]{32}", guid or "") or not re.fullmatch(r"[^/]+", version or ""):
            self._send_json({"status": -1, "msg": "invalid guid or version", "data": []}, query)
            return
        map_path = self._bundle_dir(guid, version) / "Map_32.bin"
        cache_key = map_path.resolve()
        payload = self.server.map_cache.get(cache_key)
        if payload is None:
            payload = {"status": 1, "msg": "local modern player map", "data": parse_map_bin(map_path)}
            self.server.map_cache[cache_key] = payload
        self._send_json(payload, query)

    def _serve_resource(self, route):
        target = safe_join(self.server.root, route)
        if not target.exists():
            self._download_resource(route, target)
        self._serve_file(target, mimetypes.guess_type(target.name)[0] or "application/octet-stream")

    def _download_resource(self, route, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        url = self.server.cdn_host.rstrip("/") + "/" + route
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 Modern66RPGPlayer/1.0", "Referer": "https://www.66rpg.com/"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                temp_path = Path(stream.name)
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    stream.write(chunk)
        temp_path.replace(target)

    def _serve_file(self, target, content_type):
        if not target.is_file():
            self.send_error(404, "File not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(target.stat().st_size))
        self.end_headers()
        with target.open("rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def _is_local_api(self, route):
        prefixes = (
            "HpSys/",
            "PropShop/",
            "cloud/",
            "collect/",
            "report/",
            "investigate/",
            "ajax/",
            "api/",
        )
        return route.startswith(prefixes)

    def _serve_api(self, route, query, body):
        now = int(time.time())
        if route.endswith("getMyAccountMoney"):
            payload = {
                "status": 1,
                "data": {
                    "coin_count": 999900,
                    "flower_count": 9999,
                    "light_count": 9999,
                },
            }
        elif route.endswith("getUserHaveAllPropNum"):
            payload = {"status": 1, "data": self._inventory_items(query, body)}
        elif route.endswith("getUserHavePropNum"):
            goods_id = self._request_int(query, body, "goods_id")
            items = self._inventory_items(query, body)
            payload = {
                "status": 1,
                "data": [item for item in items if item["goods_id"] == goods_id],
            }
        elif "createBuyOrder" in route:
            goods_id = self._request_int(query, body, "goods_id")
            buy_num = max(1, self._request_int(query, body, "buy_num", 1))
            if goods_id <= 0:
                payload = {"status": 0, "msg": "invalid goods_id", "data": {}}
            else:
                using_num = self._add_inventory_item(query, body, goods_id, buy_num)
                payload = {
                    "status": 1,
                    "data": {
                        "is_buy": 1,
                        "order_status": 1,
                        "order_id": f"local-{int(time.time() * 1000)}",
                        "goods_id": goods_id,
                        "buy_num": buy_num,
                        "using_num": using_num,
                    },
                }
        elif route.endswith("init_user_hp") or route.endswith("get_user_hp") or route.endswith("get_user_hp_v2"):
            payload = {"status": 1, "data": {"hp": 9999, "user_hp": 9999, "max_hp": 9999}}
        elif route.endswith("un_lock"):
            payload = {"status": 1, "data": {"is_unlock": 1}}
        elif route.endswith("get_sys_time") or route == "api/tool":
            payload = {"status": 1, "data": {"timestramp": now, "server_time": now}}
        elif route.endswith("getLimitFreeTime") or route.endswith("getOldLimitFreeTime"):
            payload = {"status": 1, "data": {"is_free": 1, "start_time": 0, "end_time": now + 31536000}}
        elif route.endswith("get_status"):
            payload = {"status": 1, "data": {"status": 0}}
        elif route.endswith("cloud_flag"):
            payload = {"status": 1, "data": True}
        elif route.endswith("cloud_save_ex"):
            # Extended variables and main progress are independent stores in
            # the official player API; mixing them corrupts resume payloads.
            namespace = "vars-" + str(body.get("varsType") or "normal")
            self._save_cloud_value(query, body, namespace, str(body.get("varsEx") or ""))
            payload = {"status": 1, "data": {"saved": 1}}
        elif route.endswith("cloud_load_ex"):
            namespace = "vars-" + str(body.get("varsType") or "normal")
            payload = {"status": 1, "data": self._load_cloud_value(query, body, namespace, "")}
        elif route.endswith("cloud_save"):
            self._save_cloud_value(query, body, "saves", str(body.get("content") or ""))
            payload = {"status": 1, "data": {"saved": 1}}
        elif route.endswith("cloud_load"):
            payload = {"status": 1, "data": self._load_cloud_value(query, body, "saves", "")}
        elif route.endswith("get_game_info.json"):
            payload = {
                "status": 1,
                "data": {
                    "game": {
                        "gindex": self._query_value(query, "gindex") or "1692579",
                        "gname": "挂件丨破茧✿校园豪门养成",
                        "author_uid": 0,
                    }
                },
            }
        elif route.endswith("get_game_link.json"):
            payload = {"status": 1, "data": {"ending_info": [], "friendly_link": []}}
        elif route.endswith("comments.json") or route.endswith("fine_comments.json"):
            payload = {"status": 1, "data": {"comments": []}}
        else:
            payload = {"status": 1, "data": {}}
        self._send_json(payload, query)

    def _cloud_key(self, query, body, namespace):
        merged = {}
        merged.update({key: values[-1] for key, values in query.items() if values})
        merged.update(body)
        game = str(merged.get("gindex") or merged.get("gameId") or "1692579")
        user = str(merged.get("uid") or "local-player")
        return re.sub(r"[^A-Za-z0-9_.-]", "_", f"{game}-{user}-{namespace}")

    def _save_cloud_value(self, query, body, namespace, value):
        key = self._cloud_key(query, body, namespace)
        self.server.data_dir.mkdir(parents=True, exist_ok=True)
        target = self.server.data_dir / f"{key}.json"
        temp = target.with_suffix(".json.tmp")
        temp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        temp.replace(target)

    def _load_cloud_value(self, query, body, namespace, default):
        target = self.server.data_dir / f"{self._cloud_key(query, body, namespace)}.json"
        if not target.is_file():
            return default
        return json.loads(target.read_text(encoding="utf-8"))

    def _inventory_items(self, query, body):
        with self.server.inventory_lock:
            inventory = self._load_cloud_value(query, body, "inventory", {})
        if not isinstance(inventory, dict):
            return []
        return [
            {"goods_id": int(goods_id), "using_num": int(count), "goods_num": int(count)}
            for goods_id, count in sorted(inventory.items(), key=lambda item: int(item[0]))
            if int(count) > 0
        ]

    def _add_inventory_item(self, query, body, goods_id, buy_num):
        with self.server.inventory_lock:
            inventory = self._load_cloud_value(query, body, "inventory", {})
            if not isinstance(inventory, dict):
                inventory = {}
            key = str(goods_id)
            inventory[key] = int(inventory.get(key, 0)) + buy_num
            self._save_cloud_value(query, body, "inventory", inventory)
            return inventory[key]

    @staticmethod
    def _request_int(query, body, name, default=0):
        value = body.get(name)
        if value in (None, ""):
            values = query.get(name)
            value = values[-1] if values else default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _read_body(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        content_type = self.headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return {}
        parsed = urllib.parse.parse_qs(raw.decode("utf-8", errors="replace"))
        return {key: values[-1] for key, values in parsed.items() if values}

    def _send_json(self, payload, query):
        callback = self._query_value(query, "jsonCallBack") or self._query_value(query, "callback")
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if callback and CALLBACK_RE.fullmatch(callback):
            content = f"{callback}({text});".encode("utf-8")
            content_type = "application/javascript; charset=utf-8"
        else:
            content = text.encode("utf-8")
            content_type = "application/json; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    @staticmethod
    def _query_value(query, name):
        values = query.get(name)
        return values[-1] if values else ""


class ModernPlayerServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, root, downloads, data_dir, cdn_host):
        super().__init__(address, ModernPlayerHandler)
        self.root = root.resolve()
        self.downloads = downloads.resolve()
        self.data_dir = data_dir.resolve()
        self.cdn_host = cdn_host
        self.map_cache = {}
        self.inventory_lock = threading.Lock()


def main():
    parser = argparse.ArgumentParser(description="Serve the independent modern 66RPG local player.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--root", default=".")
    parser.add_argument("--downloads", default=".dry-run-downloads")
    parser.add_argument("--data-dir", default=".modern-player-data")
    parser.add_argument("--cdn-host", default="https://dlcdn1.cgyouxi.com")
    args = parser.parse_args()

    root = Path(args.root)
    server = ModernPlayerServer(
        (args.host, args.port),
        root,
        root / args.downloads,
        root / args.data_dir,
        args.cdn_host,
    )
    print(f"modern player: http://{args.host}:{args.port}/modern/1692579", flush=True)
    print(f"root={server.root}", flush=True)
    print(f"downloads={server.downloads}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
