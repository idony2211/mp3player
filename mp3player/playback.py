import subprocess
import time
import json
import socket
import logging
import os
from typing import Optional, Dict, Any
import tkinter as tk

logger = logging.getLogger(__name__)

class PlaybackController:
    def __init__(self, player_instance):
        self.player = player_instance
        self.process: Optional[subprocess.Popen] = None
        self.ipc_socket_path: Optional[str] = None
        
        # Legacy segment playback variables (for backward compatibility)
        self.segment_start: float = 0.0
        self.segment_end: float = 0.0
        self.segment_enabled: bool = False
        self.is_in_segment_playback: bool = False

    def start_playback(self) -> None:
        """Start playback using mpv with IPC socket."""
        logger.info("Starting mpv playback with IPC")

        import random
        # Use a more predictable temporary path
        self.ipc_socket_path = f'/tmp/mpv_ipc_{random.randint(10000, 99999)}'
        logger.info(f"IPC socket path: {self.ipc_socket_path}")

        cmd = [
            'mpv',
            '--no-video',
            f'--input-ipc-server={self.ipc_socket_path}',
            '--idle=yes',  # Keep mpv running when playback ends
            '--really-quiet',
            '--pause=yes',  # Start paused, then we'll play via IPC
            '--input-terminal=no'  # Disable terminal input handling
        ]

        cmd.append(self.player.current_file)
        logger.info(f"Running command: {' '.join(cmd)}")

        try:
            # Start mpv as a child process, ensuring it gets killed when parent dies
            self.process = subprocess.Popen(cmd, preexec_fn=os.setsid)
            logger.info(f"Started mpv process with PID: {self.process.pid}")
        except Exception as e:
            logger.error(f"Error starting mpv process: {e}")
            return

        # Wait for the socket file to be created
        max_wait = 10  # seconds
        waited = 0
        logger.info("Waiting for IPC socket to be created...")

        while waited < max_wait and not os.path.exists(self.ipc_socket_path):
            time.sleep(0.1)
            waited += 0.1

        if os.path.exists(self.ipc_socket_path):
            logger.info(f"IPC socket created at {self.ipc_socket_path} after {waited:.1f} seconds")
        else:
            logger.error(f"IPC socket was not created within {max_wait} seconds")

    def send_command(self, command: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send a command to mpv via the IPC socket."""
        if not self.ipc_socket_path or not os.path.exists(self.ipc_socket_path):
            logger.debug(f"Cannot send command, IPC socket not available: {self.ipc_socket_path}")
            return None

        try:
            logger.debug(f"Sending command: {command}")

            # Create a Unix domain socket with a timeout to prevent hanging
            client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client_socket.settimeout(2.0)  # 2 second timeout for connections
            client_socket.connect(self.ipc_socket_path)

            # Send the command as JSON
            command_json = json.dumps(command) + '\n'
            client_socket.send(command_json.encode('utf-8'))

            # Receive response - since mpv should send complete responses with newlines,
            # we can implement a more efficient reading method
            response = b""
            while b'\n' not in response:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                response += chunk

            client_socket.close()

            # Parse the response
            response_str = response.decode('utf-8').strip()
            if response_str:
                parsed_response = json.loads(response_str)
                logger.debug(f"Command response: {parsed_response}")
                return parsed_response
            else:
                logger.debug("Empty response received")
                return {"error": "empty_response"}

        except socket.timeout:
            logger.error("IPC command timed out")
            try:
                client_socket.close()
            except:
                pass  # Socket might already be closed
            return {"error": "socket_timeout"}
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            try:
                client_socket.close()
            except:
                pass  # Socket might already be closed
            return {"error": str(e)}

    def send_command_with_retry(self, command: Dict[str, Any], max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """Send a command to mpv with retry logic."""
        for attempt in range(max_retries):
            response = self.send_command(command)

            # Check if command was successful
            if response and 'error' in response and response['error'] != 'success':
                if response['error'] == 'property unavailable' or 'error running command' in str(response['error']):
                    logger.warning(f"Command failed on attempt {attempt + 1}, retrying... Error: {response['error']}")
                    time.sleep(0.5)  # Wait before retrying
                    continue
                else:
                    # Some other error, don't retry
                    return response
            else:
                # Success
                return response

        logger.error(f"Command failed after {max_retries} attempts: {command}")
        return {"error": f"failed after {max_retries} attempts"}

    def set_segment_start(self) -> None:
        """Set the start time of the segment to the current playback position."""
        if not self.player.current_file:
            logger.warning("No file loaded, cannot set segment start")
            self.player.status_label.config(text="No file loaded")
            return

        self.segment_start = self.player.current_pos
        self.player.segment_start_label.config(text=self.player.format_time(self.segment_start))
        logger.info(f"Segment start set to: {self.player.format_time(self.segment_start)}")

        # Update progress display to show segment
        self.player.redraw_progress_display()

        # Update status
        self.player.status_label.config(text=f"Segment start set to {self.player.format_time(self.segment_start)}")

    def set_segment_end(self) -> None:
        """Set the end time of the segment to the current playback position."""
        if not self.player.current_file:
            logger.warning("No file loaded, cannot set segment end")
            self.player.status_label.config(text="No file loaded")
            return

        # Validate that end is after start
        if self.player.current_pos <= self.segment_start:
            logger.warning(f"End time {self.player.format_time(self.player.current_pos)} must be after start time {self.player.format_time(self.segment_start)}")
            self.player.status_label.config(text="End must be after start")
            return

        self.segment_end = self.player.current_pos
        self.player.segment_end_label.config(text=self.player.format_time(self.segment_end))
        logger.info(f"Segment end set to: {self.player.format_time(self.segment_end)}")

        # Update progress display to show segment
        self.player.redraw_progress_display()

        # Update status
        self.player.status_label.config(text=f"Segment end set to {self.player.format_time(self.segment_end)}")

    def on_loop_count_change(self, event=None) -> None:
        """Handle change in loop count selection."""
        selected = self.player.loop_var.get()
        if selected == "1x":
            self.player.loop_count = 1
        elif selected == "2x":
            self.player.loop_count = 2
        elif selected == "3x":
            self.player.loop_count = 3
        elif selected == "3x":
            self.player.loop_count = 3
        elif selected == "4x":
            self.player.loop_count = 4
        elif selected == "5x":
            self.player.loop_count = 5
        elif selected == "∞":
            self.player.loop_count = -1  # Infinite loop
        logger.info(f"Loop count set to: {self.player.loop_count}")

    def play_segment(self) -> None:
        """Start playback of the defined segment."""
        if not self.player.current_file:
            logger.warning("No file loaded, cannot play segment")
            self.player.status_label.config(text="No file loaded")
            return

        if self.segment_start >= self.segment_end:
            logger.warning("Invalid segment: start time must be before end time")
            self.player.status_label.config(text="Invalid segment: set start before end")
            return

        # Enable segment playback
        self.segment_enabled = True
        self.player.current_loop = 0
        self.is_in_segment_playback = True

        # If not already playing, start playback
        if not self.player.is_playing:
            self.player.play_pause()

        # Seek to the start of the segment
        logger.info(f"Playing segment from {self.player.format_time(self.segment_start)} to {self.player.format_time(self.segment_end)}")
        response = self.send_command_with_retry({"command": ["seek", self.segment_start, "absolute"]})
        logger.info(f"Seek to segment start response: {response}")

        # Update UI
        self.player.segment_play_button.config(text="Playing...")
        self.player.status_label.config(text=f"Playing segment: {self.player.format_time(self.segment_start)} - {self.player.format_time(self.segment_end)}, Loop {self.player.current_loop + 1}/{self.player.loop_count if self.player.loop_count != -1 else '∞'}")

    def clear_segment(self) -> None:
        """Clear the current segment and disable segment mode."""
        self.segment_start = 0.0
        self.segment_end = 0.0
        self.player.current_loop = 0
        self.is_in_segment_playback = False

        # Reset UI elements
        self.player.segment_start_label.config(text="00:00.00")
        self.player.segment_end_label.config(text="00:00.00")
        self.player.segment_play_button.config(text="Play Segment")
        self.player.loop_var.set("1x")
        self.player.loop_count = 1

        # Update progress display
        self.player.redraw_progress_display()

        self.player.status_label.config(text="Segment cleared")
        logger.info("Segment cleared")