import numpy as np
from typing import Optional, List, Dict, Any

# Constants
DEFAULT_GEOMETRY = "600x500"
CANVAS_HEIGHT = 30
CANVAS_BG = "#f0f0f0"
CANVAS_OUTLINE = "#cccccc"
PROGRESS_COLOR = "#8CA9DB"  # 50% opacity equivalent of #4a90e2
PROGRESS_HIGHLIGHT = "#B8D1ED"  # 50% opacity equivalent of #a0c4e8
INDICATOR_COLOR = "#ff3b30"
TIME_FORMAT = "{:02d}:{:02d}.{:02d}"
MAX_WAIT_FOR_SOCKET = 10  # seconds
SOCKET_POLL_INTERVAL = 0.1  # seconds
UPDATE_INTERVAL = 250  # milliseconds
RETRY_DELAY = 0.5  # seconds
MAX_RETRIES = 3
END_TOLERANCE = 0.5  # seconds
WAVEFORM_SAMPLES = 500
TIME_JUMP_TOLERANCE = 0.01  # seconds

def get_canvas_dimensions(canvas) -> tuple[int, int]:
    """
    Get canvas dimensions with default fallback values.
    """
    canvas_width = canvas.winfo_width()
    canvas_height = canvas.winfo_height()

    if canvas_width <= 1:
        canvas_width = 560  # Default width when canvas isn't fully rendered yet
    if canvas_height <= 1:
        canvas_height = CANVAS_HEIGHT

    return canvas_width, canvas_height