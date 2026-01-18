#!/usr/bin/env python3
"""
Command-line tool for transcribing audio files using WhisperX.

Usage:
    python -m mp3player.transcribe_cli <audio_file> [--model MODEL] [--output OUTPUT]

Examples:
    python -m mp3player.transcribe_cli audio.mp3
    python -m mp3player.transcribe_cli audio.mp3 --model medium --output transcript.txt
"""

import argparse
import logging
import sys
import os
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def transcribe_audio(
    audio_path: str, model_size: str = "base", output_file: str = None
) -> str:
    """
    Transcribe an audio file using WhisperX.

    Args:
        audio_path: Path to the audio file
        model_size: WhisperX model size (tiny, base, small, medium, large)
        output_file: Optional output file path for the transcription

    Returns:
        The transcribed text
    """
    try:
        import whisperx
        import torch

        logger.info(f"Loading WhisperX model: {model_size}")
        model = whisperx.load_model(model_size, device="cpu")

        logger.info(f"Loading audio file: {audio_path}")
        audio = whisperx.load_audio(audio_path)

        logger.info("Transcribing audio...")
        result = model.transcribe(audio, batch_size=1)

        text = result.get("text", "").strip() if result else ""

        if text:
            logger.info(f"Transcription complete: {len(text)} characters")
        else:
            logger.warning("Transcription returned empty result")

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(text)
            logger.info(f"Transcription saved to: {output_file}")

        return text

    except ImportError as e:
        logger.error(f"WhisperX not installed: {e}")
        logger.error("Install with: pip install whisperx")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        sys.exit(1)


def transcribe_segment(
    audio_path: str,
    start_time: float,
    end_time: float,
    model_size: str = "base",
    output_file: str = None,
) -> str:
    """
    Transcribe a segment of an audio file using WhisperX.

    Args:
        audio_path: Path to the audio file
        start_time: Start time in seconds
        end_time: End time in seconds
        model_size: WhisperX model size (tiny, base, small, medium, large)
        output_file: Optional output file path for the transcription

    Returns:
        The transcribed text
    """
    try:
        import subprocess
        import tempfile

        logger.info(f"Extracting audio segment: {start_time}s - {end_time}s")

        duration = end_time - start_time
        temp_dir = tempfile.gettempdir()
        temp_file = Path(temp_dir) / f"segment_{int(start_time)}_{int(end_time)}.wav"

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            audio_path,
            "-ss",
            str(start_time),
            "-t",
            str(duration),
            "-acodec",
            "pcm_s16le",
            "-vn",
            "-f",
            "wav",
            str(temp_file),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            sys.exit(1)

        logger.info(f"Extracted segment saved to: {temp_file}")
        text = transcribe_audio(str(temp_file), model_size, output_file)

        try:
            os.remove(str(temp_file))
            logger.info(f"Cleaned up temporary file: {temp_file}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp file: {e}")

        return text

    except FileNotFoundError:
        logger.error("ffmpeg not found. Install ffmpeg first.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio files using WhisperX",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    Transcribe an entire audio file:
        python -m mp3player.transcribe_cli audio.mp3

    Transcribe with a different model:
        python -m mp3player.transcribe_cli audio.mp3 --model medium

    Transcribe a segment (30-60 seconds):
        python -m mp3player.transcribe_cli audio.mp3 --start 30 --end 60

    Save transcription to a file:
        python -m mp3player.transcribe_cli audio.mp3 --output transcript.txt

Available models:
    tiny   - Fastest, lowest accuracy
    base   - Good balance of speed and accuracy
    small  - Better accuracy, slower
    medium - High accuracy, slower
    large  - Best accuracy, slowest
        """,
    )

    parser.add_argument(
        "audio_file", type=str, help="Path to the audio file to transcribe"
    )

    parser.add_argument(
        "--model",
        type=str,
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="WhisperX model size (default: base)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file for the transcription (default: stdout)",
    )

    parser.add_argument(
        "--start",
        type=float,
        default=None,
        help="Start time of segment to transcribe (in seconds)",
    )

    parser.add_argument(
        "--end",
        type=float,
        default=None,
        help="End time of segment to transcribe (in seconds)",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    audio_file = args.audio_file
    if not os.path.exists(audio_file):
        logger.error(f"Audio file not found: {audio_file}")
        sys.exit(1)

    if args.start is not None and args.end is not None:
        if args.start >= args.end:
            logger.error("Start time must be less than end time")
            sys.exit(1)
        text = transcribe_segment(
            audio_file, args.start, args.end, args.model, args.output
        )
    elif args.start is not None or args.end is not None:
        logger.error(
            "Both --start and --end must be specified for segment transcription"
        )
        sys.exit(1)
    else:
        text = transcribe_audio(audio_file, args.model, args.output)

    if args.output is None:
        print("\n" + "=" * 50)
        print("TRANSCRIPTION:")
        print("=" * 50)
        print(text)
        print("=" * 50)


if __name__ == "__main__":
    main()
