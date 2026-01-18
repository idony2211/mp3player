"""
Audio extraction utilities for segment transcription.
Uses ffmpeg directly to avoid pydub Python 3.13 compatibility issues.
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def extract_audio_segment(
    audio_file_path: str, start_time: float, end_time: float, output_format: str = "wav"
) -> Optional[str]:
    """
    Extract a segment from an audio file using ffmpeg.

    Args:
        audio_file_path: Path to the source audio file
        start_time: Start time in seconds
        end_time: End time in seconds
        output_format: Output audio format (wav, mp3, etc.)

    Returns:
        Path to the extracted segment audio file, or None if failed
    """
    try:
        temp_dir = tempfile.gettempdir()
        temp_file = (
            Path(temp_dir)
            / f"segment_{int(start_time)}_{int(end_time)}.{output_format}"
        )

        duration = end_time - start_time

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            audio_file_path,
            "-ss",
            str(start_time),
            "-t",
            str(duration),
            "-acodec",
            "pcm_s16le",
            "-vn",
            "-f",
            output_format,
            str(temp_file),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            return None

        if temp_file.exists():
            logger.info(
                f"Extracted audio segment: {start_time}s - {end_time}s -> {temp_file}"
            )
            return str(temp_file)
        else:
            logger.error(f"Failed to create audio segment file")
            return None

    except FileNotFoundError:
        logger.error("ffmpeg not found. Install ffmpeg first.")
        return None
    except Exception as e:
        logger.error(f"Failed to extract audio segment: {e}")
        return None


def cleanup_temp_audio(temp_file_path: Optional[str]) -> None:
    """
    Clean up temporary audio file.

    Args:
        temp_file_path: Path to the temporary audio file
    """
    if temp_file_path and os.path.exists(temp_file_path):
        try:
            os.remove(temp_file_path)
            logger.info(f"Cleaned up temporary file: {temp_file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp file {temp_file_path}: {e}")


def validate_segment_times(
    start_time: float, end_time: float, max_duration: float = 18000.0
) -> Tuple[bool, str]:
    """
    Validate segment time parameters.

    Args:
        start_time: Start time in seconds
        end_time: End time in seconds
        max_duration: Maximum allowed segment duration in seconds

    Returns:
        Tuple of (is_valid, error_message)
    """
    if start_time < 0:
        return False, "Start time cannot be negative"

    if end_time <= start_time:
        return False, "End time must be greater than start time"

    duration = end_time - start_time
    if duration > max_duration:
        return (
            False,
            f"Segment duration ({duration:.1f}s) exceeds maximum ({max_duration}s)",
        )

    return True, ""
