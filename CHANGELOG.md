### Version 1.0 - Initial Release

---

#### Core Architectural Components

- **GUI Framework:** The application is built on **PyQt5**, leveraging its robust widget system to create a responsive, cross-platform graphical user interface. The UI is structured as a `QMainWindow` with a `QHBoxLayout` dividing the screen into a file management panel and a tag editing panel. A custom stylesheet provides a professional, unified dark theme.
- **File I/O Engine:** The core file processing is handled by the **`mutagen`** library, which provides comprehensive read and write capabilities for metadata across various audio formats:
  - **MP3:** Uses `mutagen.id3` to handle ID3 tags, including the `APIC` frame for album art.
  - **FLAC:** Processes native FLAC tags and `Picture` blocks for cover art.
  - **M4A:** Manages MP4 atoms, including the `covr` atom for album art.
  - **Ogg:** Edits Vorbis comments and `metadata_block_picture` for embedded artwork.
- **Concurrency Model:** All long-running operations, such as file saving and network requests, are offloaded to a dedicated worker thread (`QThread`) to prevent the main UI thread from freezing. The custom `Worker` class and the `run_in_thread` helper function manage this asynchronous execution, using `pyqtSignal` to emit progress, completion, and error signals back to the main thread.
- **API Integration:** The application uses **`musicbrainzngs`** to interact with the MusicBrainz database and the **`requests`** library to fetch album art from the Cover Art Archive. All API requests are made with a custom user agent `Metagify/1.0 (negroayub97@gmail.com)` as required by the MusicBrainz terms of service.

---

#### New Features and Technical Enhancements

- **Interactive File List:** The `QListWidget` has been enhanced with key interactive features:
  - **Drag-and-Drop:** Users can drag audio files directly from their file explorer to load them.
  - **Reordering:** The list supports `QAbstractItemView.InternalMove` to let users reorder tracks, which is crucial for preparing a release submission to MusicBrainz.
  - **Multi-selection:** Supports `QAbstractItemView.ExtendedSelection` to enable efficient batch editing and removal of multiple files at once.
- **Dynamic Tag Editor:** The right-side panel features a dynamic `QFormLayout` that adapts its functionality based on the selection.
  - **Single File Mode:** Displays all tag fields for manual editing, with the album art visible.
  - **Batch Mode:** When multiple files are selected, a `QCheckBox` appears next to each tag field. Changes are only applied to files for fields where the checkbox is checked, preventing unintended overwrites.
- **MusicBrainz Integration:**
  - **Search and Apply:** The `SearchDialog` allows users to search the MusicBrainz database by artist and album. The selected release's metadata, including title, artist, album, and track number, can be applied to the loaded files.
  - **Release Submission:** The `SubmissionDialog` provides a structured form to submit new releases to MusicBrainz, including tracks, release title, artist, and date.
- **Album Art Management:** The application handles album art fetching from Cover Art Archive. It downloads the art and uses a `QPixmap` and `QBuffer` to resize the image to a standardized 500x500 pixels for optimized file size before embedding it.

---

#### Stability and Usability Improvements

- **Contextual Help System:** A `QLabel` in the status bar displays a description of each UI element on hover, based on the `HELP_TEXT` dictionary.
- **Progress and Status Feedback:** A `QProgressBar` and `QStatusBar` provide real-time feedback on file-loading and saving operations.
- **Robust File Handling:** The application includes comprehensive `try-except` blocks to gracefully handle unsupported file formats or corrupted audio files, providing clear error messages.
- **Settings Persistence:** `QSettings` is used to save and restore the main window's geometry to maintain the user's preferred size and position between sessions.
- **User Configuration:** The initial run prompts the user to enter a contact email, required by the MusicBrainz API, and stores it using `Q
