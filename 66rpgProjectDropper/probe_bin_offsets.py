import argparse
import struct
from pathlib import Path


def i32(data, pos, endian="<"):
    if pos < 0 or pos + 4 > len(data):
        return None
    return struct.unpack_from(f"{endian}i", data, pos)[0]


def u32(data, pos, endian="<"):
    if pos < 0 or pos + 4 > len(data):
        return None
    return struct.unpack_from(f"{endian}I", data, pos)[0]


def text_at(data, pos, length):
    if length is None or length < 0 or pos + length > len(data):
        return None
    return data[pos : pos + length].decode("utf-8", errors="replace")


def plausible_text(value):
    if value is None:
        return False
    if len(value) > 300:
        return False
    bad = sum(1 for char in value if ord(char) < 32 and char not in "\r\n\t")
    return bad <= 2


def probe_string(data, pos, label):
    print(f"{label} @ {pos}")
    for shift in range(-4, 9):
        start = pos + shift
        le = u32(data, start, "<")
        be = u32(data, start, ">")
        for endian_name, length in (("le", le), ("be", be)):
            if length is None or length > 512:
                continue
            value = text_at(data, start + 4, length)
            if plausible_text(value):
                print(
                    f"  shift={shift:+d} endian={endian_name} len={length} "
                    f"text={value[:120]!r} next={start + 4 + length}"
                )


def probe_dfilename(data, pos):
    print(f"DFileName candidates @ {pos}")
    layouts = [
        ("tag,from,string", ["i32", "i32", "str"]),
        ("tag,string", ["i32", "str"]),
        ("from,string", ["i32", "str"]),
        ("byte,tag,from,string", ["u8", "i32", "i32", "str"]),
        ("tag,byte,from,string", ["i32", "u8", "i32", "str"]),
        ("tag,from,byte,string", ["i32", "i32", "u8", "str"]),
    ]
    for name, layout in layouts:
        p = pos
        values = []
        ok = True
        for item in layout:
            if item == "i32":
                value = i32(data, p)
                if value is None:
                    ok = False
                    break
                values.append(value)
                p += 4
            elif item == "u8":
                if p >= len(data):
                    ok = False
                    break
                values.append(data[p])
                p += 1
            elif item == "str":
                length = u32(data, p)
                value = text_at(data, p + 4, length)
                if not plausible_text(value):
                    ok = False
                    break
                values.append(f"len={length} text={value!r}")
                p += 4 + length
        if ok:
            print(f"  {name}: values={values} next={p}")


def dump(data, pos, size):
    start = max(0, pos - size)
    end = min(len(data), pos + size)
    print(f"hex {start}:{end}")
    for p in range(start, end, 16):
        chunk = data[p : p + 16]
        ascii_hint = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"  {p:08d}: {chunk.hex(' '):47} {ascii_hint}")


def main():
    parser = argparse.ArgumentParser(description="Probe candidate binary layouts around offsets.")
    parser.add_argument("path")
    parser.add_argument("offsets", nargs="+", type=int)
    parser.add_argument("--dump-size", type=int, default=96)
    args = parser.parse_args()

    data = Path(args.path).read_bytes()
    print(f"path={args.path} size={len(data)}")
    for offset in args.offsets:
        print("")
        dump(data, offset, args.dump_size)
        probe_string(data, offset, "string")
        probe_dfilename(data, offset)


if __name__ == "__main__":
    main()
