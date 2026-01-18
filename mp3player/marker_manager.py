import tkinter as tk
import tkinter.messagebox as tkmsg
import logging
from typing import Optional, List, Dict, Any, Callable
from .constants import END_TOLERANCE, TIME_FORMAT

logger = logging.getLogger(__name__)


class MarkerManager:
    def __init__(self, player_instance):
        self.player = player_instance
        # Marker variables
        self.markers: List[
            Dict[str, Any]
        ] = []  # List of markers [{'time': float, 'name': str}]
        self.max_markers: int = 100

        # Undo/Redo functionality
        self.undo_stack: List[Dict[str, Any]] = []  # Stack of operations for undo
        self.redo_stack: List[Dict[str, Any]] = []  # Stack of operations for redo
        self.max_history: int = 50  # Maximum number of operations to keep in history

        # Currently selected marker index
        self.selected_marker_index: Optional[int] = None

        # Callbacks for when markers change
        self.marker_change_callbacks: List[Callable[[], None]] = []

    def register_marker_change_callback(self, callback: Callable[[], None]) -> None:
        """
        Register a callback function to be called when markers change.

        Args:
            callback: A function to be called when markers change
        """
        self.marker_change_callbacks.append(callback)

    def _trigger_marker_change_callbacks(self) -> None:
        """Trigger all registered callbacks when markers change."""
        for callback in self.marker_change_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in marker change callback: {e}")

    def add_marker(self) -> None:
        """Add a marker at the preview marker time if available, otherwise at the current playback position."""
        logger.info(f"Add marker button clicked. markers count: {len(self.markers)}")
        
        if not self.player.current_file:
            logger.warning("No file loaded, cannot add marker")
            self.player.status_label.config(text="No file loaded")
            return

        logger.info(f"Current markers: {[m['name'] for m in self.markers]}")

        if len(self.markers) >= self.max_markers:
            logger.warning(f"Maximum number of markers ({self.max_markers}) reached")
            self.player.status_label.config(
                text=f"Maximum markers reached: {self.max_markers}"
            )
            return

        # Determine marker time
        if (
            hasattr(self.player, "_preview_marker_time")
            and self.player._preview_marker_time is not None
        ):
            marker_time = self.player._preview_marker_time
            logger.info(f"Using preview marker time: {self.player.format_time(marker_time)}")
        else:
            # Try to parse time from input fields
            minute_str = self.player.marker_minute_entry.get().strip()
            second_str = self.player.marker_second_entry.get().strip()
            millisecond_str = self.player.marker_millisecond_entry.get().strip()
            
            logger.info(f"Time input fields: minute='{minute_str}', second='{second_str}', centisecond='{millisecond_str}'")

            # Check if any time input has been entered
            has_meaningful_input = (
                (minute_str and minute_str != "0")
                or (second_str and second_str != "0")
                or (millisecond_str and millisecond_str != "00")
            )
            has_any_input = bool(minute_str or second_str or millisecond_str)

            try:
                minutes = int(minute_str) if minute_str else 0
                seconds = int(second_str) if second_str else 0
                centiseconds = int(millisecond_str) if millisecond_str else 0

                # Calculate total time in seconds (centiseconds / 100.0)
                total_seconds = minutes * 60 + seconds + centiseconds / 100.0

                # If no meaningful time input and no preview marker time, use current playback position
                if not has_meaningful_input:
                    marker_time = self.player.current_pos
                    logger.info(f"No meaningful time input, using current playback position: {self.player.format_time(marker_time)}")
                else:
                    marker_time = total_seconds
            except ValueError:
                # If there's a parsing error and no preview time, use current position
                marker_time = self.player.current_pos
                logger.info(f"Time parsing error, using current playback position: {self.player.format_time(marker_time)}")

        logger.info(f"Final marker_time: {self.player.format_time(marker_time)}")

        # Validate time is within file duration tolerance
        if (
            self.player.duration > 0
            and marker_time > self.player.duration - END_TOLERANCE
        ):
            logger.warning(
                f"Cannot set marker beyond file duration minus tolerance ({END_TOLERANCE}s)"
            )
            self.player.status_label.config(
                text=f"Time exceeds valid range (max: {self.player.format_time(self.player.duration - END_TOLERANCE)})"
            )
            return

        # Check if there's already a marker within 1 second of the specified time
        for existing_marker in self.markers:
            # Skip fixed markers (Marker0 and Marker500) when checking for 1-second restriction
            if (
                existing_marker["name"] == "Marker0"
                or existing_marker["name"] == "Marker500"
            ):
                continue
            if abs(existing_marker["time"] - marker_time) < 1.0:
                # There's already a marker within 1 second, show error message
                logger.warning(
                    f"Cannot add marker within 1 second of existing marker at {self.player.format_time(existing_marker['time'])}"
                )
                self.player.status_label.config(
                    text=f"Cannot add marker within 1 second of existing marker at {self.player.format_time(existing_marker['time'])}"
                )
                return

        # Ensure marker isn't placed at exactly 0:00.000 (where Marker0 is fixed)
        if abs(marker_time) < 0.001:  # If time is very close to 0.0 (0:00.000)
            # Ensure this marker is placed slightly after 0.0 so it doesn't conflict with Marker0
            marker_time = 0.001  # Set to 1 millisecond after start

        # Create marker with temporary name initially
        new_marker = {
            "time": marker_time,
            "name": "TempMarker",  # Temporary name, will be renumbered after adding
            "comment": "",  # Add comment field
            "content": "",  # Add content field
        }

        # Add to list and sort by time
        self.markers.append(new_marker)
        self.markers.sort(key=lambda m: m["time"])

        # Renumber all user markers based on their position in the timeline
        self._renumber_user_markers()

        # Clear the preview marker time when a marker is added
        if hasattr(self.player, "_preview_marker_time"):
            delattr(self.player, "_preview_marker_time")

        # Update UI
        self.update_marker_list()
        self.player.update_segment_list()  # Update segment list as well
        self.player.redraw_progress_display()

        # Select the newly added marker
        new_marker_index = self.markers.index(new_marker)
        self.selected_marker_index = new_marker_index
        self.player.marker_listbox.selection_clear(0, tk.END)
        self.player.marker_listbox.selection_set(new_marker_index)
        self.player.marker_listbox.see(new_marker_index)

        # Trigger callbacks for marker changes
        self._trigger_marker_change_callbacks()

        logger.info(f"Added marker at {self.player.format_time(new_marker['time'])}")
        self.player.status_label.config(
            text=f"Added marker at {self.player.format_time(new_marker['time'])}"
        )

    def delete_selected_marker(self) -> None:
        """Delete the currently selected markers with confirmation."""
        selection = self.player.marker_listbox.curselection()
        if not selection:
            logger.info("No marker selected for deletion")
            self.player.status_label.config(text="Please select a marker to delete")
            return

        # Collect markers to delete (excluding protected markers)
        markers_to_delete = []
        for idx in selection:
            if idx < len(self.markers):
                marker = self.markers[idx]
                if marker["name"] != "Marker0" and marker["name"] != "Marker500":
                    markers_to_delete.append((idx, marker))

        if not markers_to_delete:
            logger.warning("All selected markers are protected")
            self.player.status_label.config(text="Selected markers are protected")
            return

        if len(markers_to_delete) == 1:
            marker_name = markers_to_delete[0][1]["name"]
            marker_time = markers_to_delete[0][1]["time"]
            if not tkmsg.askyesno(
                "Confirm Deletion",
                f"Are you sure you want to delete the marker: {marker_name}?",
            ):
                return
        else:
            if not tkmsg.askyesno(
                "Confirm Deletion",
                f"Are you sure you want to delete {len(markers_to_delete)} markers?",
            ):
                return

        # Sort by index in descending order to delete from end to avoid index shifting issues
        markers_to_delete.sort(key=lambda x: x[0], reverse=True)

        # Store operation in undo stack
        undo_data = {
            "action": "delete_markers",
            "markers_data": [m[1] for m in markers_to_delete],
        }
        self.push_to_undo_stack(undo_data)

        # Delete markers from end to start to preserve indices
        for idx, marker in markers_to_delete:
            del self.markers[idx]
            logger.info(f"Deleted marker {marker['name']}")

        # Renumber user markers (Marker0 and Marker500 are preserved)
        self._renumber_user_markers()

        # Update UI
        self.update_marker_list()
        self.player.update_segment_list()
        self.player.redraw_progress_display()

        # Trigger callbacks for marker changes
        self._trigger_marker_change_callbacks()

        self.player.status_label.config(
            text=f"Deleted {len(markers_to_delete)} markers"
        )

    def delete_all_markers(self) -> None:
        """Delete all user markers with confirmation, preserving fixed markers."""
        # Filter out fixed markers (Marker0 and Marker500) to preserve them
        user_markers = [
            marker
            for marker in self.markers
            if marker["name"] != "Marker0" and marker["name"] != "Marker500"
        ]

        if not user_markers:
            logger.info("No user markers to delete")
            self.player.status_label.config(text="No user markers to delete")
            return

        # Show confirmation dialog
        if not tkmsg.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete all {len(user_markers)} user markers? (Fixed markers will be preserved)",
        ):
            return

        # Store operation in undo stack - backup all markers including fixed ones
        markers_backup = [marker.copy() for marker in self.markers]

        self.push_to_undo_stack(
            {
                "action": "delete_all_markers",
                "markers_data": markers_backup,
            }
        )

        # Preserve fixed markers and clear only user markers
        fixed_markers = [
            marker
            for marker in self.markers
            if marker["name"] == "Marker0" or marker["name"] == "Marker500"
        ]
        self.markers = fixed_markers

        # Update UI
        self.update_marker_list()
        self.player.update_segment_list()  # Update segment list as well
        self.player.redraw_progress_display()

        # Trigger callbacks for marker changes
        self._trigger_marker_change_callbacks()

        self.player.status_label.config(
            text="All user markers deleted (fixed markers preserved)"
        )
        logger.info("All user markers deleted (fixed markers preserved)")

        # Auto-save functionality has been removed

    def select_all_markers(self) -> None:
        """Select all markers in the listbox."""
        self.player.marker_listbox.selection_clear(0, tk.END)
        selected_count = 0
        for i, marker in enumerate(self.markers):
            # Skip fixed markers (Marker0 and Marker500)
            if marker["name"] != "Marker0" and marker["name"] != "Marker500":
                self.player.marker_listbox.selection_set(i)
                selected_count += 1

        self.player.status_label.config(
            text=f"Selected {selected_count} markers (fixed markers excluded)"
        )

    def on_marker_select(self, event) -> None:
        """Handle marker selection in the listbox."""
        selection = self.player.marker_listbox.curselection()
        if selection:
            idx = selection[0]
            marker = self.markers[idx]

            # Check if the selected marker is a fixed marker (Marker0 or Marker500)
            if marker["name"] == "Marker0" or marker["name"] == "Marker500":
                # Deselect the fixed marker
                self.player.marker_listbox.selection_clear(idx)
                self.player.status_label.config(
                    text=f"Cannot select fixed marker: {marker['name']}"
                )
                return

            self.selected_marker_index = idx
            self.player.status_label.config(
                text=f"Selected marker at {self.player.format_time(marker['time'])}"
            )

            # Populate time input fields with the selected marker's time
            total_seconds = int(marker["time"])
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            centiseconds = round((marker["time"] - total_seconds) * 100)

            self.player.marker_minute_entry.delete(0, tk.END)
            self.player.marker_minute_entry.insert(0, str(minutes))

            self.player.marker_second_entry.delete(0, tk.END)
            self.player.marker_second_entry.insert(0, str(seconds))

            self.player.marker_millisecond_entry.delete(0, tk.END)
            self.player.marker_millisecond_entry.insert(0, f"{centiseconds:02d}")

            # Update the preview line
            self.player.on_marker_time_change()

    def update_marker_list(self) -> None:
        """Update the marker listbox with current markers."""
        try:
            # Store the currently selected index to restore it after updating
            current_selection = self.player.marker_listbox.curselection()

            self.player.marker_listbox.delete(0, tk.END)
            for i, marker in enumerate(self.markers):
                # Determine marker name based on its position
                marker_name = self._get_dynamically_named_marker(marker)
                display_text = (
                    f"{marker_name}: {self.player.format_time(marker['time'])}"
                )
                self.player.marker_listbox.insert(tk.END, display_text)

                # Highlight fixed markers (Marker0 and Marker500) differently
                if marker["name"] == "Marker0" or marker["name"] == "Marker500":
                    # Make the background color different for fixed markers and disable selection
                    self.player.marker_listbox.itemconfig(
                        tk.END,
                        {
                            "bg": "#e6f3ff",
                            "fg": "#0066cc",
                            "selectbackground": "#e6f3ff",
                            "selectforeground": "#0066cc",
                        },
                    )

            # Restore the selection if there was one
            if (
                self.selected_marker_index is not None
                and self.selected_marker_index < self.player.marker_listbox.size()
            ):
                self.player.marker_listbox.selection_clear(
                    0, tk.END
                )  # Clear any existing selection
                self.player.marker_listbox.selection_set(
                    self.selected_marker_index
                )  # Select the marker
                self.player.marker_listbox.see(
                    self.selected_marker_index
                )  # Ensure it's visible
        except Exception as e:
            # Fallback to original behavior if there's an error
            logger.error(f"Error updating marker list: {e}")
            self.player.marker_listbox.delete(0, tk.END)  # Clear anyway
            for i, marker in enumerate(self.markers):
                self.player.marker_listbox.insert(
                    tk.END,
                    f"{marker['name']}: {self.player.format_time(marker['time'])}",
                )

    def _get_dynamically_named_marker(self, marker) -> str:
        """Get the marker's name based on its position in the audio file."""
        # Return the actual name stored in the marker
        # Fixed markers have specific names, user markers have number-based names
        return marker["name"]

    def _get_marker_name_by_position(self, ratio: float) -> str:
        """Get the marker name based on its position in the audio file."""
        if ratio <= 0.01:  # Very close to start
            return "Marker0"
        elif ratio >= 0.99:  # Very close to end
            return "Marker500"
        else:
            # Map ratios to appropriate names based on proximity to start/end
            if ratio <= 0.1:  # Closer to start
                return f"MarkerSmall"
            elif ratio >= 0.9:  # Closer to end
                return f"MarkerLarge"
            else:  # Middle region
                return f"MarkerMid"

    def _renumber_user_markers(self) -> None:
        """Renumber user-created markers based on their position in the timeline."""
        # Get all non-fixed markers (not Marker0 or Marker500)
        user_markers = []
        fixed_markers = []

        for marker in self.markers:
            if marker["name"] == "Marker0" or marker["name"] == "Marker500":
                fixed_markers.append(marker)
            else:
                user_markers.append(marker)

        # Sort user markers by time
        user_markers.sort(key=lambda m: m["time"])

        # Assign numbers 1, 2, 3... to user markers based on position
        for i, marker in enumerate(user_markers):
            marker["name"] = f"Marker{i + 1}"

        # Rebuild the markers list with all markers sorted by time
        all_markers = user_markers + fixed_markers
        all_markers.sort(key=lambda m: m["time"])

        # Update the markers list
        self.markers = all_markers

        # Trigger callbacks for marker changes
        self._trigger_marker_change_callbacks()

        # Update segment list as well since markers have changed
        self.player.update_segment_list()

    def push_to_undo_stack(self, operation: Dict[str, Any]) -> None:
        """Push an operation to the undo stack and manage history size."""
        self.undo_stack.append(operation)

        # Limit undo stack size
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)  # Remove oldest item if exceeding max

        # Clear redo stack when a new operation is performed
        self.redo_stack.clear()

    def undo_action(self) -> None:
        """Undo the last action."""
        if not self.undo_stack:
            self.player.status_label.config(text="Nothing to undo")
            return

        # Get the last operation
        operation = self.undo_stack.pop()
        self.redo_stack.append(operation)  # Add to redo stack

        # Execute the undo operation
        if operation["action"] == "move_marker":
            original_time = operation["from_time"]
            marker_idx = operation["index"]
            if marker_idx < len(self.markers):
                self.markers[marker_idx]["time"] = original_time
                self.markers.sort(key=lambda m: m["time"])  # Re-sort markers by time

                # If this marker was selected, update the time fields
                if self.selected_marker_index == marker_idx:
                    total_seconds = int(original_time)
                    minutes = total_seconds // 60
                    seconds = total_seconds % 60
                    milliseconds = int((original_time - total_seconds) * 1000)

                    self.player.marker_minute_entry.delete(0, tk.END)
                    self.player.marker_minute_entry.insert(0, str(minutes))

                    self.player.marker_second_entry.delete(0, tk.END)
                    self.player.marker_second_entry.insert(0, str(seconds))

                    self.player.marker_millisecond_entry.delete(0, tk.END)
                    self.player.marker_millisecond_entry.insert(
                        0, f"{milliseconds:03d}"
                    )

                # Update UI
                self.update_marker_list()
                self.player.update_segment_list()  # Update segment list as well
                self.player.redraw_progress_display()

                # Trigger callbacks for marker changes
                self._trigger_marker_change_callbacks()

                self.player.status_label.config(
                    text=f"Undo: Moved marker back to {self.player.format_time(original_time)}"
                )
        elif operation["action"] == "add_marker":
            # Find and remove the marker by its time and name (since it was added)
            marker_to_remove = operation["marker_data"]
            for i, marker in enumerate(self.markers):
                if (
                    abs(marker["time"] - marker_to_remove["time"]) < 0.001
                    and marker["name"] == marker_to_remove["name"]
                ):
                    del self.markers[i]
                    break

            self.markers.sort(key=lambda m: m["time"])  # Re-sort markers by time

            # Renumber all user markers based on their position in the timeline
            self._renumber_user_markers()

            # Update UI
            self.update_marker_list()
            self.player.update_segment_list()  # Update segment list as well
            self.player.redraw_progress_display()

            # Trigger callbacks for marker changes
            self._trigger_marker_change_callbacks()

            self.player.status_label.config(text="Undo: Removed marker")
        elif operation["action"] == "delete_marker":
            # Re-insert the deleted marker
            marker_data = operation["marker_data"]
            self.markers.insert(operation["index"], marker_data)
            self.markers.sort(key=lambda m: m["time"])  # Re-sort markers by time

            # Update UI
            self.update_marker_list()
            self.player.update_segment_list()  # Update segment list as well
            self.player.redraw_progress_display()

            # Trigger callbacks for marker changes
            self._trigger_marker_change_callbacks()

            self.player.status_label.config(
                text=f"Undo: Restored marker at {self.player.format_time(marker_data['time'])}"
            )
        elif operation["action"] == "delete_all_markers":
            # Restore all deleted markers
            self.markers = [marker.copy() for marker in operation["markers_data"]]

            # Update UI
            self.update_marker_list()
            self.player.update_segment_list()  # Update segment list as well
            self.player.redraw_progress_display()

            # Trigger callbacks for marker changes
            self._trigger_marker_change_callbacks()

            self.player.status_label.config(
                text=f"Undo: Restored {len(self.markers)} markers"
            )

        # Also save immediately to ensure changes are saved
        self.player.save_marker_data()
        # Schedule the next auto-save if the player has this method
        if hasattr(self.player, "schedule_next_auto_save"):
            self.player.schedule_next_auto_save()

    def redo_action(self) -> None:
        """Redo the last undone action."""
        if not self.redo_stack:
            self.player.status_label.config(text="Nothing to redo")
            return

        # Get the last undone operation
        operation = self.redo_stack.pop()
        self.undo_stack.append(operation)  # Add back to undo stack

        # Execute the redo operation
        if operation["action"] == "move_marker":
            new_time = operation["to_time"]
            marker_idx = operation["index"]
            if marker_idx < len(self.markers):
                self.markers[marker_idx]["time"] = new_time
                self.markers.sort(key=lambda m: m["time"])  # Re-sort markers by time

                # If this marker was selected, update the time fields
                if self.selected_marker_index == marker_idx:
                    total_seconds = int(new_time)
                    minutes = total_seconds // 60
                    seconds = total_seconds % 60
                    milliseconds = int((new_time - total_seconds) * 1000)

                    self.player.marker_minute_entry.delete(0, tk.END)
                    self.player.marker_minute_entry.insert(0, str(minutes))

                    self.player.marker_second_entry.delete(0, tk.END)
                    self.player.marker_second_entry.insert(0, str(seconds))

                    self.player.marker_millisecond_entry.delete(0, tk.END)
                    self.player.marker_millisecond_entry.insert(
                        0, f"{milliseconds:03d}"
                    )

                # Update UI
                self.update_marker_list()
                self.player.update_segment_list()  # Update segment list as well
                self.player.redraw_progress_display()

                # Trigger callbacks for marker changes
                self._trigger_marker_change_callbacks()

                self.player.status_label.config(
                    text=f"Redo: Moved marker to {self.player.format_time(new_time)}"
                )
        elif operation["action"] == "add_marker":
            # Re-add the marker
            marker_data = operation["marker_data"]
            self.markers.append(marker_data)
            self.markers.sort(key=lambda m: m["time"])  # Re-sort markers by time

            # Renumber all user markers based on their position in the timeline
            self._renumber_user_markers()

            # Update UI
            self.update_marker_list()
            self.player.update_segment_list()  # Update segment list as well
            self.player.redraw_progress_display()

            # Trigger callbacks for marker changes
            self._trigger_marker_change_callbacks()

            self.player.status_label.config(text="Redo: Added marker")
        elif operation["action"] == "delete_marker":
            # Re-delete the marker
            marker_idx = operation["index"]
            if marker_idx < len(self.markers):
                del self.markers[marker_idx]
                self.markers.sort(key=lambda m: m["time"])  # Re-sort markers by time

                # Update UI
                self.update_marker_list()
                self.player.update_segment_list()  # Update segment list as well
                self.player.redraw_progress_display()

                # Trigger callbacks for marker changes
                self._trigger_marker_change_callbacks()

                self.player.status_label.config(text="Redo: Removed marker")
        elif operation["action"] == "delete_all_markers":
            # Re-delete all markers
            self.markers.clear()

            # Update UI
            self.update_marker_list()
            self.player.update_segment_list()  # Update segment list as well
            self.player.redraw_progress_display()

            # Trigger callbacks for marker changes
            self._trigger_marker_change_callbacks()

            self.player.status_label.config(text="Redo: Cleared all markers")

        # Also save immediately to ensure changes are saved
        self.player.save_marker_data()
        # Schedule the next auto-save if the player has this method
        if hasattr(self.player, "schedule_next_auto_save"):
            self.player.schedule_next_auto_save()

    def add_marker_at_time(self) -> None:
        """Add a new marker at the specified time from input fields."""
        if not self.player.current_file:
            logger.warning("No file loaded, cannot add marker at time")
            self.player.status_label.config(text="No file loaded")
            return

        if len(self.markers) >= self.max_markers:
            logger.warning(f"Maximum number of markers ({self.max_markers}) reached")
            self.player.status_label.config(
                text=f"Maximum markers reached: {self.max_markers}"
            )
            return

        try:
            # Parse time from input fields
            minute_str = self.player.marker_minute_entry.get().strip()
            second_str = self.player.marker_second_entry.get().strip()
            millisecond_str = self.player.marker_millisecond_entry.get().strip()

            minutes = int(minute_str) if minute_str else 0
            seconds = int(second_str) if second_str else 0
            centiseconds = int(millisecond_str) if millisecond_str else 0

            # Calculate total time in seconds (centiseconds / 100.0)
            total_seconds = minutes * 60 + seconds + centiseconds / 100.0

            # Validate time is within file duration tolerance
            if (
                self.player.duration > 0
                and total_seconds > self.player.duration - END_TOLERANCE
            ):
                logger.warning(
                    f"Cannot set marker beyond file duration minus tolerance ({END_TOLERANCE}s)"
                )
                self.player.status_label.config(
                    text=f"Time exceeds valid range (max: {self.player.format_time(self.player.duration - END_TOLERANCE)})"
                )
                return

            # Check if there's already a marker within 1 second of the specified time
            for existing_marker in self.markers:
                # Skip fixed markers (Marker0 and Marker500) when checking for 1-second restriction
                if (
                    existing_marker["name"] == "Marker0"
                    or existing_marker["name"] == "Marker500"
                ):
                    continue
                if abs(existing_marker["time"] - total_seconds) < 1.0:
                    # There's already a marker within 1 second, show error message
                    logger.warning(
                        f"Cannot add marker within 1 second of existing marker at {self.player.format_time(existing_marker['time'])}"
                    )
                    self.player.status_label.config(
                        text=f"Cannot add marker within 1 second of existing marker at {self.player.format_time(existing_marker['time'])}"
                    )
                    return

            # Ensure marker isn't placed at exactly 0:00.000 (where Marker0 is fixed)
            marker_time = total_seconds
            if abs(marker_time) < 0.001:  # If time is very close to 0.0 (0:00.000)
                # Ensure this marker is placed slightly after 0.0 so it doesn't conflict with Marker0
                marker_time = 0.001  # Set to 1 millisecond after start

            # Create marker with temporary name initially
            new_marker = {
                "time": marker_time,
                "name": "TempMarker",  # Temporary name, will be renumbered after adding
                "comment": "",  # Add comment field
                "content": "",  # Add content field
            }

            # Add to list and sort by time
            self.markers.append(new_marker)
            self.markers.sort(key=lambda m: m["time"])

            # Renumber all user markers based on their position in the timeline
            self._renumber_user_markers()

            # Find the new index after sorting and renumbering
            self.selected_marker_index = self.markers.index(new_marker)

            # Store operation in undo stack with the resolved index
            self.push_to_undo_stack(
                {
                    "action": "add_marker",
                    "index": self.selected_marker_index,
                    "marker_data": new_marker.copy(),
                }
            )

            # Clear the preview marker time when a marker is added
            if hasattr(self.player, "_preview_marker_time"):
                delattr(self.player, "_preview_marker_time")

            # Update UI
            self.update_marker_list()
            self.player.update_segment_list()  # Update segment list as well
            self.player.redraw_progress_display()

            # Trigger callbacks for marker changes
            self._trigger_marker_change_callbacks()

            logger.info(f"Added marker at {self.player.format_time(total_seconds)}")
            self.player.status_label.config(
                text=f"Added marker at {self.player.format_time(total_seconds)}"
            )

            # Auto-save functionality has been removed
        except ValueError:
            logger.error("Invalid time format entered")
            self.player.status_label.config(
                text="Invalid time format. Enter numbers only."
            )

    def jump_to_next_marker(self) -> None:
        """Jump to the next marker in the timeline."""
        if not self.player.current_file or not self.markers:
            self.player.status_label.config(
                text="No file loaded or no markers available"
            )
            return

        # Find the next marker after the current playback position
        sorted_markers = sorted(self.markers, key=lambda m: m["time"])
        next_marker = None
        next_marker_index = -1

        for i, marker in enumerate(sorted_markers):
            if marker["time"] > self.player.current_pos:
                next_marker = marker
                next_marker_index = i
                break

        if next_marker:
            # Jump to the next marker position
            logger.info(
                f"Jumping to next marker at {self.player.format_time(next_marker['time'])}"
            )
            response = self.player.send_command_with_retry(
                {"command": ["seek", next_marker["time"], "absolute"]}
            )
            logger.info(f"Seek to next marker response: {response}")

            self.player.current_pos = next_marker["time"]
            self.player.update_time_display()
            self.player.redraw_progress_display()

            # Select the marker in the listbox
            self.selected_marker_index = next_marker_index
            self.update_marker_list()

            # Select the marker in the listbox
            if (
                self.selected_marker_index is not None
                and self.selected_marker_index < self.player.marker_listbox.size()
            ):
                self.player.marker_listbox.selection_clear(
                    0, tk.END
                )  # Clear any existing selection
                self.player.marker_listbox.selection_set(
                    self.selected_marker_index
                )  # Select the marker
                self.player.marker_listbox.see(
                    self.selected_marker_index
                )  # Ensure it's visible

            self.player.status_label.config(
                text=f"Jumped to next marker at {self.player.format_time(next_marker['time'])}"
            )
        else:
            self.player.status_label.config(text="No next marker found")

    def jump_to_previous_marker(self) -> None:
        """Jump to the previous marker in the timeline."""
        if not self.player.current_file or not self.markers:
            self.player.status_label.config(
                text="No file loaded or no markers available"
            )
            return

        # Find the previous marker before the current playback position
        sorted_markers = sorted(self.markers, key=lambda m: m["time"])
        prev_marker = None
        prev_marker_index = -1

        # Iterate in reverse order to find the previous marker
        for i in range(len(sorted_markers) - 1, -1, -1):
            marker = sorted_markers[i]
            if marker["time"] < self.player.current_pos:
                prev_marker = marker
                prev_marker_index = i
                break

        if prev_marker:
            # Jump to the previous marker position
            logger.info(
                f"Jumping to previous marker at {self.player.format_time(prev_marker['time'])}"
            )
            response = self.player.send_command_with_retry(
                {"command": ["seek", prev_marker["time"], "absolute"]}
            )
            logger.info(f"Seek to previous marker response: {response}")

            self.player.current_pos = prev_marker["time"]
            self.player.update_time_display()
            self.player.redraw_progress_display()

            # Select the marker in the listbox
            self.selected_marker_index = prev_marker_index
            self.update_marker_list()

            # Select the marker in the listbox
            if (
                self.selected_marker_index is not None
                and self.selected_marker_index < self.player.marker_listbox.size()
            ):
                self.player.marker_listbox.selection_clear(
                    0, tk.END
                )  # Clear any existing selection
                self.player.marker_listbox.selection_set(
                    self.selected_marker_index
                )  # Select the marker
                self.player.marker_listbox.see(
                    self.selected_marker_index
                )  # Ensure it's visible

            self.player.status_label.config(
                text=f"Jumped to previous marker at {self.player.format_time(prev_marker['time'])}"
            )
        else:
            self.player.status_label.config(text="No previous marker found")

    def delete_nearest_marker(self) -> None:
        """Delete the nearest marker to the current playback position."""
        if not self.player.current_file or not self.markers:
            self.player.status_label.config(
                text="No file loaded or no markers available"
            )
            return

        # Find the nearest marker to the current position
        nearest_marker = None
        min_distance = float("inf")

        for i, marker in enumerate(self.markers):
            distance = abs(marker["time"] - self.player.current_pos)
            if distance < min_distance:
                min_distance = distance
                nearest_marker = (i, marker)

        if nearest_marker:
            marker_idx, marker = nearest_marker

            # Check if the nearest marker is a protected fixed marker (marker0 or marker100)
            marker_name = marker["name"]
            if marker_name == "Marker0" or marker_name == "Marker500":
                logger.warning(f"Cannot delete protected marker: {marker_name}")
                self.player.status_label.config(
                    text=f"Cannot delete protected marker: {marker_name}"
                )
                return

            # Show confirmation dialog
            if not tkmsg.askyesno(
                "Confirm Deletion",
                f"Delete nearest marker '{marker_name}' at {self.player.format_time(marker['time'])}?",
            ):
                return

            # Store operation in undo stack
            self.push_to_undo_stack(
                {
                    "action": "delete_marker",
                    "index": marker_idx,
                    "marker_data": marker.copy(),
                }
            )

            # Remove the marker
            del self.markers[marker_idx]

            # Update UI
            self.update_marker_list()
            self.player.update_segment_list()  # Update segment list as well
            self.player.redraw_progress_display()

            # Trigger callbacks for marker changes
            self._trigger_marker_change_callbacks()

            logger.info(
                f"Deleted nearest marker at {self.player.format_time(marker['time'])}"
            )
            self.player.status_label.config(
                text=f"Deleted nearest marker at {self.player.format_time(marker['time'])}"
            )

            # Auto-save functionality has been removed
        else:
            self.player.status_label.config(text="No markers to delete")

    def update_selected_marker_time(self) -> None:
        """Update the time of the currently selected marker to the specified time."""
        if not self.player.current_file:
            logger.warning("No file loaded, cannot update marker time")
            self.player.status_label.config(text="No file loaded")
            return

        # Check if a marker is selected
        if self.selected_marker_index is None or self.selected_marker_index >= len(
            self.markers
        ):
            self.player.status_label.config(text="Please select a marker first")
            return

        try:
            # Parse time from input fields
            minute_str = self.player.marker_minute_entry.get().strip()
            second_str = self.player.marker_second_entry.get().strip()
            millisecond_str = self.player.marker_millisecond_entry.get().strip()

            minutes = int(minute_str) if minute_str else 0
            seconds = int(second_str) if second_str else 0
            centiseconds = int(millisecond_str) if millisecond_str else 0

            # Calculate total time in seconds (centiseconds / 100.0)
            total_seconds = minutes * 60 + seconds + centiseconds / 100.0

            # Validate time is within file duration tolerance
            if (
                self.player.duration > 0
                and total_seconds > self.player.duration - END_TOLERANCE
            ):
                logger.warning(
                    f"Cannot set marker beyond file duration minus tolerance ({END_TOLERANCE}s)"
                )
                self.player.status_label.config(
                    text=f"Time exceeds valid range (max: {self.player.format_time(self.player.duration - END_TOLERANCE)})"
                )
                return

            # Check if there's already a marker within 1 second of the specified time
            for existing_marker in self.markers:
                # Skip the marker we're updating and fixed markers when checking for 1-second restriction
                if (
                    existing_marker == self.markers[self.selected_marker_index]
                    or existing_marker["name"] == "Marker0"
                    or existing_marker["name"] == "Marker500"
                ):
                    continue
                if abs(existing_marker["time"] - total_seconds) < 1.0:
                    # There's already a marker within 1 second, show error message
                    logger.warning(
                        f"Cannot update marker within 1 second of existing marker at {self.player.format_time(existing_marker['time'])}"
                    )
                    self.player.status_label.config(
                        text=f"Cannot update marker within 1 second of existing marker at {self.player.format_time(existing_marker['time'])}"
                    )
                    return

            # Get current marker
            original_time = self.markers[self.selected_marker_index]["time"]
            new_time = total_seconds

            # Ensure time doesn't go below 0.001 to avoid conflict with Marker0 at exactly 0:00.000
            if new_time < 0.001:
                new_time = 0.001

            # Store operation in undo stack
            self.push_to_undo_stack(
                {
                    "action": "move_marker",
                    "index": self.selected_marker_index,
                    "from_time": original_time,
                    "to_time": new_time,
                }
            )

            # Store the marker reference before updating
            marker_to_update = self.markers[self.selected_marker_index]

            # Update the marker time
            marker_to_update["time"] = new_time
            self.markers.sort(key=lambda m: m["time"])  # Re-sort markers by time

            # Find the new index after sorting
            self.selected_marker_index = self.markers.index(marker_to_update)

            # Clear the preview marker time when a marker is updated
            if hasattr(self.player, "_preview_marker_time"):
                delattr(self.player, "_preview_marker_time")

            # Trigger callbacks for marker changes first to recalculate segments
            self._trigger_marker_change_callbacks()

            # Update UI - only update the listbox selection and redraw progress
            self.update_marker_list()  # This is needed to maintain proper listbox selection after sorting
            self.player.update_segment_list()  # Update segment list as well
            self.player.redraw_progress_display()

            # Force UI update to ensure segment list is refreshed immediately
            self.player.root.update_idletasks()

            logger.info(
                f"Updated marker from {self.player.format_time(original_time)} to {self.player.format_time(new_time)}"
            )
            self.player.status_label.config(
                text=f"Updated marker to {self.player.format_time(new_time)}"
            )

            # Auto-save functionality has been removed
        except ValueError:
            logger.error("Invalid time format entered")
            self.player.status_label.config(
                text="Invalid time format. Enter numbers only."
            )

    def edit_marker_by_index(self, idx: int) -> None:
        """Select the marker at the given index for editing."""
        if idx < 0 or idx >= len(self.markers):
            return

        marker = self.markers[idx]
        self.selected_marker_index = idx

        total_seconds = int(marker["time"])
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        centiseconds = round((marker["time"] - total_seconds) * 100)

        self.player.marker_minute_entry.delete(0, tk.END)
        self.player.marker_minute_entry.insert(0, str(minutes))

        self.player.marker_second_entry.delete(0, tk.END)
        self.player.marker_second_entry.insert(0, str(seconds))

        self.player.marker_millisecond_entry.delete(0, tk.END)
        self.player.marker_millisecond_entry.insert(0, f"{centiseconds:02d}")

        # Update the preview line
        self.player.on_marker_time_change()

        self.player.status_label.config(
            text=f"Editing {marker['name']} at {self.player.format_time(marker['time'])}"
        )

    def adjust_marker_time(self, time_delta: float) -> None:
        """Adjust the marker time display by the specified delta (in seconds)."""
        try:
            minute_str = self.player.marker_minute_entry.get().strip()
            second_str = self.player.marker_second_entry.get().strip()
            centisecond_str = self.player.marker_millisecond_entry.get().strip()

            minutes = int(minute_str) if minute_str else 0
            seconds = int(second_str) if second_str else 0
            centiseconds = int(centisecond_str) if centisecond_str else 0

            current_displayed_time = minutes * 60 + seconds + centiseconds / 100.0
        except ValueError:
            current_displayed_time = 0.0

        new_time = max(0, current_displayed_time + time_delta)
        if new_time < 0.001:
            new_time = 0.001

        if self.player.duration > 0:
            new_time = min(new_time, self.player.duration - END_TOLERANCE)

        total_seconds = int(new_time)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        centiseconds = round((new_time - total_seconds) * 100)

        self.player.marker_minute_entry.delete(0, tk.END)
        self.player.marker_minute_entry.insert(0, str(minutes))

        self.player.marker_second_entry.delete(0, tk.END)
        self.player.marker_second_entry.insert(0, str(seconds))

        self.player.marker_millisecond_entry.delete(0, tk.END)
        self.player.marker_millisecond_entry.insert(0, f"{centiseconds:02d}")

        # Update the preview line
        self.player.on_marker_time_change()

        self.player.status_label.config(
            text=f"Display updated: {self.player.format_time(new_time)}"
        )
