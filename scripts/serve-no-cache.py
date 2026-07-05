from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import os


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description="Serve the runner locally with no-cache headers.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    os.chdir(Path(args.root).resolve())
    httpd = ThreadingHTTPServer((args.host, args.port), NoCacheHandler)
    print(f"serving {Path.cwd()} at http://{args.host}:{args.port}/")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
