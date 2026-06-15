import argparse
import struct
from pathlib import Path


def i32(data, pos):
    if pos < 0 or pos + 4 > len(data):
        return None
    return struct.unpack_from("<i", data, pos)[0]


def plausible_string(data, pos, max_len=512):
    length = i32(data, pos)
    if length is None or length < 0 or length > max_len:
        return None
    end = pos + 4 + length
    if end > len(data):
        return None
    raw = data[pos + 4 : end]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    control = sum(1 for char in text if ord(char) < 32 and char not in "\r\n\t")
    if control:
        return None
    return length, text, end


def safe(text):
    return repr(text).encode("ascii", "backslashreplace").decode("ascii")


def main():
    parser = argparse.ArgumentParser(description="Print a loose int/string token stream from a binary region.")
    parser.add_argument("path")
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--strings-first", action="store_true")
    args = parser.parse_args()

    data = Path(args.path).read_bytes()
    pos = args.start
    while pos < min(args.end, len(data)):
        string = plausible_string(data, pos)
        if args.strings_first and string:
            length, text, next_pos = string
            print(f"{pos}: str len={length} text={safe(text)} next={next_pos}")
            pos = next_pos
            continue
        value = i32(data, pos)
        if value is None:
            break
        string_hint = plausible_string(data, pos)
        hint = ""
        if string_hint:
            length, text, next_pos = string_hint
            hint = f" | str len={length} text={safe(text)} next={next_pos}"
        print(f"{pos}: i32={value}{hint}")
        pos += 4


if __name__ == "__main__":
    main()
