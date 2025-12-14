import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.infrastructure.config import get_config_dir, load_data, save_data

PID_FILE = get_config_dir() / "app.pid"


def get_current_pid():
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except Exception:
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
    print(f"Ghost Mode (Click-through) set to: {new_state}")

    pid = get_current_pid()

    if is_running(pid):
        print("Restarting application to apply Ghost Mode...")

        try:
            os.kill(pid, signal.SIGTERM)

            # Wait for process to die - using efficient Linux pidfd if available
            try:
                if hasattr(os, "pidfd_open"):
                    import select

                    fd = os.pidfd_open(pid)
                    try:
                        p = select.poll()
                        p.register(fd, select.POLLIN)
                        if not p.poll(5000):
                            print("Timed out waiting for application to close.")
                    finally:
                        os.close(fd)
                else:
                    raise OSError("pidfd_open not supported")

            except Exception:
                # Fallback to polling
                import time

                timeout = 5.0
                start_time = time.time()

                while is_running(pid):
                    if time.time() - start_time > timeout:
                        print("Timed out waiting for application to close.")
                        break
                    time.sleep(0.05)

        except Exception as e:
            print(f"Error during close: {e}")

    cmd_launch(args)


def cmd_invert(args):
    """Toggle color inversion (black <-> white)."""
    data = load_data()
    if "global_config" not in data:
        data["global_config"] = {}

    current = data["global_config"].get("color_inverted", False)
    new_state = not current
    data["global_config"]["color_inverted"] = new_state

    save_data(data)
    print(f"Color Inversion set to: {new_state}")

    pid = get_current_pid()

    if is_running(pid):
        print("Restarting application to apply color inversion...")

        try:
            os.kill(pid, signal.SIGTERM)

            try:
                if hasattr(os, "pidfd_open"):
                    import select

                    fd = os.pidfd_open(pid)
                    try:
                        p = select.poll()
                        p.register(fd, select.POLLIN)
                        if not p.poll(5000):
                            print("Timed out waiting for application to close.")
                    finally:
                        os.close(fd)
                else:
                    raise OSError("pidfd_open not supported")

            except Exception:
                import time

                timeout = 5.0
                start_time = time.time()

                while is_running(pid):
                    if time.time() - start_time > timeout:
                        print("Timed out waiting for application to close.")
                        break
                    time.sleep(0.05)

        except Exception as e:
            print(f"Error during close: {e}")

    cmd_launch(args)


def cmd_border(args):
    """Edit visual effects."""
    data = load_data()
    if "global_config" not in data:
        data["global_config"] = {}
    if "visuals" not in data["global_config"]:
        data["global_config"]["visuals"] = {}

    match args.action:
        case "set":
            data["global_config"]["visuals"]["rough_slide"] = float(args.val)
            print(f"Border roughness set to: {args.val}")
            save_data(data)
        case "radius":
            data["global_config"]["visuals"]["border_radius"] = float(args.val)
            print(f"Border radius set to: {args.val}")
            save_data(data)
        case "animation":
            val = args.state.lower() == "on"
            data["global_config"]["visuals"]["animation_enabled"] = val
            print(f"Border animation set to: {val}")
            save_data(data)
        case "show":
            vis = data.get("global_config", {}).get("visuals", {})
            print(f"Current roughness: {vis.get('rough_slide', 1.0)}")
            print(f"Current radius: {vis.get('border_radius', 10.0)}")
            print(f"Animation enabled: {vis.get('animation_enabled', True)}")


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

    match args.action:
        case "add":
            bars.append(float(args.val))
            print(f"Added bar value: {args.val}")
        case "set":
            idx = int(args.id)
            if 0 <= idx < len(bars):
                bars[idx] = float(args.val)
                print(f"Set bar {idx} to {args.val}")
            else:
                print(f"Error: Index {idx} out of range")
        case "rm":
            idx = int(args.id)
            if 0 <= idx < len(bars):
                val = bars.pop(idx)
                print(f"Removed bar {idx} (val: {val})")
            else:
                print(f"Error: Index {idx} out of range")

    save_data(data)


def cmd_deadline(args):
    """Manage global deadlines."""
    data = load_data()
    cls_data = get_active_class(data)
    if "deadlines" not in cls_data:
        cls_data["deadlines"] = []

    deadlines = cls_data["deadlines"]

    match args.action:
        case "add":
            new_task = {"task": args.task, "date": args.date}
            deadlines.append(new_task)
            print("Added new deadline:")
            print(f"  Task: {args.task}")
            print(f"  Date: {args.date}")
        case "rm":
            idx = int(args.id)
            if 0 <= idx < len(deadlines):
                removed = deadlines.pop(idx)
                print(f"Removed deadline {idx}:")
                print(f"  Task: {removed.get('task')}")
                print(f"  Date: {removed.get('date')}")
            else:
                print(f"Error: Index {idx} out of range")
        case "list":
            if not deadlines:
                print("No deadlines configured.")
            else:
                print(f"Total deadlines: {len(deadlines)}\n")
                for i, item in enumerate(deadlines):
                    print(f"[{i}] {item.get('task')} ({item.get('date')})")

    save_data(data)


def cmd_slide_content(args):
    """Manage content items within text slides."""
    data = load_data()
    cls_data = get_active_class(data)
    if "active_slides" not in cls_data:
        cls_data["active_slides"] = []

    slides = cls_data["active_slides"]
    slide_idx = args.slide_id

    if not (0 <= slide_idx < len(slides)):
        print(f"Error: Slide ID {slide_idx} out of range")
        return

    slide = slides[slide_idx]
    if slide.get("type") != "text":
        print(f"Error: Slide {slide_idx} is not a text slide")
        return

    if "messages" not in slide:
        slide["messages"] = []

    messages = slide["messages"]

    match args.content_action:
        case "add":
            new_msg = args.content
            messages.append(new_msg)
            print(
                f"Added content item to slide {slide_idx} (now {len(messages)} items)"
            )
        case "rm":
            content_idx = args.content_id
            if 0 <= content_idx < len(messages):
                messages.pop(content_idx)
                print(f"Removed content item {content_idx} from slide {slide_idx}")
            else:
                print(f"Error: Content ID {content_idx} out of range")
                return
        case "edit":
            content_idx = args.content_id
            if 0 <= content_idx < len(messages):
                messages[content_idx] = args.content
                print(f"Edited content item {content_idx} in slide {slide_idx}")
            else:
                print(f"Error: Content ID {content_idx} out of range")
                return
        case "list":
            if not messages:
                print(f"Slide {slide_idx} has no content items")
            else:
                item_duration = slide.get("duration", 10) / len(messages)
                print(
                    f"Slide {slide_idx} - {len(messages)} content item(s) ({item_duration:.1f}s each):\n"
                )
                for i, msg in enumerate(messages):
                    content = msg if isinstance(msg, str) else msg.get("content", "")
                    preview = content[:60]
                    if len(content) > 60:
                        preview += "..."
                    print(f"[{i}] {preview}")

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

    match args.action:
        case "lock":
            idx = int(args.id)
            if 0 <= idx < len(slides):
                cls_data["state"]["locked_slide"] = idx
                print(f"Locked on slide {idx}")
            else:
                print(f"Error: Index {idx} out of range")
        case "unlock":
            cls_data["state"]["locked_slide"] = -1
            print("Unlocked slides")
        case "rm":
            idx = int(args.id)
            if 0 <= idx < len(slides):
                s = slides.pop(idx)
                print(f"Removed slide {idx} ({s.get('type')})")
            else:
                print(f"Error: Index {idx} out of range")
        case "add":
            new_slide = {"type": args.type, "duration": args.duration}

            match args.type:
                case "web":
                    new_slide["url"] = args.url or "about:blank"
                    if args.zoom:
                        new_slide["zoom"] = float(args.zoom)
                case "text":
                    # Store content items as simple strings
                    if args.content:
                        new_slide["messages"] = args.content
                    else:
                        new_slide["messages"] = ["# Vazio"]

                    new_slide["title"] = args.title or "Info"

                    if hasattr(args, "text_align") and args.text_align:
                        new_slide["text_align"] = args.text_align
                case "deadline":
                    if args.date:
                        new_slide["date"] = args.date
                    new_slide["title"] = args.title or "Deadline"
                case "chart":
                    pass

            slides.append(new_slide)
            print(f"Added new {args.type} slide.")
            if args.type == "text" and args.content:
                print(f"  → {len(args.content)} content item(s) added")
        case "edit":
            idx = int(args.id)
            if not (0 <= idx < len(slides)):
                print(f"Error: Index {idx} out of range")
                return

            s = slides[idx]
            if args.duration is not None:
                s["duration"] = args.duration

            # Generic updates
            if hasattr(args, "url") and args.url is not None:
                s["url"] = args.url
            if hasattr(args, "zoom") and args.zoom is not None:
                s["zoom"] = float(args.zoom)
            if hasattr(args, "title") and args.title is not None:
                s["title"] = args.title
            if hasattr(args, "date") and args.date is not None:
                s["date"] = args.date

            # Text slide content editing
            if hasattr(args, "content") and args.content is not None:
                if s.get("type") == "text":
                    # If content-id specified, edit specific content item
                    if hasattr(args, "content_id") and args.content_id is not None:
                        if "messages" in s:
                            content_idx = args.content_id
                            if 0 <= content_idx < len(s["messages"]):
                                s["messages"][content_idx] = args.content
                                print(
                                    f"Edited content item {content_idx} in slide {idx}."
                                )
                            else:
                                print(f"Error: Content ID {content_idx} out of range")
                                return
                        else:
                            print("Error: Slide has no content items")
                            return
                    else:
                        # Replace all content with single item (backward compatibility)
                        s["messages"] = [args.content]
                        print(f"Replaced all content in slide {idx}.")
                else:
                    # For non-text slides, keep old behavior
                    s["content"] = args.content
                    print(f"Edited slide {idx}.")
            else:
                print(f"Edited slide {idx}.")
        case "list":
            if not slides:
                print("No slides configured.")
            else:
                print(f"Total slides: {len(slides)}\n")
                for i, s in enumerate(slides):
                    stype = s.get("type", "unknown")
                    duration = s.get("duration", 10)
                    info = []

                    if stype == "web":
                        info.append(f"URL: {s.get('url')}")
                    elif stype == "text":
                        info.append(f"Title: {s.get('title')}")
                        # Show multiple content items if available
                        if "messages" in s:
                            info.append(f"Content items: {len(s['messages'])}")
                            item_duration = s.get("duration", 10) / len(s["messages"])
                            for ci, msg in enumerate(s["messages"]):
                                content = (
                                    msg
                                    if isinstance(msg, str)
                                    else msg.get("content", "")
                                )
                                preview = content[:50]
                                if len(content) > 50:
                                    preview += "..."
                                info.append(
                                    f"  [{ci}] {preview} ({item_duration:.1f}s)"
                                )
                        else:
                            # Backward compatibility
                            info.append(f"Content: {s.get('content')}")
                    elif stype == "deadline":
                        info.append(f"Title: {s.get('title')}")
                        if s.get("date"):
                            info.append(f"Date: {s.get('date')}")
                        else:
                            info.append("Source: Global Deadlines")

                    state_str = ""
                    if cls_data.get("state", {}).get("locked_slide") == i:
                        state_str = " [LOCKED]"

                    print(f"[{i}] {stype.upper()} ({duration}s){state_str}")
                    for line in info:
                        print(f"    - {line}")
                    print("")
    save_data(data)


class ColoredHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom help formatter with colors."""

    def _format_action_invocation(self, action):
        if not action.option_strings:
            return super()._format_action_invocation(action)

        # Colorize flags (e.g. -h, --help) in yellow
        default = super()._format_action_invocation(action)
        return f"\033[93m{default}\033[0m"

    def _format_usage(self, usage, actions, groups, prefix):
        # Colorize usage prefix
        usage_text = super()._format_usage(usage, actions, groups, prefix)
        return usage_text.replace("usage:", "\033[96musage:\033[0m")

    def start_section(self, heading):
        # Colorize section headers (e.g. "options:", "positional arguments:") in Cyan
        super().start_section(f"\033[96m{heading}\033[0m")


def main():
    parser = argparse.ArgumentParser(
        description="\033[1mSlide Scroller Management CLI\033[0m",
        formatter_class=ColoredHelpFormatter,
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Command to execute"
    )

    # Launch
    p_launch = subparsers.add_parser(
        "launch",
        help="Launch the application detached.",
        formatter_class=ColoredHelpFormatter,
    )
    p_launch.set_defaults(func=cmd_launch)

    # Close
    p_close = subparsers.add_parser(
        "close",
        help="Close the running application.",
        formatter_class=ColoredHelpFormatter,
    )
    p_close.set_defaults(func=cmd_close)

    # Ghost
    p_ghost = subparsers.add_parser(
        "ghost",
        help="Toggle Ghost Mode (Click-through).",
        formatter_class=ColoredHelpFormatter,
    )
    p_ghost.set_defaults(func=cmd_ghost)

    # Invert
    p_invert = subparsers.add_parser(
        "invert",
        help="Toggle color inversion (black <-> white).",
        formatter_class=ColoredHelpFormatter,
    )
    p_invert.set_defaults(func=cmd_invert)

    # Border
    p_border = subparsers.add_parser(
        "border",
        help="Manage visual border effects.",
        formatter_class=ColoredHelpFormatter,
    )
    border_subs = p_border.add_subparsers(dest="action", required=True)

    # Border Set
    p_border_set = border_subs.add_parser(
        "set",
        help="Set roughness value",
        formatter_class=ColoredHelpFormatter,
    )
    p_border_set.add_argument(
        "--val", required=True, type=float, help="Roughness value"
    )

    # Border Radius
    p_border_radius = border_subs.add_parser(
        "radius",
        help="Set border radius",
        formatter_class=ColoredHelpFormatter,
    )
    p_border_radius.add_argument(
        "--val", required=True, type=float, help="Radius value"
    )

    # Border Animation
    p_border_anim = border_subs.add_parser(
        "animation",
        help="Toggle animation",
        formatter_class=ColoredHelpFormatter,
    )
    p_border_anim.add_argument(
        "--state", required=True, choices=["on", "off"], help="Animation state"
    )

    # Border Show
    border_subs.add_parser(
        "show",
        help="Show current border settings",
        formatter_class=ColoredHelpFormatter,
    )

    p_border.set_defaults(func=cmd_border)

    # Bar
    p_bar = subparsers.add_parser(
        "bar", help="Manage chart bar values.", formatter_class=ColoredHelpFormatter
    )
    bar_subs = p_bar.add_subparsers(dest="action", required=True)

    # Bar Add
    p_bar_add = bar_subs.add_parser(
        "add",
        help="Add a bar value",
        formatter_class=ColoredHelpFormatter,
    )
    p_bar_add.add_argument("--val", required=True, type=float, help="Value to add")

    # Bar Set
    p_bar_set = bar_subs.add_parser(
        "set",
        help="Set a bar value by ID",
        formatter_class=ColoredHelpFormatter,
    )
    p_bar_set.add_argument("--id", required=True, type=int, help="Index of bar")
    p_bar_set.add_argument("--val", required=True, type=float, help="New value")

    # Bar Remove
    p_bar_rm = bar_subs.add_parser(
        "rm",
        help="Remove a bar by ID",
        formatter_class=ColoredHelpFormatter,
    )
    p_bar_rm.add_argument(
        "--id", required=True, type=int, help="Index of bar to remove"
    )

    p_bar.set_defaults(func=cmd_bar)

    # Deadline
    p_deadline = subparsers.add_parser(
        "deadline",
        help="Manage global deadlines.",
        formatter_class=ColoredHelpFormatter,
    )
    deadline_subs = p_deadline.add_subparsers(dest="action", required=True)

    # Deadline Add
    p_deadline_add = deadline_subs.add_parser(
        "add",
        help="Add a new deadline",
        formatter_class=ColoredHelpFormatter,
    )
    p_deadline_add.add_argument("--task", required=True, help="Task description")
    p_deadline_add.add_argument(
        "--date", required=True, help="Date in DD/MM/YYYY format"
    )

    # Deadline Remove
    p_deadline_rm = deadline_subs.add_parser(
        "rm",
        help="Remove a deadline by ID",
        formatter_class=ColoredHelpFormatter,
    )
    p_deadline_rm.add_argument("--id", required=True, type=int, help="Deadline ID")

    # Deadline List
    deadline_subs.add_parser(
        "list",
        help="List all deadlines",
        formatter_class=ColoredHelpFormatter,
    )

    p_deadline.set_defaults(func=cmd_deadline)

    # Slide
    p_slide = subparsers.add_parser(
        "slide", help="Manage slides.", formatter_class=ColoredHelpFormatter
    )
    slide_subs = p_slide.add_subparsers(dest="action", required=True)

    # Slide Lock
    p_slide_lock = slide_subs.add_parser(
        "lock",
        help="Lock specific slide",
        formatter_class=ColoredHelpFormatter,
    )
    p_slide_lock.add_argument("--id", required=True, type=int, help="Slide ID")

    # Slide Unlock
    slide_subs.add_parser(
        "unlock", help="Unlock slides", formatter_class=ColoredHelpFormatter
    )

    # Slide List
    slide_subs.add_parser(
        "list", help="List all slides", formatter_class=ColoredHelpFormatter
    )

    # Slide Remove
    p_slide_rm = slide_subs.add_parser(
        "rm",
        help="Remove specific slide",
        formatter_class=ColoredHelpFormatter,
    )
    p_slide_rm.add_argument("--id", required=True, type=int, help="Slide ID")

    # Slide Add
    p_slide_add = slide_subs.add_parser(
        "add",
        help="Add a new slide",
        formatter_class=ColoredHelpFormatter,
    )

    # Common Options
    p_slide_add.add_argument(
        "--type",
        required=True,
        choices=["web", "text", "deadline", "chart"],
        help="Type of slide to add.",
    )
    p_slide_add.add_argument(
        "--duration", type=int, default=10, help="Duration in seconds (default: 10)."
    )

    # Web Slide Options
    grp_web = p_slide_add.add_argument_group("Web Slide Options")
    grp_web.add_argument("--url", help="URL to display (e.g. https://google.com).")
    grp_web.add_argument("--zoom", help="Zoom level for the page (e.g. 1.0, 1.5).")

    # Text & Deadline Options
    grp_content = p_slide_add.add_argument_group("Text & Deadline Options")
    grp_content.add_argument("--title", help="Title header for the slide.")
    grp_content.add_argument(
        "--content",
        action="append",
        help="Text content (can be used multiple times for rotating content items).",
    )
    grp_content.add_argument(
        "--text-align",
        choices=["center", "left"],
        default="center",
        dest="text_align",
        help="Text alignment: 'center' (default) or 'left'.",
    )
    grp_content.add_argument(
        "--date", help="Target date in ISO format YYYY-MM-DD (Deadline slides only)."
    )

    # Rename standard "options" group to "Common Options" for clarity
    for action_group in p_slide_add._action_groups:
        if action_group.title == "options":
            action_group.title = "Common Options"

    # Slide Edit
    p_slide_edit = slide_subs.add_parser(
        "edit",
        help="Edit an existing slide",
        formatter_class=ColoredHelpFormatter,
    )
    p_slide_edit.add_argument("--id", required=True, type=int, help="Slide ID")
    p_slide_edit.add_argument("--duration", type=int, help="Duration in seconds")
    p_slide_edit.add_argument("--url", help="URL (web)")
    p_slide_edit.add_argument("--zoom", help="Zoom (web)")
    p_slide_edit.add_argument("--content", help="Content (text)")
    p_slide_edit.add_argument(
        "--content-id",
        type=int,
        help="Specific content item ID to edit (text slides only)",
    )
    p_slide_edit.add_argument("--title", help="Title (text/deadline)")
    p_slide_edit.add_argument("--date", help="Date (deadline)")

    # Slide Content (manage content items within text slides)
    p_slide_content = slide_subs.add_parser(
        "content",
        help="Manage content items within text slides",
        formatter_class=ColoredHelpFormatter,
    )
    content_subs = p_slide_content.add_subparsers(dest="content_action", required=True)

    # Content Add
    p_content_add = content_subs.add_parser(
        "add",
        help="Add content item to text slide",
        formatter_class=ColoredHelpFormatter,
    )
    p_content_add.add_argument("--slide-id", required=True, type=int, help="Slide ID")
    p_content_add.add_argument("--content", required=True, help="Content text")

    # Content Remove
    p_content_rm = content_subs.add_parser(
        "rm",
        help="Remove content item from text slide",
        formatter_class=ColoredHelpFormatter,
    )
    p_content_rm.add_argument("--slide-id", required=True, type=int, help="Slide ID")
    p_content_rm.add_argument(
        "--content-id", required=True, type=int, help="Content item ID"
    )

    # Content Edit
    p_content_edit = content_subs.add_parser(
        "edit",
        help="Edit content item in text slide",
        formatter_class=ColoredHelpFormatter,
    )
    p_content_edit.add_argument("--slide-id", required=True, type=int, help="Slide ID")
    p_content_edit.add_argument(
        "--content-id", required=True, type=int, help="Content item ID"
    )
    p_content_edit.add_argument("--content", required=True, help="New content text")

    # Content List
    p_content_list = content_subs.add_parser(
        "list",
        help="List content items in text slide",
        formatter_class=ColoredHelpFormatter,
    )
    p_content_list.add_argument("--slide-id", required=True, type=int, help="Slide ID")

    p_slide_content.set_defaults(func=cmd_slide_content)
    p_slide.set_defaults(func=cmd_slide)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
