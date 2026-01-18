import logging
import os
from datetime import datetime
from pathlib import Path

# Global flag to ensure logging is only set up once
_logging_initialized = False

def setup_logging(log_level=logging.DEBUG, log_file=None):
    """
    Set up logging to write to a file instead of the console.

    Args:
        log_level: The logging level (default: logging.DEBUG)
        log_file: Path to the log file (default: 'mp3player.log' in current directory)
    """
    global _logging_initialized

    # Only set up logging once
    if _logging_initialized:
        return

    # Get the mp3player project root directory (parent of the mp3player package)
    module_dir = Path(__file__).resolve().parent
    project_root = module_dir.parent
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)

    if log_file is None:
        # Create a log file with timestamp in the name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"mp3player_{timestamp}.log"

    # Full path for the log file (always use the logs directory in the mp3player package)
    log_file_path = log_dir / log_file

    # Remove all existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Configure logging to write to the file
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
            # Removed logging.StreamHandler() to stop console output
        ]
    )

    # Mark logging as initialized
    _logging_initialized = True

    # Create a logger for the application
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_file_path}")

    return log_file_path