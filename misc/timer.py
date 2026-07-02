#!/usr/bin/env -S uv run --script
# /// script
# dependencies = []
# ///

import statistics
import sys
import termios
import time
import tty


def _format_stat(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.3f}s"
    hours, remainder = divmod(int(round(seconds)), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _format_counter(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _get_char(timeout: float) -> str | None:
    import select

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        r, _, _ = select.select([sys.stdin], [], [], timeout)
        if r:
            return sys.stdin.read(1)
        return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def main() -> None:
    rounds: list[float] = []
    start = time.monotonic()
    round_start = start
    round_num = 1

    print()

    try:
        while True:
            ch = _get_char(0.05)

            if ch == " ":
                lap = time.monotonic() - round_start
                rounds.append(lap)

                total_time = time.monotonic() - start
                avg = sum(rounds) / len(rounds)
                med = statistics.median(rounds)

                round_label = f"round {round_num}:"
                tot_label = "total:"
                avg_label = "average:"
                med_label = "median:"
                pad = max(len(round_label), len(tot_label), len(avg_label), len(med_label)) + 2

                round_str = f"{round_label:<{pad}}{_format_stat(lap)}"
                tot_str = f"{tot_label:<{pad}}{_format_stat(total_time)}"
                avg_str = f"{avg_label:<{pad}}{_format_stat(avg)}"
                med_str = f"{med_label:<{pad}}{_format_stat(med)}"

                if med > 0 and (1.0 / med) >= 0.5:
                    hz = 1.0 / med
                    bpm = hz * 60.0
                    med_str += f" ({hz:.2f}Hz, {int(round(bpm))}bpm)"

                # Clear line, print stats block, then a blank line
                print(f"\r{round_str}")
                print(tot_str)
                print(avg_str)
                print(med_str)
                print()

                round_num += 1
                round_start = time.monotonic()
            elif ch == "\x03":
                break

            current = time.monotonic() - round_start
            if round_num == 1:
                print(f"\r{_format_counter(current)}  ", end="", flush=True)
            else:
                print(f"\r[R{round_num}] {_format_counter(current)}  ", end="", flush=True)

    except KeyboardInterrupt:
        pass

    print()
    if rounds:
        print("--- Final ---")
        print(f"Rounds: {len(rounds)}")
        print(f"Total:  {_format_stat(time.monotonic() - start)}")
        avg = sum(rounds) / len(rounds)
        med = statistics.median(rounds)
        print(f"Last:   {_format_stat(rounds[-1])}")
        print(f"Avg:    {_format_stat(avg)}")
        med_str = f"Med:    {_format_stat(med)}"
        if med > 0 and (1.0 / med) >= 0.5:
            hz = 1.0 / med
            bpm = hz * 60.0
            med_str += f" ({hz:.2f}Hz, {int(round(bpm))}bpm)"
        print(med_str)
    else:
        total = time.monotonic() - start
        print(f"Total:  {_format_counter(total)}")


if __name__ == "__main__":
    main()
