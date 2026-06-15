import argparse
import struct
from pathlib import Path


def u8(data, pos):
    return data[pos] if 0 <= pos < len(data) else None


def i32(data, pos):
    if pos < 0 or pos + 4 > len(data):
        raise ValueError("out of bounds")
    return struct.unpack_from("<i", data, pos)[0]


def read_string(data, pos, max_len=512):
    length = i32(data, pos)
    if length < 0 or length > max_len or pos + 4 + length > len(data):
        raise ValueError(f"bad string length {length} at {pos}")
    raw = data[pos + 4 : pos + 4 + length]
    return raw.decode("utf-8", errors="replace"), pos + 4 + length


def read_dfilename(data, pos):
    marker = i32(data, pos)
    from_value = i32(data, pos + 4)
    name, next_pos = read_string(data, pos + 8)
    return {"marker": marker, "from": from_value, "name": name}, next_pos


def should_skip_pad(data, pos):
    if u8(data, pos) != 0:
        return False
    try:
        current = i32(data, pos)
        shifted = i32(data, pos + 1)
    except ValueError:
        return False
    return current % 256 == 0 and 0 < shifted < 10000


def read_button(data, pos):
    skipped = False
    if should_skip_pad(data, pos):
        pos += 1
        skipped = True
    start = pos
    marker = i32(data, pos)
    name, pos = read_string(data, pos + 4)
    image1, pos = read_dfilename(data, pos)
    image2, pos = read_dfilename(data, pos)
    x = i32(data, pos)
    y = i32(data, pos + 4)
    pos += 8
    return {
        "start": start,
        "end": pos,
        "skipped_pad": skipped,
        "marker": marker,
        "name": name,
        "image1": image1,
        "image2": image2,
        "x": x,
        "y": y,
    }


def safe(value):
    return repr(value).encode("ascii", "backslashreplace").decode("ascii")


def main():
    parser = argparse.ArgumentParser(description="Parse consecutive DSystem DButton records from a game bin.")
    parser.add_argument("path")
    parser.add_argument("--start", type=int, default=9950)
    parser.add_argument("--max", type=int, default=140)
    args = parser.parse_args()

    data = Path(args.path).read_bytes()
    pos = args.start
    for index in range(args.max):
        try:
            button = read_button(data, pos)
        except Exception as exc:
            print(f"stop index={index} pos={pos} error={exc}")
            break
        print(
            f"{index:03d} start={button['start']} end={button['end']} pad={button['skipped_pad']} "
            f"marker={button['marker']} name={safe(button['name'])} "
            f"img1={safe(button['image1']['name'])} img2={safe(button['image2']['name'])} "
            f"x={button['x']} y={button['y']}"
        )
        pos = button["end"]
    print(f"next_pos={pos}")
    for probe in range(pos, min(pos + 32, len(data)), 4):
        print(f"  {probe}: {data[probe:probe+4].hex(' ')} i32={i32(data, probe)}")


if __name__ == "__main__":
    main()
