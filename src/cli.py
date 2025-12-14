import argparse
import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.infrastructure.config import get_config_dir, load_data, save_data

PID_FILE = get_config_dir() / "app.pid"


def get_current_pid():
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except:
            return None
    return None


def is_running(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)  # Check if process exists
        return True
    except OSError:
        return False


def cmd_launch(args):
    """Launch the application in the background."""
    pid = get_current_pid()
    if is_running(pid):
        print(f"Application is already running (PID: {pid})")
        return

    # Launch main.py
    main_script = Path(__file__).parent / "main.py"
    log_file = get_config_dir() / "app.log"

    try:
        # Open log file for appending
        with open(log_file, "a") as f:
            # Use subprocess.Popen to launch detached, redirecting output to log
            proc = subprocess.Popen(
                [sys.executable, str(main_script)],
                preexec_fn=os.setsid,
                stdout=f,
                stderr=subprocess.STDOUT,
            )
        print(f"Launched application (PID: {proc.pid})")
        print(f"Logs redirected to {log_file}")
    except Exception as e:
        print(f"Failed to launch application: {e}")


def cmd_close(args):
    """Close the running application."""
    pid = get_current_pid()
    if not is_running(pid):
        print("Application is not running.")
        return

    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Sent close signal to application (PID: {pid})")
    except Exception as e:
        print(f"Failed to close application: {e}")


def cmd_ghost(args):
    """Toggle click-through mode (transparency for input)."""
    data = load_data()
    if "global_config" not in data:
        data["global_config"] = {}

    current = data["global_config"].get("clickthrough", False)
    new_state = not current
    data["global_config"]["clickthrough"] = new_state

    save_data(data)
    save_data(data)
    print(f"Ghost Mode (Click-through) set to: {new_state}")


def cmd_border(args):
    """Edit visual effects."""
    data = load_data()
    if "global_config" not in data:
        data["global_config"] = {}
    if "visuals" not in data["global_config"]:
        data["global_config"]["visuals"] = {}

    if args.action == "set":
        if args.val is not None:
            data["global_config"]["visuals"]["rough_slide"] = float(args.val)
            print(f"Border roughness set to: {args.val}")
            save_data(data)
        else:
            print("Error: --val required for set")
    elif args.action == "animation":
        if args.state is not None:
            val = args.state.lower() == "on"
            data["global_config"]["visuals"]["animation_enabled"] = val
            print(f"Border animation set to: {val}")
            save_data(data)
        else:
            print("Error: --state (on/off) required for animation")
    else:
        print(
            f"Current roughness: {data['global_config']['visuals'].get('rough_slide', 1.0)}"
        )
        print(
            f"Animation enabled: {data['global_config']['visuals'].get('animation_enabled', True)}"
        )


def get_active_class(data):
    gid = data.get("global_config", {}).get("current_class_id", "Geral")
    if "classes" not in data:
        data["classes"] = {}
    if gid not in data["classes"]:
        data["classes"][gid] = {}
    return data["classes"][gid]


def cmd_bar(args):
    """Manage chart bar values."""
    data = load_data()
    cls_data = get_active_class(data)
    if "bars" not in cls_data:
        cls_data["bars"] = []

    bars = cls_data["bars"]

    if args.action == "add":
        if args.val is None:
            print("Error: Value required for add")
            return
        bars.append(float(args.val))
        print(f"Added bar value: {args.val}")
    elif args.action == "set":
        if args.id is None or args.val is None:
            print("Error: ID and Value required for set")
            return
        idx = int(args.id)
        if 0 <= idx < len(bars):
            bars[idx] = float(args.val)
            print(f"Set bar {idx} to {args.val}")
        else:
            print(f"Error: Index {idx} out of range")
    elif args.action == "rm":
        if args.id is None:
            print("Error: ID required for rm")
            return
        idx = int(args.id)
        if 0 <= idx < len(bars):
            val = bars.pop(idx)
            print(f"Removed bar {idx} (val: {val})")
        else:
            print(f"Error: Index {idx} out of range")

    save_data(data)


def cmd_slide(args):
    """Manage slides."""
    data = load_data()
    cls_data = get_active_class(data)
    if "active_slides" not in cls_data:
        cls_data["active_slides"] = []
    if "state" not in cls_data:
        cls_data["state"] = {}

    slides = cls_data["active_slides"]

    if args.action == "lock":
        if args.id is None:
            print("Error: ID required for lock")
            return
        idx = int(args.id)
        if 0 <= idx < len(slides):
            cls_data["state"]["locked_slide"] = idx
            print(f"Locked on slide {idx}")
        else:
            print(f"Error: Index {idx} out of range")

    elif args.action == "unlock":
        cls_data["state"]["locked_slide"] = -1
        print("Unlocked slides")

    elif args.action == "rm":
        if args.id is None:
            print("Error: ID required for rm")
            return
        idx = int(args.id)
        if 0 <= idx < len(slides):
            s = slides.pop(idx)
            print(f"Removed slide {idx} ({s.get('type')})")
        else:
            print(f"Error: Index {idx} out of range")

    elif args.action == "add":
        if not args.type:
            print("Error: Type required for add")
            return

        new_slide = {"type": args.type, "duration": args.duration}

        if args.type == "web":
            new_slide["url"] = args.url or "about:blank"
            if args.zoom:
                new_slide["zoom"] = float(args.zoom)
        elif args.type == "text":
            new_slide["content"] = args.content or "No Content"
            new_slide["title"] = args.title or "Info"
        elif args.type == "deadline":
            new_slide["date"] = args.date or datetime.now().isoformat()
            new_slide["title"] = args.title or "Deadline"
        elif args.type == "chart":
            pass  # No specific extras yet

        slides.append(new_slide)
        print(f"Added new {args.type} slide.")

    elif args.action == "edit":
        if args.id is None:
            print("Error: ID required for edit")
            return
        idx = int(args.id)
        if not (0 <= idx < len(slides)):
            print(f"Error: Index {idx} out of range")
            return

        s = slides[idx]
        if args.duration is not None:
            s["duration"] = args.duration

        # Generic updates based on args presence
        if args.url is not None:
            s["url"] = args.url
        if args.zoom is not None:
            s["zoom"] = float(args.zoom)
        if args.content is not None:
            s["content"] = args.content
        if args.title is not None:
            s["title"] = args.title
        if args.date is not None:
            s["date"] = args.date

        print(f"Edited slide {idx}.")

    save_data(data)


def main():
    parser = argparse.ArgumentParser(description="Slide Scroller Management CLI")
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Command to execute"
    )

    # Launch
    p_launch = subparsers.add_parser("launch", help="Launch the application detached.")
    p_launch.set_defaults(func=cmd_launch)

    # Close
    p_close = subparsers.add_parser("close", help="Close the running application.")
    p_close.set_defaults(func=cmd_close)

    # Ghost
    p_ghost = subparsers.add_parser("ghost", help="Toggle Ghost Mode (Click-through).")
    p_ghost.set_defaults(func=cmd_ghost)

    # Border
    p_border = subparsers.add_parser("border", help="Manage visual border effects.")
    p_border.add_argument(
        "action", choices=["set", "animation"], help="Action to perform"
    )
    p_border.add_argument("--val", help="Value to set (for 'set' action). Float.")
    p_border.add_argument(
        "--state",
        choices=["on", "off"],
        help="Animation state (for 'animation' action)",
    )
    p_border.set_defaults(func=cmd_border)

    # Bar
    p_bar = subparsers.add_parser("bar", help="Manage chart bar values.")
    p_bar.add_argument(
        "action",
        choices=["add", "set", "rm"],
        help="Action: add value, set index value, rm index",
    )
    p_bar.add_argument("id", nargs="?", help="Index (for set/rm)")
    p_bar.add_argument("val", nargs="?", help="Value (for add/set)")
    p_bar.set_defaults(func=cmd_bar)

    # Slide
    p_slide = subparsers.add_parser("slide", help="Manage slides.")
    p_slide.add_argument(
        "action",
        choices=["add", "rm", "edit", "lock", "unlock"],
        help="Action to perform",
    )
    p_slide.add_argument("id", nargs="?", help="Index (for rm/edit/lock)")

    # Slide Add/Edit Options
    p_slide.add_argument(
        "--type",
        choices=["web", "text", "deadline", "chart"],
        help="Type of slide (for add)",
    )
    p_slide.add_argument(
        "--duration", type=int, default=10, help="Duration in seconds (default 10)"
    )

    # Specifics
    p_slide.add_argument("--url", help="URL for web slide")
    p_slide.add_argument("--zoom", help="Zoom level for web slide")
    p_slide.add_argument("--content", help="Content for text/notice slide")
    p_slide.add_argument("--title", help="Title for text/deadline slide")
    p_slide.add_argument("--date", help="Date for deadline slide (ISO format)")

    p_slide.set_defaults(func=cmd_slide)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
