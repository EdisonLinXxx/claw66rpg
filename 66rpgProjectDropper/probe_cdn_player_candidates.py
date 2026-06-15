import argparse
import hashlib
from urllib.parse import urljoin

import urllib3


PATHS = [
    "website/hfplayer/v1/bin/main.min.js",
    "website/hfplayer/v1/bin/main.js",
    "website/hfplayer/v2/bin/main.min.js",
    "website/hfplayer/v2/bin/main.js",
    "website/hfplayer/v2/bin/main-debug.js",
    "website/hfplayer/v2/bin/main.min.debug.js",
    "website/hfplayer/v2/bin/js/main.min.js",
    "website/hfplayer/v2/bin/js/main.js",
    "website/hfplayer/v2/bin/js/lib/LibClass.js",
    "website/hfplayer/v2/bin/js/lib/LibClass.min.js",
    "website/hfplayer/v2/common/Common.js",
    "website/hfplayer/v2/common/Login.js",
    "website/hfplayer/v3/bin/main.min.js",
    "website/hfplayer/v3/bin/main.js",
    "website/hfplayer/bin/main.min.js",
    "website/hfplayer/bin/main.js",
]


HOSTS = [
    "https://c1.cgyouxi.com/",
    "https://c2.cgyouxi.com/",
    "https://c3.cgyouxi.com/",
    "https://c4.cgyouxi.com/",
]


def main():
    parser = argparse.ArgumentParser(description="Probe common 66RPG player CDN candidate paths.")
    parser.add_argument("--download", action="store_true", help="GET successful JS candidates and print md5")
    args = parser.parse_args()

    http = urllib3.PoolManager()
    seen = set()
    for host in HOSTS:
        for path in PATHS:
            url = urljoin(host, path)
            if url in seen:
                continue
            seen.add(url)
            try:
                response = http.request(
                    "GET" if args.download else "HEAD",
                    url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    redirect=True,
                    timeout=urllib3.Timeout(connect=10.0, read=30.0),
                )
                length = response.headers.get("Content-Length", "")
                ctype = response.headers.get("Content-Type", "")
                digest = ""
                if args.download and response.status == 200:
                    digest = hashlib.md5(response.data).hexdigest()
                    length = str(len(response.data))
                print(f"{response.status} len={length} md5={digest} type={ctype} {url}")
            except Exception as exc:
                print(f"ERROR {type(exc).__name__}: {exc} {url}")


if __name__ == "__main__":
    main()
