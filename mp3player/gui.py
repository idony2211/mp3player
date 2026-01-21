import tkinter as tk
from tkinter import filedialog, ttk
import logging
from typing import Optional
from .constants import (
    DEFAULT_GEOMETRY,
    CANVAS_HEIGHT,
    CANVAS_BG,
    CANVAS_OUTLINE,
    PROGRESS_COLOR,
    PROGRESS_HIGHLIGHT,
    INDICATOR_COLOR,
    TIME_FORMAT,
    UPDATE_INTERVAL,
)
from .marker_manager import MarkerManager

logger = logging.getLogger(__name__)


class GUIController:
    def __init__(self, player_instance):
        self.player = player_instance
        self.setup_gui()

    def setup_gui(self) -> None:
        self.player.root = tk.Tk()
        self.player.root.title("MP3 Player (MPV via IPC)")
        self.player.root.geometry(DEFAULT_GEOMETRY)

        # File selection
        file_frame = tk.Frame(self.player.root)
        file_frame.pack(pady=2)

        tk.Label(file_frame, text="Select MP3 File:").pack(side=tk.LEFT)
        self.player.file_button = tk.Button(
            file_frame, text="Browse", command=self.player.load_file, takefocus=False
        )
        self.player.file_button.pack(side=tk.LEFT, padx=2)
        self.player.file_label = tk.Label(
            file_frame, text="No file selected", wraplength=300
        )
        self.player.file_label.pack(side=tk.LEFT, padx=3)

        # Segment Player Control button (placed next to the file browser)
        self.player.segment_player_toggle_button = tk.Button(
            file_frame,
            text="Activate Segment Player",
            command=self.player.toggle_segment_player,
            takefocus=False,
            bg="#e6f3ff",
            font=("TkDefaultFont", 10, "bold"),
        )
        self.player.segment_player_toggle_button.pack(side=tk.LEFT, padx=5)

        # All controls in one row: -10s, -5s, -1s, play, +1s, +5s, +10s
        control_frame = tk.Frame(self.player.root)
        control_frame.pack(pady=3)

        # Add rewind buttons first: -10s, -5s, -1s
        self.player.rewind_buttons = []
        for seconds in [10, 5, 1]:
            btn = tk.Button(
                control_frame,
                text=f"-{seconds}s",
                command=lambda s=seconds: self.player.rewind(s),
                takefocus=False,
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.player.rewind_buttons.append(btn)

        # Add play button in the middle
        self.player.play_button = tk.Button(
            control_frame, text="Play", command=self.player.play_pause, takefocus=False
        )
        self.player.play_button.pack(side=tk.LEFT, padx=2)

        # Add fast forward buttons: +1s, +5s, +10s
        self.player.fast_forward_buttons = []
        for seconds in [1, 5, 10]:
            btn = tk.Button(
                control_frame,
                text=f"+{seconds}s",
                command=lambda s=seconds: self.player.fast_forward(s),
                takefocus=False,
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.player.fast_forward_buttons.append(btn)

        # Custom progress bar with progress indicator
        progress_frame = tk.Frame(self.player.root)
        progress_frame.pack(pady=1, fill=tk.X, padx=5)

        # Canvas for the progress bar
        self.player.progress_canvas = tk.Canvas(
            progress_frame,
            height=CANVAS_HEIGHT,
            bg=CANVAS_BG,
            relief=tk.FLAT,
            bd=1,
            highlightthickness=1,
            highlightbackground="#888888",
        )

        self.player.progress_canvas.pack(fill=tk.X)

        # Left-click to select marker, right-click to set marker time, double-click to seek
        self.player.progress_canvas.bind(
            "<Button-1>", self.player.on_canvas_click_marker_select
        )
        self.player.progress_canvas.bind(
            "<Double-Button-1>", self.player.on_canvas_double_click
        )
        self.player.progress_canvas.bind(
            "<Button-3>", self.player.on_canvas_right_click
        )

        # Time display
        time_frame = tk.Frame(self.player.root)
        time_frame.pack(pady=1)

        self.player.time_label = tk.Label(
            time_frame, text="00:00.00 / 00:00.00", font=("TkDefaultFont", 14, "bold")
        )
        self.player.time_label.pack()

        # Segment time frame
        segment_time_frame = tk.Frame(self.player.root)
        segment_time_frame.pack(pady=1)

        # Segment time display (shows relative time within the segment)
        self.player.segment_time_label = tk.Label(
            segment_time_frame,
            text="Segment time: 00:00.00",
            font=("TkDefaultFont", 10),
        )
        self.player.segment_time_label.pack()

        # Segment absolute time display (shows segment current time in the context of the entire MP3)
        self.player.segment_absolute_time_label = tk.Label(
            segment_time_frame,
            text="Segment absolute time: 00:00.00",
            font=("TkDefaultFont", 10),
        )
        self.player.segment_absolute_time_label.pack()

        # Time jump controls
        jump_frame = tk.Frame(self.player.root)
        jump_frame.pack(pady=2)

        tk.Label(jump_frame, text="Jump to:").pack(side=tk.LEFT)

        self.player.jump_minute_entry = tk.Entry(jump_frame, width=5, takefocus=False)
        self.player.jump_minute_entry.pack(side=tk.LEFT, padx=1)
        self.player.jump_minute_entry.bind(
            "<KeyRelease>", self.player.validate_time_input
        )
        self.player.jump_minute_entry.bind("<FocusIn>", self.player._on_any_widget_focus_in)
        self.player.jump_minute_entry.bind("<FocusOut>", self.player._on_any_widget_focus_out)

        tk.Label(jump_frame, text=":").pack(side=tk.LEFT)

        self.player.jump_second_entry = tk.Entry(jump_frame, width=5, takefocus=False)
        self.player.jump_second_entry.pack(side=tk.LEFT, padx=1)
        self.player.jump_second_entry.bind(
            "<KeyRelease>", self.player.validate_time_input
        )
        self.player.jump_second_entry.bind("<FocusIn>", self.player._on_any_widget_focus_in)
        self.player.jump_second_entry.bind("<FocusOut>", self.player._on_any_widget_focus_out)

        tk.Label(jump_frame, text=".").pack(side=tk.LEFT)

        self.player.jump_millisecond_entry = tk.Entry(
            jump_frame, width=6, takefocus=False
        )
        self.player.jump_millisecond_entry.pack(side=tk.LEFT, padx=1)
        self.player.jump_millisecond_entry.bind(
            "<KeyRelease>", self.player.validate_time_input
        )
        self.player.jump_millisecond_entry.bind("<FocusIn>", self.player._on_any_widget_focus_in)
        self.player.jump_millisecond_entry.bind("<FocusOut>", self.player._on_any_widget_focus_out)

        # Set default value for millisecond entry
        self.player.jump_millisecond_entry.insert(0, "00")

        self.player.jump_button = tk.Button(
            jump_frame,
            text="Jump To",
            command=self.player.jump_to_time,
            takefocus=False,
        )
        self.player.jump_button.pack(side=tk.LEFT, padx=5)

        # Speed controls
        speed_frame = tk.Frame(self.player.root)
        speed_frame.pack(pady=2)

        tk.Label(speed_frame, text="Speed:").pack(side=tk.LEFT)

        # Current speed display
        self.player.current_speed_label = tk.Label(
            speed_frame, text="1.0x", font=("TkDefaultFont", 10, "bold")
        )
        self.player.current_speed_label.pack(side=tk.LEFT, padx=(5, 0))

        speed_buttons_frame = tk.Frame(speed_frame)
        speed_buttons_frame.pack()

        self.player.speed_values = [0.5, 0.6, 0.7, 0.8, 1.0, 1.2, 1.5, 2.0, 2.2, 2.5, 3.0]

        for speed in self.player.speed_values:
            btn = tk.Button(
                speed_buttons_frame,
                text=f"{speed}x",
                command=lambda s=speed: self.player.set_speed(s),
                takefocus=False,
            )
            if speed == 1.0:
                btn.config(font=("TkDefaultFont", 12, "bold"), fg="blue")
            btn.pack(side=tk.LEFT, padx=2)

        # Status label
        self.player.status_label = tk.Label(
            self.player.root, text="Ready", bd=1, relief=tk.SUNKEN, anchor=tk.W
        )
        self.player.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        # Create a tabbed interface for marker management
        marker_notebook = ttk.Notebook(self.player.root)
        marker_notebook.pack(pady=2, fill=tk.BOTH, expand=True, padx=10)

        # Marker Controls tab
        marker_frame = tk.Frame(marker_notebook, padx=10, pady=5)
        marker_notebook.add(marker_frame, text="Markers")

        # Marker management controls
        marker_ctrl_frame = tk.Frame(marker_frame)
        marker_ctrl_frame.pack(fill=tk.X)

        # Get Current Time button
        self.player.get_current_time_button = tk.Button(
            marker_ctrl_frame,
            text="Get Current Time",
            command=self.player.get_current_time,
            takefocus=False,
        )
        self.player.get_current_time_button.pack(side=tk.LEFT, padx=(0, 5))

        # Get Segment Current Time button
        self.player.get_seg_current_time_button = tk.Button(
            marker_ctrl_frame,
            text="Get Seg Current Time",
            command=self.player.get_seg_current_time,
            takefocus=False,
        )
        self.player.get_seg_current_time_button.pack(side=tk.LEFT, padx=(0, 5))

        # Add marker button
        self.player.add_marker_button = tk.Button(
            marker_ctrl_frame,
            text="Add Marker",
            command=self.player.marker_manager.add_marker,
            takefocus=False,
        )
        self.player.add_marker_button.pack(side=tk.LEFT, padx=(0, 5))

        # Time input fields for precise marker positioning
        time_input_frame = tk.Frame(marker_ctrl_frame)
        time_input_frame.pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(time_input_frame, text="Marker Time:").pack()
        time_fields_frame = tk.Frame(time_input_frame)
        time_fields_frame.pack()

        self.player.marker_minute_entry = tk.Entry(
            time_fields_frame, width=5, takefocus=False
        )
        self.player.marker_minute_entry.pack(side=tk.LEFT, padx=(0, 2))
        self.player.marker_minute_entry.insert(0, "0")
        self.player.marker_minute_entry.bind(
            "<KeyRelease>", self.player.validate_time_input
        )
        self.player.marker_minute_entry.bind(
            "<FocusOut>", self.player.on_marker_time_change
        )
        self.player.marker_minute_entry.bind("<FocusIn>", self.player._on_any_widget_focus_in)
        self.player.marker_minute_entry.bind("<FocusOut>", self.player._on_any_widget_focus_out)
        tk.Label(time_fields_frame, text=":").pack(side=tk.LEFT)

        self.player.marker_second_entry = tk.Entry(
            time_fields_frame, width=5, takefocus=False
        )
        self.player.marker_second_entry.pack(side=tk.LEFT, padx=(0, 2))
        self.player.marker_second_entry.insert(0, "0")
        self.player.marker_second_entry.bind(
            "<KeyRelease>", self.player.validate_time_input
        )
        self.player.marker_second_entry.bind(
            "<FocusOut>", self.player.on_marker_time_change
        )
        self.player.marker_second_entry.bind("<FocusIn>", self.player._on_any_widget_focus_in)
        self.player.marker_second_entry.bind("<FocusOut>", self.player._on_any_widget_focus_out)
        tk.Label(time_fields_frame, text=".").pack(side=tk.LEFT)

        self.player.marker_millisecond_entry = tk.Entry(
            time_fields_frame, width=6, takefocus=False
        )
        self.player.marker_millisecond_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.player.marker_millisecond_entry.insert(0, "00")
        self.player.marker_millisecond_entry.bind(
            "<KeyRelease>", self.player.validate_time_input
        )
        self.player.marker_millisecond_entry.bind(
            "<FocusOut>", self.player.on_marker_time_change
        )
        self.player.marker_millisecond_entry.bind("<FocusIn>", self.player._on_any_widget_focus_in)
        self.player.marker_millisecond_entry.bind("<FocusOut>", self.player._on_any_widget_focus_out)

        # Time adjustment buttons
        time_adjust_frame = tk.Frame(time_input_frame)
        time_adjust_frame.pack()

        # Quick adjustment buttons: -30s, -20s, -10s, -5s, -1s, -0.5s, -0.3s, -0.2s, -0.1s, +0.1s, +0.2s, +0.3s, +0.5s, +1s, +5s, +10s, +20s, +30s
        # Large adjustments (red)
        btn_minus_30 = tk.Button(time_adjust_frame, text="-30s", takefocus=False, bg="#ffcccc")
        btn_minus_30.pack(side=tk.LEFT, padx=1)
        btn_minus_30.bind(
            "<ButtonPress-1>", lambda e: self.player.start_continuous_adjustment(-30.0)
        )
        btn_minus_30.bind(
            "<ButtonRelease-1>", lambda e: self.player.stop_continuous_adjustment()
        )

        btn_minus_20 = tk.Button(time_adjust_frame, text="-20s", takefocus=False, bg="#ffcccc")
        btn_minus_20.pack(side=tk.LEFT, padx=1)
        btn_minus_20.bind(
            "<ButtonPress-1>", lambda e: self.player.start_continuous_adjustment(-20.0)
        )
        btn_minus_20.bind(
            "<ButtonRelease-1>", lambda e: self.player.stop_continuous_adjustment()
        )

        btn_minus_10 = tk.Button(time_adjust_frame, text="-10s", takefocus=False, bg="#ffcccc")
        btn_minus_10.pack(side=tk.LEFT, padx=1)
        btn_minus_10.bind(
            "<ButtonPress-1>", lambda e: self.player.start_continuous_adjustment(-10.0)
        )
        btn_minus_10.bind(
            "<ButtonRelease-1>", lambda e: self.player.stop_continuous_adjustment()
        )

        # Medium-large adjustments (orange)
        btn_minus_5 = tk.Button(time_adjust_frame, text="-5s", takefocus=False, bg="#ffe5cc")
        btn_minus_5.pack(side=tk.LEFT, padx=1)
        btn_minus_5.bind(
            "<ButtonPress-1>", lambda e: self.player.start_continuous_adjustment(-5.0)
        )
        btn_minus_5.bind(
            "<ButtonRelease-1>", lambda e: self.player.stop_continuous_adjustment()
        )

        btn_minus_1 = tk.Button(time_adjust_frame, text="-1s", takefocus=False, bg="#ffe5cc")
        btn_minus_1.pack(side=tk.LEFT, padx=1)
        btn_minus_1.bind(
            "<ButtonPress-1>", lambda e: self.player.start_continuous_adjustment(-1.0)
        )
        btn_minus_1.bind(
            "<ButtonRelease-1>", lambda e: self.player.stop_continuous_adjustment()
        )

        # Fine adjustments (green)
        btn_minus_500ms = tk.Button(time_adjust_frame, text="-0.5s", takefocus=False, bg="#ccffcc")
        btn_minus_500ms.pack(side=tk.LEFT, padx=1)
        btn_minus_500ms.bind(
            "<Button-1>", lambda e: self.player.adjust_marker_time(-0.5)
        )

        btn_minus_300ms = tk.Button(time_adjust_frame, text="-0.3s", takefocus=False, bg="#ccffcc")
        btn_minus_300ms.pack(side=tk.LEFT, padx=1)
        btn_minus_300ms.bind(
            "<Button-1>", lambda e: self.player.adjust_marker_time(-0.3)
        )

        btn_minus_200ms = tk.Button(time_adjust_frame, text="-0.2s", takefocus=False, bg="#ccffcc")
        btn_minus_200ms.pack(side=tk.LEFT, padx=1)
        btn_minus_200ms.bind(
            "<Button-1>", lambda e: self.player.adjust_marker_time(-0.2)
        )

        btn_minus_100ms = tk.Button(time_adjust_frame, text="-0.1s", takefocus=False, bg="#ccffcc")
        btn_minus_100ms.pack(side=tk.LEFT, padx=1)
        btn_minus_100ms.bind(
            "<Button-1>", lambda e: self.player.adjust_marker_time(-0.1)
        )

        # Fine adjustments (green)
        btn_plus_100ms = tk.Button(time_adjust_frame, text="+0.1s", takefocus=False, bg="#ccffcc")
        btn_plus_100ms.pack(side=tk.LEFT, padx=1)
        btn_plus_100ms.bind("<Button-1>", lambda e: self.player.adjust_marker_time(0.1))

        btn_plus_200ms = tk.Button(time_adjust_frame, text="+0.2s", takefocus=False, bg="#ccffcc")
        btn_plus_200ms.pack(side=tk.LEFT, padx=1)
        btn_plus_200ms.bind("<Button-1>", lambda e: self.player.adjust_marker_time(0.2))

        btn_plus_300ms = tk.Button(time_adjust_frame, text="+0.3s", takefocus=False, bg="#ccffcc")
        btn_plus_300ms.pack(side=tk.LEFT, padx=1)
        btn_plus_300ms.bind("<Button-1>", lambda e: self.player.adjust_marker_time(0.3))

        btn_plus_500ms = tk.Button(time_adjust_frame, text="+0.5s", takefocus=False, bg="#ccffcc")
        btn_plus_500ms.pack(side=tk.LEFT, padx=1)
        btn_plus_500ms.bind("<Button-1>", lambda e: self.player.adjust_marker_time(0.5))

        # Medium-large adjustments (orange)
        btn_plus_1 = tk.Button(time_adjust_frame, text="+1s", takefocus=False, bg="#ffe5cc")
        btn_plus_1.pack(side=tk.LEFT, padx=1)
        btn_plus_1.bind(
            "<ButtonPress-1>", lambda e: self.player.start_continuous_adjustment(1.0)
        )
        btn_plus_1.bind(
            "<ButtonRelease-1>", lambda e: self.player.stop_continuous_adjustment()
        )

        btn_plus_5 = tk.Button(time_adjust_frame, text="+5s", takefocus=False, bg="#ffe5cc")
        btn_plus_5.pack(side=tk.LEFT, padx=1)
        btn_plus_5.bind(
            "<ButtonPress-1>", lambda e: self.player.start_continuous_adjustment(5.0)
        )
        btn_plus_5.bind(
            "<ButtonRelease-1>", lambda e: self.player.stop_continuous_adjustment()
        )

        # Large adjustments (red)
        btn_plus_10 = tk.Button(time_adjust_frame, text="+10s", takefocus=False, bg="#ffcccc")
        btn_plus_10.pack(side=tk.LEFT, padx=1)
        btn_plus_10.bind(
            "<ButtonPress-1>", lambda e: self.player.start_continuous_adjustment(10.0)
        )
        btn_plus_10.bind(
            "<ButtonRelease-1>", lambda e: self.player.stop_continuous_adjustment()
        )

        btn_plus_20 = tk.Button(time_adjust_frame, text="+20s", takefocus=False, bg="#ffcccc")
        btn_plus_20.pack(side=tk.LEFT, padx=1)
        btn_plus_20.bind(
            "<ButtonPress-1>", lambda e: self.player.start_continuous_adjustment(20.0)
        )
        btn_plus_20.bind(
            "<ButtonRelease-1>", lambda e: self.player.stop_continuous_adjustment()
        )

        btn_plus_30 = tk.Button(time_adjust_frame, text="+30s", takefocus=False, bg="#ffcccc")
        btn_plus_30.pack(side=tk.LEFT, padx=1)
        btn_plus_30.bind(
            "<ButtonPress-1>", lambda e: self.player.start_continuous_adjustment(30.0)
        )
        btn_plus_30.bind(
            "<ButtonRelease-1>", lambda e: self.player.stop_continuous_adjustment()
        )

        # Create frame for time-based marker buttons
        time_marker_frame = tk.Frame(time_input_frame)
        time_marker_frame.pack()

        # Add separate buttons for different functions
        tk.Button(
            time_marker_frame,
            text="Update Selected Marker",
            command=self.player.marker_manager.update_selected_marker_time,
            takefocus=False,
        ).pack(side=tk.LEFT)
        tk.Button(
            time_marker_frame,
            text="Preview",
            command=self.player.preview_marker_time,
            takefocus=False,
        ).pack(side=tk.LEFT, padx=(5, 0))

        # Add a label and entry for preview duration
        tk.Label(time_marker_frame, text="Duration (s):").pack(
            side=tk.LEFT, padx=(10, 0)
        )
        self.player.preview_duration_entry = tk.Entry(
            time_marker_frame, width=5, takefocus=False
        )
        self.player.preview_duration_entry.pack(side=tk.LEFT, padx=(2, 0))
        self.player.preview_duration_entry.insert(0, "8")  # Default value of 8 seconds
        self.player.preview_duration_entry.bind(
            "<KeyRelease>", self.player.validate_preview_duration
        )
        self.player.preview_duration_entry.bind(
            "<FocusOut>", self.player.validate_preview_duration
        )
        self.player.preview_duration_entry.bind("<FocusIn>", self.player._on_any_widget_focus_in)

        # Marker list and controls
        marker_list_frame = tk.Frame(marker_frame)
        marker_list_frame.pack(fill=tk.X, pady=(5, 0))

        # Marker listbox on the left
        listbox_frame = tk.Frame(marker_list_frame)
        listbox_frame.pack(side=tk.LEFT, fill=tk.Y)

        # Scrollbar for marker listbox
        marker_listbox_scrollbar = tk.Scrollbar(listbox_frame)
        marker_listbox_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Marker listbox with scrollbar
        self.player.marker_listbox = tk.Listbox(
            listbox_frame,
            height=8,
            font=("TkDefaultFont", 10),
            width=50,
            selectmode=tk.EXTENDED,
            yscrollcommand=marker_listbox_scrollbar.set,
        )
        self.player.marker_listbox.pack(side=tk.LEFT, fill=tk.Y)
        marker_listbox_scrollbar.config(command=self.player.marker_listbox.yview)

        # Bind click event for marker selection
        def _on_marker_select(event):
            self.player.marker_manager.on_marker_select(event)

        self.player.marker_listbox.bind("<<ListboxSelect>>", _on_marker_select)

        # Bind mousewheel for marker listbox scrolling
        def _on_marker_mousewheel(event):
            self.player.marker_listbox.yview_scroll(
                int(-1 * (event.delta / 120)), "units"
            )

        self.player.marker_listbox.bind("<MouseWheel>", _on_marker_mousewheel)

        # Marker listbox bindings for add/edit/delete functionality
        def _on_marker_double_click(event):
            selection = self.player.marker_listbox.curselection()
            if selection:
                idx = selection[0]
                if idx < len(self.player.marker_manager.markers):
                    marker = self.player.marker_manager.markers[idx]
                    if marker["name"] != "Marker0" and marker["name"] != "Marker500":
                        self.player.marker_manager.edit_marker_by_index(idx)

        self.player.marker_listbox.bind("<Double-Button-1>", _on_marker_double_click)

        # Marker button frame on the right
        marker_btn_frame = tk.Frame(marker_list_frame)
        marker_btn_frame.pack(side=tk.LEFT, padx=(10, 0))

        tk.Button(
            marker_btn_frame,
            text="Delete Selected",
            command=self.player.marker_manager.delete_selected_marker,
            takefocus=False,
        ).pack(fill=tk.X, pady=2)
        tk.Button(
            marker_btn_frame,
            text="Delete All",
            command=self.player.marker_manager.delete_all_markers,
            takefocus=False,
        ).pack(fill=tk.X, pady=2)
        tk.Button(
            marker_btn_frame,
            text="Select All",
            command=self.player.marker_manager.select_all_markers,
            takefocus=False,
        ).pack(fill=tk.X, pady=2)
        tk.Button(
            marker_btn_frame,
            text="Undo",
            command=self.player.marker_manager.undo_action,
            takefocus=False,
        ).pack(fill=tk.X, pady=2)
        tk.Button(
            marker_btn_frame,
            text="Redo",
            command=self.player.marker_manager.redo_action,
            takefocus=False,
        ).pack(fill=tk.X, pady=2)

        # Manual save configuration
        auto_save_frame = tk.Frame(marker_frame)
        auto_save_frame.pack(fill=tk.X, pady=(5, 0))

        tk.Label(auto_save_frame, text="Manual Save:").pack(anchor=tk.W)
        auto_save_config_frame = tk.Frame(auto_save_frame)
        auto_save_config_frame.pack(fill=tk.X)

        # Manual save button
        tk.Button(
            auto_save_config_frame,
            text="Save Markers",
            command=self.player.save_marker_data,
            takefocus=False,
        ).pack(side=tk.LEFT, padx=(5, 0))

        # Segments tab
        segments_frame = tk.Frame(marker_notebook, padx=5, pady=2)
        marker_notebook.add(segments_frame, text="Segments")

        # Segment timeline label and canvas (half width)
        segment_time_frame = tk.Frame(segments_frame)
        segment_time_frame.pack(fill=tk.X, pady=(0, 2))

        tk.Label(segment_time_frame, text="Timeline:").pack(anchor=tk.W)
        self.player.segment_time_canvas = tk.Canvas(
            segment_time_frame,
            height=25,
            width=1600,
            bg="#f0f0f0",
            relief=tk.FLAT,
            bd=1,
            highlightthickness=1,
            highlightbackground="#888888",
        )
        self.player.segment_time_canvas.pack(anchor=tk.W)

        # Bind click event for seeking within the selected segment
        self.player.segment_time_canvas.bind(
            "<Button-1>", self.player.on_segment_time_canvas_click
        )

        # Create a main frame to hold both the list and controls
        main_segment_frame = tk.Frame(segments_frame)
        main_segment_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(0, 0), ipady=50)

        # Segment list on the left
        list_frame = tk.Frame(main_segment_frame)
        list_frame.pack(side=tk.LEFT)

        tk.Label(list_frame, text="Segments:").pack(anchor=tk.W)
        self.player.segment_listbox = tk.Listbox(
            list_frame,
            height=25,
            font=("TkDefaultFont", 10),
            width=55,
            selectmode=tk.EXTENDED,
            exportselection=False,
        )
        self.player.segment_listbox.pack(side=tk.LEFT)

        def _on_segment_select(event):
            self.player.on_segment_select(event)

        self.player.segment_listbox.bind("<<ListboxSelect>>", _on_segment_select)

        # Bind mousewheel for segment listbox scrolling
        def _on_listbox_mousewheel(event):
            self.player.segment_listbox.yview_scroll(
                int(-1 * (event.delta / 120)), "units"
            )

        self.player.segment_listbox.bind("<MouseWheel>", _on_listbox_mousewheel)

        # Bind space key for segment listbox to prevent default selection toggle
        def _on_listbox_space(event):
            self.player.handle_space_key(event)
            return "break"

        self.player.segment_listbox.bind("<KeyPress-space>", _on_listbox_space)

        # Add scrollbar for segment list
        listbox_scrollbar = tk.Scrollbar(list_frame)
        listbox_scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.player.segment_listbox.config(yscrollcommand=listbox_scrollbar.set)
        listbox_scrollbar.config(command=self.player.segment_listbox.yview)

        # Controls on the right,贴着listbox
        controls_frame = tk.Frame(main_segment_frame)
        controls_frame.pack(side=tk.LEFT, padx=0)

        # Current playing segment label
        self.player.current_playing_segment_label_var = tk.StringVar()
        self.player.current_playing_segment_label_var.set("No segment playing")
        tk.Label(controls_frame, textvariable=self.player.current_playing_segment_label_var, 
                 font=("TkDefaultFont", 9, "bold"), fg="blue").pack(anchor=tk.W, pady=(0, 2))

        # Play/Pause Segment button
        self.player.segment_play_pause_button = tk.Button(
            controls_frame,
            text="Play Segment",
            command=self.player.toggle_segment_play_pause,
            takefocus=False,
        )
        self.player.segment_play_pause_button.pack(fill=tk.X, pady=1)

        # Seek Controls
        tk.Label(controls_frame, text="Seek:", font=("TkDefaultFont", 9, "bold")).pack(
            anchor=tk.W, pady=(2, 1)
        )

        seek_frame = tk.Frame(controls_frame)
        seek_frame.pack(fill=tk.X)

        self.player.back_5s_button = tk.Button(
            seek_frame,
            text="<5s",
            command=lambda: self.player.segment_player.seek_in_segment(-5),
            takefocus=False,
            font=("TkDefaultFont", 8),
            width=2,
        )
        self.player.back_5s_button.pack(side=tk.LEFT, padx=0)
        self.player.back_2s_button = tk.Button(
            seek_frame,
            text="<2s",
            command=lambda: self.player.segment_player.seek_in_segment(-2),
            takefocus=False,
            font=("TkDefaultFont", 8),
            width=2,
        )
        self.player.back_2s_button.pack(side=tk.LEFT, padx=0)
        self.player.back_1s_button = tk.Button(
            seek_frame,
            text="<1s",
            command=lambda: self.player.segment_player.seek_in_segment(-1),
            takefocus=False,
            font=("TkDefaultFont", 8),
            width=2,
        )
        self.player.back_1s_button.pack(side=tk.LEFT, padx=0)
        self.player.back_05s_button = tk.Button(
            seek_frame,
            text="<0.5s",
            command=lambda: self.player.segment_player.seek_in_segment(-0.5),
            takefocus=False,
            font=("TkDefaultFont", 8),
            width=2,
        )
        self.player.back_05s_button.pack(side=tk.LEFT, padx=(0, 1))

        self.player.fwd_05s_button = tk.Button(
            seek_frame,
            text="0.5s>",
            command=lambda: self.player.segment_player.seek_in_segment(0.5),
            takefocus=False,
            font=("TkDefaultFont", 8),
            width=2,
        )
        self.player.fwd_05s_button.pack(side=tk.LEFT, padx=1)
        self.player.fwd_1s_button = tk.Button(
            seek_frame,
            text="1s>",
            command=lambda: self.player.segment_player.seek_in_segment(1),
            takefocus=False,
            font=("TkDefaultFont", 8),
            width=2,
        )
        self.player.fwd_1s_button.pack(side=tk.LEFT, padx=0)
        self.player.fwd_2s_button = tk.Button(
            seek_frame,
            text="2s>",
            command=lambda: self.player.segment_player.seek_in_segment(2),
            takefocus=False,
            font=("TkDefaultFont", 8),
            width=2,
        )
        self.player.fwd_2s_button.pack(side=tk.LEFT, padx=0)
        self.player.fwd_5s_button = tk.Button(
            seek_frame,
            text="5s>",
            command=lambda: self.player.segment_player.seek_in_segment(5),
            takefocus=False,
            font=("TkDefaultFont", 8),
            width=2,
        )
        self.player.fwd_5s_button.pack(side=tk.LEFT, padx=0)

        # Segment Navigation
        tk.Label(controls_frame, text="Nav:", font=("TkDefaultFont", 9, "bold")).pack(
            anchor=tk.W, pady=(2, 1)
        )
        nav_frame = tk.Frame(controls_frame)
        nav_frame.pack(fill=tk.X)
        self.player.prev_seg_button = tk.Button(
            nav_frame,
            text="Prev",
            command=self.player.segment_player.previous_segment,
            takefocus=False,
        )
        self.player.prev_seg_button.pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 1)
        )
        self.player.next_seg_button = tk.Button(
            nav_frame,
            text="Next",
            command=self.player.segment_player.next_segment,
            takefocus=False,
        )
        self.player.next_seg_button.pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(1, 0)
        )

        # Repeat Settings
        tk.Label(
            controls_frame, text="Repeat:", font=("TkDefaultFont", 9, "bold")
        ).pack(anchor=tk.W, pady=(2, 1))

        settings_frame = tk.Frame(controls_frame)
        settings_frame.pack(fill=tk.X)

        tk.Label(settings_frame, text="Intervals:").grid(row=0, column=0, sticky="w")
        self.player.ri_entry = tk.Entry(settings_frame, width=4, takefocus=False)
        self.player.ri_entry.grid(row=0, column=1, sticky="w", padx=(2, 0))
        self.player.ri_entry.insert(0, "2")
        self.player.ri_entry.bind("<FocusIn>", self.player._on_any_widget_focus_in)
        self.player.ri_entry.bind("<FocusOut>", self.player._on_any_widget_focus_out)
        tk.Label(settings_frame, text="Times:").grid(row=1, column=0, sticky="w")
        self.player.rt_entry = tk.Entry(settings_frame, width=4, takefocus=False)
        self.player.rt_entry.grid(row=1, column=1, sticky="w", padx=(2, 0), pady=(1, 0))
        self.player.rt_entry.insert(0, "5")
        self.player.rt_entry.bind("<FocusIn>", self.player._on_any_widget_focus_in)
        self.player.rt_entry.bind("<FocusOut>", self.player._on_any_widget_focus_out)

        self.player.apply_repeat_button = tk.Button(
            settings_frame,
            text="Apply",
            command=self.player.apply_repeat_settings,
            takefocus=False,
        )
        self.player.apply_repeat_button.grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(3, 0)
        )

        # Apply default repeat settings on startup
        self.player.apply_repeat_settings()

        # Export Segments button
        self.player.export_segments_button = tk.Button(
            controls_frame,
            text="Export Segments",
            command=self.player.export_segments,
            takefocus=False,
        )
        self.player.export_segments_button.pack(fill=tk.X, pady=(5, 0))

        # Export Segment MDs button
        self.player.export_segment_mds_button = tk.Button(
            controls_frame,
            text="Export Segment MDs",
            command=self.player.export_segment_mds,
            takefocus=False,
        )
        self.player.export_segment_mds_button.pack(fill=tk.X, pady=(5, 0))

        # Framework on the right of controls with border
        extra_frame = tk.Frame(segments_frame, bd=2, relief=tk.RIDGE)
        extra_frame.pack(side=tk.RIGHT, fill=tk.Y, expand=True)

        self.player.transcription_segment_label = tk.StringVar(value="Transcription")
        tk.Label(
            extra_frame,
            textvariable=self.player.transcription_segment_label,
            font=("TkDefaultFont", 9, "bold"),
            fg="darkgreen",
        ).pack(anchor=tk.W, padx=5, pady=0)

        # Transcribe button and segment selector on the same row
        transcribe_segment_frame = tk.Frame(extra_frame)
        transcribe_segment_frame.pack(fill=tk.X, padx=5, pady=(0, 2))

        self.player.transcribe_button = tk.Button(
            transcribe_segment_frame,
            text="Transcribe",
            command=self.player.transcribe_segment,
            takefocus=False,
        )
        self.player.transcribe_button.pack(side=tk.LEFT, padx=(0, 5))

        tk.Label(transcribe_segment_frame, text="Segment:", font=("TkDefaultFont", 9)).pack(side=tk.LEFT)

        self.player.segment_selector = ttk.Combobox(
            transcribe_segment_frame,
            state="readonly",
            width=45,
        )
        self.player.segment_selector.pack(side=tk.LEFT, padx=(5, 0))
        self.player.segment_selector.bind("<<ComboboxSelected>>", self.player.on_segment_selector_changed)
        # Initialize segment selector with current segments
        self.player.update_segment_selector()

        # Content buttons frame
        content_buttons_frame = tk.Frame(extra_frame)
        content_buttons_frame.pack(fill=tk.X, padx=5, pady=(0, 2))

        # Show Content button
        self.player.show_content_button = tk.Button(
            content_buttons_frame,
            text="Show Content",
            command=self.player.show_restored_content,
            takefocus=False,
        )
        self.player.show_content_button.pack(side=tk.LEFT, padx=(0, 2))

        # Copy Content button
        self.player.copy_content_button = tk.Button(
            content_buttons_frame,
            text="Copy Content",
            command=lambda: [
                self.player.root.clipboard_append(
                    self.player.transcription_text.get(1.0, tk.END).strip()
                ),
                self.player.status_label.config(text="Content copied to clipboard")
            ],
            takefocus=False,
        )
        self.player.copy_content_button.pack(side=tk.LEFT, padx=(0, 2))

        # Save Content button
        self.player.save_content_button = tk.Button(
            content_buttons_frame,
            text="Save Content",
            command=self.player.save_transcription,
            takefocus=False,
        )
        self.player.save_content_button.pack(side=tk.LEFT)

        # Export LRC button
        self.player.export_lrc_button = tk.Button(
            content_buttons_frame,
            text="Export LRC",
            command=self.player.export_segments_to_lrc,
            takefocus=False,
        )
        self.player.export_lrc_button.pack(side=tk.LEFT, padx=(5, 0))

        # Transcription status label
        self.player.transcription_status = tk.StringVar(value="")
        self.player.transcription_status_label = tk.Label(
            content_buttons_frame,
            textvariable=self.player.transcription_status,
            font=("TkDefaultFont", 8),
            fg="blue",
            wraplength=150,
        )
        self.player.transcription_status_label.pack(side=tk.LEFT, padx=(10, 0))

        # Transcription text display
        transcription_frame = tk.Frame(extra_frame)
        transcription_frame.pack(
            fill=tk.BOTH, expand=True, padx=5, pady=(0, 5), ipady=20
        )

        transcription_scrollbar = tk.Scrollbar(transcription_frame)
        transcription_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.player.transcription_text = tk.Text(
            transcription_frame,
            height=25,
            width=120,
            font=("TkDefaultFont", 16),
            wrap=tk.WORD,
            yscrollcommand=transcription_scrollbar.set,
        )
        self.player.transcription_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        transcription_scrollbar.config(command=self.player.transcription_text.yview)

        self.player.transcription_text.bind(
            "<FocusIn>", self.player._on_transcription_focus_in
        )
        self.player.transcription_text.bind(
            "<FocusOut>", self.player._on_transcription_focus_out
        )



        # Bind 'Ctrl+o' key to browse files
        self.player.root.bind("<Control-o>", lambda event: self.player.key_load_file())

        # Bind space key to play segment when no input has focus
        self.player.root.bind("<KeyPress-space>", self.player.handle_space_key)

        # Bind Ctrl+S to save transcription
        self.player.root.bind('<Control-s>', lambda e: self.player.save_transcription())

        # Bind window close event to our cleanup function
        self.player.root.protocol("WM_DELETE_WINDOW", self.player.on_closing)

        # Initialize GUI ready flag to avoid logging initial resize events
        self.player.gui_initialized = False
        # Schedule setting the flag after GUI is fully initialized
        self.player.root.after(
            500, lambda: setattr(self.player, "gui_initialized", True)
        )

        self.player.segment_player._disable_segment_controls()

        if hasattr(self.player, "segment_listbox"):
            self.player.segment_listbox.focus_set()
