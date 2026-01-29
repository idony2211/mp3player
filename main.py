#!/usr/bin/env python3
"""
Main entry point for the MP3 Player application.

This file serves as the main entry point for the application.
The actual implementation is now modularized in the mp3player package.
"""

import os
import sys
import logging

os.environ["TORCH_LOAD_WEIGHTS_ONLY"] = "False"
os.environ["HF_HUB_DISABLE_XDG_CACHE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Respect HF_HUB_OFFLINE_OVERRIDE if set (this must be done before importing faster_whisper_transcriber)
if os.environ.get("HF_HUB_OFFLINE_OVERRIDE") is not None:
    os.environ["HF_HUB_OFFLINE"] = os.environ["HF_HUB_OFFLINE_OVERRIDE"]
else:
    os.environ["HF_HUB_OFFLINE"] = "1"

# os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from mp3player.player import MP3Player
from mp3player.utils import setup_logging

# Set up logging to file
setup_logging()

logger = logging.getLogger(__name__)
logger.info(f"Python executable: {sys.executable}")
logger.info(f"Python version: {sys.version}")
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"Command line arguments: {sys.argv}")
logger.info(f"PATH: {os.environ.get('PATH', 'Not set')[:100]}...")
logger.info(f"VIRTUAL_ENV: {os.environ.get('VIRTUAL_ENV', 'Not set')}")

if __name__ == "__main__":
    logger.info("Starting MP3 Player application")
    player = MP3Player()
    player.run()
