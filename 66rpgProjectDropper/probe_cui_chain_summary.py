import argparse
from collections import Counter
from importlib.machinery import SourceFileLoader
from pathlib import Path


tail_probe = SourceFileLoader(
    "probe_dsystem_tail",
    str(Path(__file__).with_name("probe_dsystem_tail.py")),
).load_module()


def safe(value):
    return repr(value).encode("ascii", "backslashreplace").decode("ascii")


def main():
    parser = argparse.ArgumentParser(description="Summarize chained newer Custom UI blocks.")
    parser.add_argument("path")
    parser.add_argument("--start", type=int, default=48330)
    parser.add_argument("--max", type=int, default=3000)
    parser.add_argument("--sample-every", type=int, default=250)
    parser.add_argument("--stop-empty-run", type=int, default=0)
    args = parser.parse_args()

    data = Path(args.path).read_bytes()
    reader = tail_probe.Reader(data, args.start)
    empty_run = 0
    first_empty = None
    last_non_empty = None
    extras = Counter()
    control_counts = Counter()

    for index in range(args.max):
        start = reader.pos
        try:
            cui = tail_probe.parse_custom_ui(reader, no_after_events=True)
        except Exception as exc:
            print(f"stop index={index} pos={reader.pos} error={exc}")
            break

        first_control = cui["controls"][0] if cui["controls"] else None
        first_image = first_control["image1"] if first_control else ""
        is_empty = (
            cui["load_events"] == 0
            and len(cui["controls"]) == 0
            and cui["show_effect"] == 0
            and cui["is_mouse_exit"] == 1
            and cui["is_key_exit"] == 1
        )
        if is_empty:
            empty_run += 1
            if first_empty is None:
                first_empty = index
        else:
            empty_run = 0
            last_non_empty = index

        extra = None
        extra_pos = reader.pos
        if index + 1 < args.max:
            try:
                extra = reader.i32()
                extras[extra] += 1
            except Exception as exc:
                print(f"extra stop index={index} pos={extra_pos} error={exc}")
                break

        control_counts[len(cui["controls"])] += 1
        should_print = (
            index < 20
            or index % args.sample_every == 0
            or (first_empty is not None and first_empty <= index < first_empty + 10)
            or (args.stop_empty_run and empty_run >= args.stop_empty_run)
        )
        if should_print:
            print(
                f"{index:04d} start={start} end={reader.pos if extra is not None else cui['end']} "
                f"extra={extra} load={cui['load_events']} controls={len(cui['controls'])} "
                f"empty={is_empty} first_image={safe(first_image)}"
            )
        if args.stop_empty_run and empty_run >= args.stop_empty_run:
            print(f"stop empty_run={empty_run} at index={index} pos={reader.pos}")
            break
    else:
        print(f"reached max={args.max} pos={reader.pos}")

    print(f"first_empty={first_empty}")
    print(f"last_non_empty={last_non_empty}")
    print(f"top_extras={extras.most_common(12)}")
    print(f"top_control_counts={control_counts.most_common(12)}")
    print(f"final_pos={reader.pos}")


if __name__ == "__main__":
    main()
