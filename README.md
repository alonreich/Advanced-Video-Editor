# ==============================================================================
# PROJECT GOAL: SMART GPU-ACCELERATED VIDEO EDITING APPLICATION
# TARGET: PYTHON / DESKTOP (GPU-ENABLED)
# ==============================================================================

1.  PURPOSE
    The application delivers an advanced desktop video editing environment that 
    enforces deterministic timeline behavior and leverages pure hardware GPU 
    acceleration for all non-destructive editing workflows.

2.  PRIMARY GOALS & SUCCESS CRITERIA
    The system provides real-time editing performance via hardware-specific 
    [cite_start]encoders while preventing invalid timeline states by design [cite: 32-36]. 
    Success is defined by zero timeline corruption and a keyboard-first workflow 
    [cite_start]that minimizes user friction [cite: 176-178].

3.  TARGET USERS
    Designed for technical content creators and power editors who require 
    high-performance rendering, absolute predictability in clip placement, 
    and a streamlined, professional-grade interface.

4.  TIMELINE & LANE MANAGEMENT
    The interface initializes with two lanes, utilizing a vertical scrollbar 
    for expansion beyond four lanes. Clips are treated as solid objects and 
    are strictly forbidden from overlapping within the same lane; any collision 
    [cite_start]physically blocks movement and triggers a visual "Blocked" warning [cite: 512-514].

5.  MAGNETIC SNAPPING & GAP DETECTION
    Magnetic snapping is absolute, with the playhead receiving 2x magnetism (40px) 
    to ensure frame-perfect alignment. Upon clip deletion, the system highlights 
    the created gap in red and prompts the user via a Metallic Dark Green/Red 
    [cite_start]dialog to decide whether to ripple shift clips or leave the hole [cite: 494-496, 61].

6.  HARDWARE GPU ACCELERATION
    The engine auto-detects hardware-specific encoders (h264_nvenc, h264_qsv, 
    or h264_amf) to offload all rendering and effects processing from the CPU 
    [cite_start][cite: 32-36]. This ensures smooth, real-time playback even with complex 
    filter graphs.

7.  AUDIO & VOICEOVER INTEGRATION
    Media components appear as a single unified box on the timeline; audio 
    waveforms are hidden until the user explicitly chooses "Split Audio & Video" 
    via the context menu. Voiceover recording is triggered by the 'V' key, 
    inserting audio at the playhead.

8.  ADVANCED NAVIGATION & SHORTCUTS
    Implemented shortcuts: Ctrl+K for track splitting, '[' for start-trim, 
    ']' for end-trim, and 'C' for entering interactive Crop mode. Navigation 
    [cite_start]uses arrow keys for frame stepping and Ctrl+Arrow for aggressive seeking [cite: 497-498].

9.  DATA SAFETY & CRASH RECOVERY
    The system maintains a 50-step undo history and utilizes continuous 
    background auto-saving to project files. A global exception hook manages 
    recovery by attempting to restore state from an emergency sidecar log 
    [cite_start]during fatal crashes [cite: 1-2].

10. VISUAL INSPECTOR & PROJECT SETTINGS
    A dedicated Clip Inspector manages metadata, speed, and volume. The 
    application supports switching between Landscape and Portrait modes, with 
    out-of-bounds media rendered at 50% transparency for editing clarity 
    [cite_start][cite: 169-170, 266-267].

11. FIFO PROJECT MANAGEMENT
    The system enforces a strict 10-project storage limit, automatically 
    [cite_start]nuking the oldest directory using FIFO logic to prevent drive saturation [cite: 338-340].

12. SMART HISTORY COMPRESSION
    The UndoStack utilizes delta-based "Smart Push" logic to store only 
    granular modifications, preventing memory bloat during high-intensity 
    [cite_start]editing sessions [cite: 117-120].

13. UIPI ELEVATION WORKAROUND
    Implements user32.dll message filters to ensure drag-and-drop functionality 
    remains operational even if the process is running with elevated Admin 
    [cite_start]privileges [cite: 2-3].

14. HARDWARE-ACCELERATED THUMBNAILING
    The ThumbnailWorker hijacks CUDA or QSV hardware to offload preview 
    [cite_start]generation [cite: 556-557], ensuring the UI remains responsive while 
    importing large media batches.

15. OCCLUSION-AWARE RENDERING
    The FilterGraphGenerator calculates clip layering to skip rendering 
    visual data that is 100% occluded by clips on higher tracks, maximizing throughput.

16. INTERACTIVE VISUAL TRANSFORMS
    A SafeOverlay provides direct on-preview handles for real-time manipulation 
    [cite_start]of clip scale, position, and crop parameters with center-snapping guides [cite: 268-271, 295].

17. AUTOMATIC DLL PATCHING
    The BinaryManager automatically clones libmpv-2.dll to mpv-1.dll on boot 
    [cite_start]to resolve Windows-specific backend compatibility issues [cite: 27-28].

18. VERTICAL VIEW SYNCHRONIZATION
    The TimelineContainer enforces strict vertical alignment between track 
    headers and the viewport, maintaining integrity across all 50 possible lanes.

19. EMERGENCY SIDECAR LOGGING
    Critical failures trigger an immediate state dump to project.sidecar.json, 
    allowing for the deterministic recovery of the user's work.

20. THROTTLED BACKGROUND TASKS
    During active playback, background proxy generation is throttled to a 
    single low-priority thread to prioritize the real-time preview frame rate.

# ==============================================================================
# PROJECT ARCHITECTURE & FILE ROLE STRUCTURE
# ==============================================================================

.
├── advanced_video_editor.py        # Entry point: System bootstrap & Global recovery hooks
├── core/                           # The "Engine Room"
│   ├── binary_manager.py           # GPU detection (AV1/NVENC) & DLL environment setup
│   ├── history.py                  # 50-depth Undo/Redo with Delta Compression
│   ├── model.py                    # Data classes (Unified A/V unit logic)
│   ├── project.py                  # FIFO project management (10-project limit)
│   ├── project_controller.py       # High-level state switching & Autosave timer
│   └── system.py                   # ConfigManager & Rotating Log system
├── timeline/                       # The "Battlefield" (Collision & Lane Logic)
│   ├── clip_item.py                # Visual representation (Single box until split)
│   ├── clip_painter.py             # Drawing logic: Waveforms, Thumbs, Selection borders
│   ├── timeline_container.py       # Scalable container (Handles 50+ track headers)
│   ├── timeline_grid.py            # Cached ruler & Red Playhead painting
│   ├── timeline_ops.py             # Structural logic: A/V Splitting & Track reordering
│   ├── timeline_scene.py           # The Graphics Scene (Infinite scroll area)
│   ├── timeline_view.py            # Interaction: Hard Collisions & Magnetic Snapping
│   └── track_header.py             # Vertical scroll-linked headers for 50 tracks
├── rendering/                      # "The Forge"
│   ├── ffmpeg_generator.py         # Dynamic FilterGraph builder (Occlusion optimized)
│   ├── playback_manager.py         # Playhead sync & Throttled real-time playback
│   ├── player.py                   # MPV Backend for frame-accurate seek
│   ├── player_vlc.py               # VLC Fallback backend
│   ├── prober.py                   # FFprobe metadata & Waveform generation workers
│   └── render_worker.py            # High-priority export threading
├── ui/                             # "The Cockpit" (Slick Professional Interface)
│   ├── custom_title_bar.py         # Dark mode title bar
│   ├── export_dialog.py            # Rendering UI with file size estimation
│   ├── inspector.py                # Clip property sliders (Speed/Volume/Crop)
│   ├── main_window.py              # Central Docking UI (Media Pool, Timeline, Preview)
│   ├── media_pool.py               # Drag-and-drop asset management
│   └── preview.py                  # Video window + SafeOverlay for interactive cropping
├── workers/                        # "The Grunts" (Background Tasks)
│   ├── asset_loader.py             # File importer & Duplicate drop prevention
│   ├── clip_manager.py             # Razor logic (Select Right + Jump) & Gap prompts
│   ├── recorder.py                 # Core audio capture logic
│   ├── voice_recorder.py           # Background Mic level monitoring
│   └── worker.py                   # GPU-hijacked Proxy & Thumbnail generation
├── binaries/                       # Local FFmpeg, VLC, & MPV runtimes
├── cache/                          # Persistent Thumbnails & Waveforms
├── projects/                       # User project JSONs, Assets, & Autosaves
└── logs/                           # Debug/Crash recovery logs
