"""
Module for handling audio segments based on markers.

This module provides functionality to create, manage, and navigate
audio segments based on existing markers in the audio file.
Each segment is defined by two consecutive markers.

The segment functionality works as follows:
- Segment 0: from marker0 to marker1
- Segment 1: from marker1 to marker2
- ...
- Segment N: from markerN to markerN+1
- Last segment: from last user marker to marker100

The implementation automatically recalculates segments when markers change
through the callback mechanism with the MarkerManager.
"""

import logging
from typing import List, Optional, Dict, Any
from .constants import END_TOLERANCE


logger = logging.getLogger(__name__)


class Segment:
    """
    Represents a single segment of an audio file defined by two consecutive markers.

    Attributes:
        index: The sequential number of the segment (0, 1, 2, ...)
        start_time: The start time in seconds based on the first marker of the segment
        end_time: The end time in seconds based on the second marker of the segment
        duration: The duration of the segment in seconds
        comment: A comment associated with the segment
        content: The content associated with the segment
    """

    def __init__(
        self,
        index: int,
        start_time: float,
        end_time: float,
        comment: str = "",
        content: str = "",
    ):
        """
        Initialize a Segment instance.

        Args:
            index: The sequential number of the segment
            start_time: The start time in seconds
            end_time: The end time in seconds
            comment: A comment associated with the segment
            content: The content associated with the segment
        """
        if start_time > end_time:
            raise ValueError(
                f"Start time ({start_time}) cannot be greater than end time ({end_time})"
            )

        self.index = index
        self.start_time = start_time
        self.end_time = end_time
        self.duration = end_time - start_time
        self.comment = comment
        self.content = content

    def __repr__(self) -> str:
        """String representation of the segment."""
        return (
            f"Segment(index={self.index}, start_time={self.start_time}, "
            f"end_time={self.end_time}, duration={self.duration}, "
            f"comment='{self.comment}', content='{self.content}')"
        )

    def contains_time(self, time: float) -> bool:
        """
        Check if the given time falls within this segment.

        Args:
            time: The time to check

        Returns:
            True if the time is within the segment, False otherwise
        """
        return self.start_time <= time <= self.end_time


class SegmentManager:
    """
    Manages the collection of segments and provides navigation functionality.

    This class calculates segments based on the current markers and provides
    methods to navigate between segments.
    """

    def __init__(self, marker_manager):
        """
        Initialize the SegmentManager.

        Args:
            marker_manager: Reference to the MarkerManager instance
        """
        self.marker_manager = marker_manager
        self.segments: List[Segment] = []
        self._calculate_segments()

        # Register callback to update segments when markers change
        # This assumes the MarkerManager has a method to register callbacks
        if hasattr(marker_manager, "register_marker_change_callback"):
            marker_manager.register_marker_change_callback(self._on_markers_changed)

    def _on_markers_changed(self) -> None:
        """Callback method when markers change."""
        self._calculate_segments()

    def _calculate_segments(self) -> None:
        """
        Calculate segments based on the current markers.

        Segments are calculated by pairing consecutive markers:
        - Segment 0: marker0 → marker1
        - Segment 1: marker1 → marker2
        - ...
        - Segment N: markerN → markerN+1
        """
        markers = self.marker_manager.markers

        sorted_markers = sorted(markers, key=lambda m: m["time"])

        existing_segments = self.segments
        self.segments = []

        if len(sorted_markers) < 2:
            logger.warning("Not enough markers to create segments")
            return

        used_old_segments = set()

        for i in range(len(sorted_markers) - 1):
            start_marker = sorted_markers[i]
            end_marker = sorted_markers[i + 1]

            comment = start_marker.get("comment", "")
            
            new_start_time = start_marker["time"]
            new_end_time = end_marker["time"]
            
            preserved_content = ""
            
            for j, old_seg in enumerate(existing_segments):
                if j in used_old_segments:
                    continue
                
                if old_seg.start_time == new_start_time and old_seg.end_time == new_end_time:
                    preserved_content = old_seg.content
                    used_old_segments.add(j)
                    logger.info(
                        f"Exact match for segment {i}: preserving content"
                    )
                    break
                
                if old_seg.start_time <= new_start_time < new_end_time <= old_seg.end_time:
                    if new_start_time == old_seg.start_time:
                        preserved_content = old_seg.content
                        used_old_segments.add(j)
                        logger.info(
                            f"Segment split: keeping content in left segment [{new_start_time}, {new_end_time}]"
                        )
                        break
            
            for j, old_seg in enumerate(existing_segments):
                if j in used_old_segments:
                    continue
                
                if old_seg.start_time == new_start_time:
                    for k, old_seg2 in enumerate(existing_segments):
                        if k in used_old_segments or k == j:
                            continue
                        
                        if old_seg2.end_time == new_end_time and old_seg.end_time == old_seg2.start_time:
                            merged_content_parts = []
                            if old_seg.content:
                                merged_content_parts.append(old_seg.content)
                            if old_seg2.content:
                                merged_content_parts.append(old_seg2.content)
                            preserved_content = "\n".join(merged_content_parts)
                            used_old_segments.add(j)
                            used_old_segments.add(k)
                            logger.info(
                                f"Segments merged: combining content from [{old_seg.start_time}, {old_seg.end_time}] and [{old_seg2.start_time}, {old_seg2.end_time}]"
                            )
                            break
            
            logger.info(
                f"Creating segment {i} from {start_marker['name']} to {end_marker['name']} with content: '{preserved_content[:50] if preserved_content else '(empty)'}...'"
            )

            segment = Segment(
                index=i,
                start_time=new_start_time,
                end_time=new_end_time,
                comment=comment,
                content=preserved_content,
            )

            self.segments.append(segment)

        logger.info(
            f"Calculated {len(self.segments)} segments from {len(sorted_markers)} markers"
        )

    def get_segments(self) -> List[Segment]:
        """
        Get the current list of segments.

        Returns:
            List of Segment objects
        """
        return self.segments.copy()

    def get_segment_count(self) -> int:
        """
        Get the total number of segments.

        Returns:
            Number of segments
        """
        return len(self.segments)

    def get_segment_by_index(self, index: int) -> Optional[Segment]:
        """
        Get the segment at the specified index.

        Args:
            index: The index of the segment to retrieve

        Returns:
            Segment object if found, None otherwise
        """
        if 0 <= index < len(self.segments):
            return self.segments[index]
        return None

    def get_segment_at_time(self, time: float) -> Optional[Segment]:
        """
        Get the segment that contains the given time.

        Args:
            time: The time to check

        Returns:
            Segment object if found, None otherwise
        """
        # Find all segments that contain the time
        containing_segments = []
        for segment in self.segments:
            if segment.contains_time(time):
                containing_segments.append(segment)

        # If no segments contain the time, return None
        if not containing_segments:
            return None

        # If multiple segments contain the time (e.g., at a boundary),
        # return the one with the higher index (later segment)
        return max(containing_segments, key=lambda s: s.index)

    def get_current_segment_index(self, current_time: float) -> Optional[int]:
        """
        Get the index of the segment at the current playback time.

        Args:
            current_time: The current playback time

        Returns:
            Index of the current segment if found, None otherwise
        """
        segment = self.get_segment_at_time(current_time)
        return segment.index if segment else None

    def get_next_segment(self, current_time: float) -> Optional[Segment]:
        """
        Get the next segment after the current time.

        Args:
            current_time: The current playback time

        Returns:
            Next Segment object if exists, None otherwise
        """
        current_segment = self.get_segment_at_time(current_time)
        if current_segment is None:
            # If current time is not in any segment, find where it would fit
            for i, segment in enumerate(self.segments):
                if current_time < segment.start_time:
                    # Current time is before this segment, so this is the next segment
                    return segment
            # Current time is after all segments
            return None

        # Return the next segment if it exists
        next_index = current_segment.index + 1
        return self.get_segment_by_index(next_index)

    def get_previous_segment(self, current_time: float) -> Optional[Segment]:
        """
        Get the previous segment before the current time.

        Args:
            current_time: The current playback time

        Returns:
            Previous Segment object if exists, None otherwise
        """
        current_segment = self.get_segment_at_time(current_time)
        if current_segment is None:
            # If current time is not in any segment, find where it would fit
            for i in range(len(self.segments) - 1, -1, -1):
                segment = self.segments[i]
                if current_time > segment.end_time:
                    # Current time is after this segment, so this is the previous segment
                    return segment
            # Current time is before all segments
            return None

        # Return the previous segment if it exists
        prev_index = current_segment.index - 1
        return self.get_segment_by_index(prev_index)

    def get_segment_start_time(self, index: int) -> Optional[float]:
        """
        Get the start time of the segment at the specified index.

        Args:
            index: The index of the segment

        Returns:
            Start time of the segment if found, None otherwise
        """
        segment = self.get_segment_by_index(index)
        return segment.start_time if segment else None

    def get_segment_end_time(self, index: int) -> Optional[float]:
        """
        Get the end time of the segment at the specified index.

        Args:
            index: The index of the segment

        Returns:
            End time of the segment if found, None otherwise
        """
        segment = self.get_segment_by_index(index)
        return segment.end_time if segment else None

    def get_segment_duration(self, index: int) -> Optional[float]:
        """
        Get the duration of the segment at the specified index.

        Args:
            index: The index of the segment

        Returns:
            Duration of the segment if found, None otherwise
        """
        segment = self.get_segment_by_index(index)
        return segment.duration if segment else None
