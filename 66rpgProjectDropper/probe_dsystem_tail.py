import argparse
import struct
from pathlib import Path


class Reader:
    def __init__(self, data, pos=0):
        self.data = data
        self.pos = pos

    def i32(self):
        if self.pos + 4 > len(self.data):
            raise ValueError(f"i32 out of bounds at {self.pos}")
        value = struct.unpack_from("<i", self.data, self.pos)[0]
        self.pos += 4
        return value

    def string(self, max_len=4096):
        start = self.pos
        length = self.i32()
        if length < 0 or length > max_len or self.pos + length > len(self.data):
            raise ValueError(f"bad string length {length} at {start}")
        raw = self.data[self.pos : self.pos + length]
        self.pos += length
        return raw.decode("utf-8", errors="replace")


def parse_event(reader):
    start = reader.pos
    code = reader.i32()
    indent = reader.i32()
    argc = reader.i32()
    if argc < 0 or argc > 64:
        raise ValueError(f"bad event argc {argc} at {reader.pos - 4}")
    argv = [reader.string() for _ in range(argc)]
    return {"start": start, "end": reader.pos, "code": code, "indent": indent, "argc": argc, "argv": argv}


def parse_event_list(reader, label):
    count_pos = reader.pos
    count = reader.i32()
    if count < 0 or count > 10000:
        raise ValueError(f"bad {label} count {count} at {count_pos}")
    events = []
    for _ in range(count):
        reader.i32()
        events.append(parse_event(reader))
    return events


def parse_control(reader):
    start = reader.pos
    reader.i32()
    events = parse_event_list(reader, "control.event")
    control_type = reader.i32()
    is_user_string = reader.i32()
    image1 = reader.string()
    image2 = reader.string()
    string_index = reader.i32()
    is_user_var = reader.i32()
    x = reader.i32()
    y = reader.i32()
    is_user_index = reader.i32()
    index = reader.i32()
    max_index = reader.i32()
    color = reader.string()
    return {
        "start": start,
        "end": reader.pos,
        "events": len(events),
        "type": control_type,
        "is_user_string": is_user_string,
        "image1": image1,
        "image2": image2,
        "string_index": string_index,
        "is_user_var": is_user_var,
        "x": x,
        "y": y,
        "is_user_index": is_user_index,
        "index": index,
        "max_index": max_index,
        "color": color,
    }


def parse_custom_ui(reader, no_after_events=False):
    start = reader.pos
    marker = reader.i32()
    load_events = parse_event_list(reader, "loadEvent")
    after_events = [] if no_after_events else parse_event_list(reader, "afterEvent")
    control_count_pos = reader.pos
    control_count = reader.i32()
    if control_count < 0 or control_count > 2000:
        raise ValueError(f"bad controls count {control_count} at {control_count_pos}")
    controls = []
    for control_index in range(control_count):
        try:
            controls.append(parse_control(reader))
        except Exception as exc:
            raise ValueError(
                f"control[{control_index}] failed at {reader.pos}: {exc}"
            ) from exc
    show_effect = reader.i32()
    is_mouse_exit = reader.i32()
    is_key_exit = reader.i32()
    return {
        "start": start,
        "end": reader.pos,
        "marker": marker,
        "load_events": len(load_events),
        "after_events": len(after_events),
        "controls": controls,
        "show_effect": show_effect,
        "is_mouse_exit": is_mouse_exit,
        "is_key_exit": is_key_exit,
    }


def safe(value):
    return repr(value).encode("ascii", "backslashreplace").decode("ascii")


def main():
    parser = argparse.ArgumentParser(description="Probe DSystem tail after the extended button table.")
    parser.add_argument("path")
    parser.add_argument("--tail", type=int, default=48318)
    parser.add_argument("--cui-start", type=int, default=48330)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--no-after-events", action="store_true")
    parser.add_argument("--chain-extra", action="store_true")
    args = parser.parse_args()

    data = Path(args.path).read_bytes()
    tail = Reader(data, args.tail)
    ui_init_save = tail.i32()
    ext_a = tail.i32()
    ext_b = tail.i32()
    ext_c = tail.i32()
    first_cui_load_count = tail.i32()
    print(
        f"tail@{args.tail}: ui_init_save={ui_init_save} "
        f"ext=({ext_a},{ext_b},{ext_c}) first_cui_load_count={first_cui_load_count} "
        f"next={tail.pos}"
    )

    reader = Reader(data, args.cui_start)
    for index in range(args.count):
        try:
            cui = parse_custom_ui(reader, no_after_events=args.no_after_events)
        except Exception as exc:
            print(f"cui[{index}] failed at {reader.pos}: {exc}")
            break
        first_control = cui["controls"][0] if cui["controls"] else None
        first_summary = ""
        if first_control:
            first_summary = (
                f" first_control_type={first_control['type']}"
                f" image1={safe(first_control['image1'])}"
                f" index={first_control['index']}"
            )
        print(
            f"cui[{index}] start={cui['start']} end={cui['end']} marker={cui['marker']} "
            f"load={cui['load_events']} after={cui['after_events']} "
            f"controls={len(cui['controls'])} show={cui['show_effect']} "
            f"mouse={cui['is_mouse_exit']} key={cui['is_key_exit']}{first_summary}"
        )
        if args.chain_extra and index + 1 < args.count:
            extra_pos = reader.pos
            try:
                extra = reader.i32()
            except Exception as exc:
                print(f"chain extra failed at {extra_pos}: {exc}")
                break
            print(f"  chain_extra pos={extra_pos} value={extra} next={reader.pos}")
    print(f"next_pos={reader.pos}")


if __name__ == "__main__":
    main()
