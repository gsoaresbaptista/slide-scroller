import json
import os
import platform
from pathlib import Path


def get_config_dir():
    if platform.system() == "Windows":
        base = Path(os.environ.get("APPDATA"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    path = base / "slide-scroller"
    path.mkdir(parents=True, exist_ok=True)
    return path


DATA_FILE = get_config_dir() / "dashboard.json"


def load_data():
    """Loads the dashboard data from JSON."""
    if not DATA_FILE.exists():
        # Create default if not exists
        default_data = {
            "global_config": {
                "width": 600,
                "height": 500,
                "x": 100,
                "y": 100,
                "current_class_id": "Geral",
                "clickthrough": False,
                "visuals": {
                    "breathing_intensity": 0.5,
                    "bar_alpha": 0.5,
                    "font_family": "Segoe UI",
                },
            },
            "classes": {
                "Geral": {
                    "bars": [10.0, 20.0, 15.0],
                    "notices": [{"content": "# Welcome", "duration": 10}],
                    "active_slides": [{"type": "chart", "duration": 10}],
                }
            },
        }
        save_data(default_data)
        return default_data

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading data: {e}")
        return {}


def save_data(data):
    """Saves the dashboard data to JSON atomically."""
    try:
        # Atomic write: write to temp file then rename
        temp_file = DATA_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        # Rename is atomic on POSIX
        temp_file.replace(DATA_FILE)
    except Exception as e:
        print(f"Error saving data: {e}")
        if "temp_file" in locals() and temp_file.exists():
            try:
                temp_file.unlink()
            except:
                pass


def get_current_class_data():
    """Helper to get the data for the currently active class."""
    data = load_data()
    if not data:
        return {}

    global_conf = data.get("global_config", {})
    current_id = global_conf.get("current_class_id", "Geral")
    classes = data.get("classes", {})

    return classes.get(current_id, {})
