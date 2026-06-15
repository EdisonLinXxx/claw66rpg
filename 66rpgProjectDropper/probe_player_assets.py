import argparse
import re
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urljoin

import urllib3


class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("src"):
            self.assets.append(attrs["src"])
        if tag == "link" and attrs.get("href"):
            self.assets.append(attrs["href"])


def fetch_text(http, url):
    response = http.request(
        "GET",
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
            )
        },
        redirect=True,
    )
    return response.status, response.geturl(), response.data.decode("utf-8", errors="replace")


def extract_assets(html, page_url):
    parser = AssetParser()
    parser.feed(html)
    result = []
    for asset in parser.assets:
        if asset.startswith("//"):
            asset = "https:" + asset
        result.append(urljoin(page_url, asset))
    return result


def summarize_game(http, gindex):
    url = f"https://www.66rpg.com/h5/v2/{gindex}"
    status, final_url, html = fetch_text(http, url)
    assets = extract_assets(html, final_url)
    player_assets = [asset for asset in assets if "hfplayer" in asset or "laya." in asset]
    main_assets = [asset for asset in player_assets if "main" in asset.lower()]
    versions = []
    for asset in player_assets:
        match = re.search(r"[?&]v=([^&\\s]+)", asset)
        versions.append(match.group(1).strip() if match else "")
    return {
        "gindex": gindex,
        "status": status,
        "final_url": final_url,
        "title": re.search(r"<title>(.*?)</title>", html, flags=re.I | re.S),
        "asset_count": len(player_assets),
        "main_assets": main_assets,
        "versions": sorted(set(versions)),
        "assets": player_assets,
    }


def main():
    parser = argparse.ArgumentParser(description="Probe 66RPG H5 player asset URLs across game pages.")
    parser.add_argument("gindexes", nargs="+", help="game indexes to probe")
    args = parser.parse_args()

    http = urllib3.PoolManager()
    version_counter = Counter()
    main_counter = Counter()
    for gindex in args.gindexes:
        item = summarize_game(http, gindex)
        title = item["title"].group(1).strip() if item["title"] else ""
        print(f"game={item['gindex']} status={item['status']} title={title}")
        print(f"  final_url={item['final_url']}")
        print(f"  asset_count={item['asset_count']}")
        for version in item["versions"]:
            version_counter[version] += 1
        for main in item["main_assets"]:
            main_counter[main] += 1
            print(f"  main={main.strip()}")
        print(f"  versions={','.join(item['versions'])}")

    print("summary_main_assets:")
    for asset, count in main_counter.most_common():
        print(f"  {count} {asset}")
    print("summary_versions:")
    for version, count in version_counter.most_common():
        print(f"  {count} {version}")


if __name__ == "__main__":
    main()
