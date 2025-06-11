import datetime
import os
import sys

import musicbrainzngs
import mutagen
import qtawesome as qta
import requests
from PyQt5.QtCore import QObject, QSettings, QSize, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                             QFileDialog, QFormLayout, QFrame, QHBoxLayout,
                             QHeaderView, QInputDialog, QLabel, QLineEdit,
                             QListWidget, QListWidgetItem, QMainWindow,
                             QMessageBox, QProgressBar, QPushButton,
                             QScrollArea, QStatusBar, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

# --- MusicBrainz API Configuration ---
# NOTE: For submissions, you MUST authenticate. This is done when you try to submit.
musicbrainzngs.set_useragent(
    "Metatag",
    "3.0",
    "negroayub97@gmail.com"  # Please change this to your email or project URL
)

# --- VISUAL STYLES (QSS) ---
STYLESHEET = """
    QMainWindow, QDialog { background-color: #2B2D30; }
    QWidget { color: #F0F0F0; font-family: 'Segoe UI', 'Roboto', 'Arial'; font-size: 14px; }
    QScrollArea { border: none; background-color: #2B2D30; }
    QWidget#editorPanel { background-color: #2B2D30; }
    QTableWidget { background-color: #202124; border: 1px solid #404040; border-radius: 8px; gridline-color: #404040; }
    QTableWidget::item { padding: 8px; border-bottom: 1px solid #404040; }
    QTableWidget::item:selected { background-color: #007ACC; color: white; }
    QHeaderView::section { background-color: #35373A; color: #F0F0F0; padding: 6px; border: 1px solid #404040; font-weight: bold; }
    QLineEdit { background-color: #35373A; border: 1px solid #505050; border-radius: 5px; padding: 8px; }
    QLineEdit:focus { border: 1px solid #007ACC; }
    QLineEdit:disabled { background-color: #252525; color: #707070; }
    QPushButton { background-color: #007ACC; color: white; border: none; border-radius: 5px; padding: 10px 15px; font-weight: bold; }
    QPushButton:hover { background-color: #005A9E; }
    QPushButton:disabled { background-color: #454545; color: #808080; }
    QListWidget { background-color: #202124; border: 1px solid #404040; border-radius: 8px; padding: 5px; }
    QListWidget::item { padding: 8px; border-radius: 4px; }
    QListWidget::item:hover { background-color: #35373A; }
    QListWidget::item:selected { background-color: #007ACC; color: white; }
    QLabel#titleLabel { font-size: 18px; font-weight: bold; padding-bottom: 10px; }
    QLabel#albumArtLabel { border: 2px dashed #505050; border-radius: 10px; }
    QLabel#submissionInfoLabel { font-size: 12px; color: #AAAAAA; }
    QStatusBar, QProgressBar { color: #A0A0A0; }
    QProgressBar { text-align: center; }
"""

# --- Worker for Background Tasks (Networking) ---


class Worker(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(Exception)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(e)

# --- MusicBrainz Submission Dialog ---


class SubmissionDialog(QDialog):
    def __init__(self, file_paths, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.setWindowTitle("Submit New Release to MusicBrainz")
        self.setMinimumSize(700, 600)
        self.setStyleSheet(STYLESHEET)

        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Form Layout for release details
        form_layout = QFormLayout()
        self.album_artist_input = QLineEdit()
        self.album_title_input = QLineEdit()
        self.release_date_input = QLineEdit()
        self.release_date_input.setPlaceholderText("YYYY-MM-DD")
        self.release_type_combo = QComboBox()
        self.release_type_combo.addItems(["Album", "EP", "Single", "Other"])

        form_layout.addRow("Album Artist:", self.album_artist_input)
        form_layout.addRow("Album Title:", self.album_title_input)
        form_layout.addRow("Release Date:", self.release_date_input)
        form_layout.addRow("Release Type:", self.release_type_combo)
        layout.addLayout(form_layout)

        # Table for tracks
        layout.addWidget(QLabel("Tracks:"))
        self.track_table = QTableWidget()
        self.track_table.setColumnCount(3)
        self.track_table.setHorizontalHeaderLabels(
            ["Track #", "Title", "Duration"])
        self.track_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.track_table)

        # Info label
        info_label = QLabel(
            "Note: This will create an edit on MusicBrainz for community review. It will not appear instantly.")
        info_label.setObjectName("submissionInfoLabel")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Submit Button
        self.submit_button = QPushButton("Authenticate and Submit")
        self.submit_button.setIcon(qta.icon('fa5s.upload', color='white'))
        layout.addWidget(self.submit_button)

        # Connections
        self.submit_button.clicked.connect(self.submit_data)

        self.populate_from_files()

    def populate_from_files(self):
        """Pre-fills the form with data from the audio files."""
        if not self.file_paths:
            return

        # Guess album artist and title from the first file
        try:
            first_audio = mutagen.File(self.file_paths[0], easy=True)
            if first_audio:
                self.album_artist_input.setText(first_audio.get('albumartist', [''])[
                                                0] or first_audio.get('artist', [''])[0])
                self.album_title_input.setText(
                    first_audio.get('album', [''])[0])
                date_str = first_audio.get('date', [''])[0]
                if date_str:
                    # Try to parse just the year if it's longer
                    self.release_date_input.setText(date_str.split('-')[0])
        except Exception as e:
            print(f"Error reading first file for defaults: {e}")

        # Populate tracks
        self.track_table.setRowCount(len(self.file_paths))
        for i, f_path in enumerate(self.file_paths):
            try:
                audio = mutagen.File(f_path, easy=True)
                audio_info = mutagen.File(f_path)
                track_num = audio.get('tracknumber', [str(i + 1)])[0]
                title = audio.get('title', [os.path.basename(f_path)])[0]
                duration_sec = audio_info.info.length

                duration_str = str(datetime.timedelta(
                    seconds=int(duration_sec)))
                if duration_str.startswith("0:"):
                    # Format as M:SS instead of 0:M:SS
                    duration_str = duration_str[2:]

                self.track_table.setItem(
                    i, 0, QTableWidgetItem(track_num.split('/')[0]))
                self.track_table.setItem(i, 1, QTableWidgetItem(title))
                self.track_table.setItem(i, 2, QTableWidgetItem(duration_str))
                self.track_table.item(i, 2).setData(
                    Qt.UserRole, int(duration_sec * 1000))

            except Exception as e:
                self.track_table.setItem(
                    i, 1, QTableWidgetItem(f"Error reading file"))
                print(f"Error populating track {i}: {e}")

    def submit_data(self):
        """Handles authentication and data submission."""
        user, ok1 = QInputDialog.getText(
            self, "MusicBrainz Authentication", "Enter your MusicBrainz username:")
        if not ok1 or not user:
            return

        password, ok2 = QInputDialog.getText(
            self, "MusicBrainz Authentication", "Enter your MusicBrainz password:", echo=QLineEdit.Password)
        if not ok2 or not password:
            return

        if not self.album_artist_input.text() or not self.album_title_input.text():
            QMessageBox.warning(self, "Missing Information",
                                "Album Artist and Album Title are required.")
            return

        try:
            tracks = []
            for i in range(self.track_table.rowCount()):
                tracks.append({
                    "title": self.track_table.item(i, 1).text(),
                    "length": self.track_table.item(i, 2).data(Qt.UserRole)
                })

            release_data = {
                "artist_credit": [{"artist": {"name": self.album_artist_input.text()}}],
                "title": self.album_title_input.text(),
                "date": self.release_date_input.text(),
                "release_group": {"title": self.album_title_input.text()},
                "mediums": [{"format": "Digital Media", "tracks": tracks}]
            }
        except Exception as e:
            QMessageBox.critical(self, "Data Error",
                                 f"Could not build submission data: {e}")
            return

        self.submit_button.setEnabled(False)
        self.submit_button.setText("Submitting...")
        QApplication.setOverrideCursor(Qt.WaitCursor)

        self.thread = QThread()
        self.worker = Worker(self._perform_submission,
                             user, password, release_data)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.submission_finished)
        self.worker.error.connect(self.submission_error)

        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def _perform_submission(self, user, password, data):
        """Function to be run in the worker thread."""
        musicbrainzngs.auth(user, password)
        musicbrainzngs.submit_release(data, client_token="Metatag/3.0")
        return True

    def submission_finished(self, result):
        """Called when submission succeeds."""
        QApplication.restoreOverrideCursor()
        self.submit_button.setText("Authenticate and Submit")
        self.submit_button.setEnabled(True)
        QMessageBox.information(self, "Submission Successful",
                                "Your new release has been submitted as an edit to MusicBrainz.\n"
                                "You can check your open edits on the MusicBrainz website to track its progress.")
        self.accept()

    def submission_error(self, e):
        """Called when submission fails."""
        QApplication.restoreOverrideCursor()
        self.submit_button.setText("Authenticate and Submit")
        self.submit_button.setEnabled(True)
        error_message = str(e)
        if isinstance(e, musicbrainzngs.AuthenticationError):
            error_message = "Authentication failed. Please check your username and password."
        elif isinstance(e, musicbrainzngs.ResponseError):
            error_message = f"MusicBrainz API error:\n{e}"

        QMessageBox.critical(self, "Submission Failed", error_message)


# --- MusicBrainz Search Dialog ---
class SearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Search MusicBrainz")
        self.setMinimumSize(600, 400)
        self.setStyleSheet(STYLESHEET)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        search_layout = QHBoxLayout()
        self.artist_input = QLineEdit()
        self.album_input = QLineEdit()
        search_button = QPushButton("Search")
        search_layout.addWidget(QLabel("Artist:"))
        search_layout.addWidget(self.artist_input)
        search_layout.addWidget(QLabel("Album:"))
        search_layout.addWidget(self.album_input)
        search_layout.addWidget(search_button)
        self.results_list = QListWidget()
        self.apply_button = QPushButton("Apply Tags")
        self.apply_button.setEnabled(False)
        layout.addLayout(search_layout)
        layout.addWidget(self.results_list)
        layout.addWidget(self.apply_button)
        search_button.clicked.connect(self.search)
        self.apply_button.clicked.connect(self.accept)
        self.results_list.itemSelectionChanged.connect(
            lambda: self.apply_button.setEnabled(True))
        self.results_list.itemDoubleClicked.connect(self.accept)

    def search(self):
        artist = self.artist_input.text()
        album = self.album_input.text()
        if not artist and not album:
            QMessageBox.warning(self, "Empty Search",
                                "Please enter an artist or an album.")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        query = f'artist:"{artist}" AND release:"{album}"'
        self.thread = QThread()
        self.worker = Worker(
            musicbrainzngs.search_releases, query=query, limit=20)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.show_results)
        self.worker.error.connect(self.show_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def show_results(self, data):
        self.results_list.clear()
        QApplication.restoreOverrideCursor()
        releases = data.get('release-list', [])
        if not releases:
            self.results_list.addItem(
                "No results found. Consider submitting this release.")
            return
        for release in releases:
            artist = release.get('artist-credit-phrase', 'N/A')
            title = release.get('title', 'N/A')
            date = release.get('date', 'N/A')
            track_count = release.get('medium-track-count', 'N/A')
            item_text = f"{artist} - {title} ({date}) [{track_count} tracks]"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, release['id'])
            self.results_list.addItem(item)

    def show_error(self, e):
        QApplication.restoreOverrideCursor()
        QMessageBox.critical(self, "Network Error",
                             f"Could not connect to MusicBrainz:\n{e}")

    def get_selected_release_id(self):
        if self.results_list.currentItem() and self.results_list.currentItem().data(Qt.UserRole):
            return self.results_list.currentItem().data(Qt.UserRole)
        return None


# --- Main Application Window ---
class Metatag(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("MyCompany", "Metatag")
        self.files_data = {}
        self.current_art_data = None
        self.art_is_dirty = False
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        self.setWindowTitle("Metatag - Audio Metadata Editor")
        self.setWindowIcon(qta.icon('fa5s.tags', color='#007ACC'))
        self.setStyleSheet(STYLESHEET)

        try:
            screen = QApplication.primaryScreen()
            screen_geometry = screen.availableGeometry()
            self.setGeometry(
                int(screen_geometry.width() * 0.1),
                int(screen_geometry.height() * 0.1),
                int(screen_geometry.width() * 0.8),
                int(screen_geometry.height() * 0.8)
            )
        except Exception as e:
            print(f"Could not get screen resolution, using default size: {e}")
            self.resize(1280, 720)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Left Panel
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)
        table_actions_layout = QHBoxLayout()

        load_button = QPushButton(" Load Files")
        load_button.setIcon(qta.icon('fa5s.folder-open', color='white'))

        self.rename_button = QPushButton(" Rename Files")
        self.rename_button.setIcon(qta.icon('fa5s.i-cursor', color='white'))

        self.musicbrainz_button = QPushButton(" Search MusicBrainz")
        self.musicbrainz_button.setIcon(
            qta.icon('fa5b.searchengin', color='white'))

        self.submit_button = QPushButton(" Submit to MusicBrainz")
        self.submit_button.setIcon(qta.icon('fa5s.upload', color='white'))

        restart_button = QPushButton(" Restart")
        restart_button.setIcon(qta.icon('fa5s.sync-alt', color='white'))

        table_actions_layout.addWidget(load_button)
        table_actions_layout.addWidget(self.rename_button)
        table_actions_layout.addWidget(self.musicbrainz_button)
        table_actions_layout.addWidget(self.submit_button)
        table_actions_layout.addStretch()
        table_actions_layout.addWidget(restart_button)

        self.file_table = QTableWidget(0, 4)
        self.file_table.setHorizontalHeaderLabels(
            ["File", "Title", "Artist", "Album"])
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.file_table.setColumnWidth(0, 300)
        for i in range(1, 4):
            self.file_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
        self.file_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.file_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.file_table.setSortingEnabled(True)

        left_panel.addLayout(table_actions_layout)
        left_panel.addWidget(self.file_table)

        # --- Right Panel (Editor) ---
        self.editor_panel = QWidget()
        self.editor_panel.setObjectName("editorPanel")
        self.editor_panel.setAutoFillBackground(False)

        editor_layout = QVBoxLayout(self.editor_panel)
        editor_layout.setContentsMargins(10, 10, 10, 10)
        editor_layout.setSpacing(10)

        self.title_label = QLabel("Select a file to edit")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)

        self.album_art_label = QLabel("Album Art")
        self.album_art_label.setObjectName("albumArtLabel")
        self.album_art_label.setAlignment(Qt.AlignCenter)
        self.album_art_label.setMinimumSize(250, 250)

        self.art_buttons_widget = QWidget()
        art_buttons_layout = QHBoxLayout(self.art_buttons_widget)
        art_buttons_layout.setContentsMargins(0, 5, 0, 5)
        art_buttons_layout.setSpacing(10)
        self.change_art_button = QPushButton(" Change/Add")
        self.change_art_button.setIcon(qta.icon('fa5s.image', color='white'))
        self.delete_art_button = QPushButton(" Delete")
        self.delete_art_button.setIcon(
            qta.icon('fa5s.trash-alt', color='white'))
        art_buttons_layout.addStretch()
        art_buttons_layout.addWidget(self.change_art_button)
        art_buttons_layout.addWidget(self.delete_art_button)
        art_buttons_layout.addStretch()

        self.fields = {}
        self.checkboxes = {}
        self.form_layout = QFormLayout()
        self.form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self.form_layout.setLabelAlignment(Qt.AlignRight)
        self.form_layout.setVerticalSpacing(10)
        self.tags_to_edit = ["Title", "Artist", "Album",
                             "Album Artist", "Genre", "Year", "Track", "Comment"]

        for tag in self.tags_to_edit:
            self.checkboxes[tag] = QCheckBox()
            self.checkboxes[tag].setVisible(False)
            line_edit = QLineEdit()
            self.fields[tag] = line_edit
            field_container_layout = QHBoxLayout()
            field_container_layout.setContentsMargins(0, 0, 0, 0)
            field_container_layout.setSpacing(5)
            field_container_layout.addWidget(self.checkboxes[tag])
            field_container_layout.addWidget(line_edit)
            self.form_layout.addRow(QLabel(f"{tag}:"), field_container_layout)

        self.save_button = QPushButton(" Save Changes")
        self.save_button.setIcon(qta.icon('fa5s.save', color='white'))

        editor_layout.addWidget(self.title_label)
        editor_layout.addWidget(self.album_art_label, 0, Qt.AlignCenter)
        editor_layout.addWidget(self.art_buttons_widget, 0, Qt.AlignCenter)
        editor_layout.addSpacing(15)
        editor_layout.addLayout(self.form_layout)
        editor_layout.addStretch()
        editor_layout.addWidget(self.save_button)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.editor_panel)
        self.scroll_area.setVisible(False)

        right_panel = QVBoxLayout()
        right_panel.addWidget(self.scroll_area)

        main_layout.addLayout(left_panel, 3)
        main_layout.addLayout(right_panel, 2)

        # Connections
        load_button.clicked.connect(self.open_file_dialog)
        self.rename_button.clicked.connect(self.rename_files_dialog)
        self.musicbrainz_button.clicked.connect(self.search_musicbrainz)
        self.submit_button.clicked.connect(self.open_submission_dialog)
        self.file_table.itemSelectionChanged.connect(self.on_selection_changed)
        self.save_button.clicked.connect(self.save_metadata)
        self.change_art_button.clicked.connect(self.change_album_art)
        self.delete_art_button.clicked.connect(self.delete_album_art)
        restart_button.clicked.connect(self.restart_application)

        self.rename_button.setEnabled(False)
        self.musicbrainz_button.setEnabled(False)
        self.submit_button.setEnabled(False)

        # Status Bar
        self.status_bar = QStatusBar()
        self.progress_bar = QProgressBar()
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.progress_bar.hide()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready to work.")
        self.setAcceptDrops(True)

    def restart_application(self):
        reply = QMessageBox.question(self, "Restart Application",
                                     "Are you sure you want to restart?\nAny unsaved changes will be lost.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            os.execv(sys.executable, ['python'] + sys.argv)

    def open_submission_dialog(self):
        selected_rows = sorted(list(set(index.row()
                               for index in self.file_table.selectedIndexes())))
        if not selected_rows:
            QMessageBox.warning(
                self, "No Files Selected", "Please select the files for the release you want to submit.")
            return

        file_paths = [self.files_data[row]['path'] for row in selected_rows]
        dialog = SubmissionDialog(file_paths, self)
        dialog.exec_()

    def on_selection_changed(self):
        selected_rows = list(set(index.row()
                             for index in self.file_table.selectedIndexes()))
        num_rows_selected = len(selected_rows)

        is_enabled = num_rows_selected > 0
        self.rename_button.setEnabled(is_enabled)
        self.musicbrainz_button.setEnabled(is_enabled)
        self.submit_button.setEnabled(is_enabled)

        if num_rows_selected == 0:
            self.scroll_area.setVisible(False)
        elif num_rows_selected == 1:
            self.art_is_dirty = False
            self.current_art_data = None
            self.scroll_area.setVisible(True)
            self.update_editor_for_single(selected_rows[0])
        else:
            self.scroll_area.setVisible(True)
            self.update_editor_for_batch(num_rows_selected)

    def update_editor_for_single(self, row):
        path = self.files_data[row].get('path')
        if not path:
            return
        self.title_label.setText(f"Editing: {os.path.basename(path)}")
        for tag in self.tags_to_edit:
            self.checkboxes[tag].setVisible(False)
        self.art_buttons_widget.setVisible(True)
        try:
            audio = mutagen.File(path, easy=True)
            if audio is None:
                raise ValueError("Could not load audio file.")
            self.fields["Title"].setText(audio.get('title', [''])[0])
            self.fields["Artist"].setText(audio.get('artist', [''])[0])
            self.fields["Album"].setText(audio.get('album', [''])[0])
            self.fields["Album Artist"].setText(
                audio.get('albumartist', [''])[0])
            self.fields["Genre"].setText(audio.get('genre', [''])[0])
            self.fields["Year"].setText(audio.get('date', [''])[0])
            self.fields["Track"].setText(audio.get('tracknumber', [''])[0])
            self.fields["Comment"].setText(audio.get('comment', [''])[0])
            self.load_album_art(path)
        except Exception as e:
            self.status_bar.showMessage(
                f"Could not read file: {os.path.basename(path)} - {e}", 4000)

    def update_editor_for_batch(self, count):
        self.title_label.setText(f"Editing {count} files (batch mode)")
        self.album_art_label.setText("Album art unavailable\nin batch mode")
        self.album_art_label.setPixmap(QPixmap())
        self.art_buttons_widget.setVisible(False)
        for tag in self.tags_to_edit:
            self.checkboxes[tag].setVisible(True)
            self.checkboxes[tag].setChecked(False)
            self.fields[tag].clear()
            self.fields[tag].setPlaceholderText("Leave blank for no change")

    def load_settings(self):
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = [url.toLocalFile() for url in event.mimeData().urls()]
        self.add_files_to_table(urls)

    def open_file_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Audio Files", "", "Audio Files (*.mp3 *.flac *.m4a *.ogg)")
        if files:
            self.add_files_to_table(files)

    def add_files_to_table(self, files):
        valid_files = [f for f in files if f.lower().endswith(
            ('.mp3', '.flac', '.m4a', '.ogg'))]
        self.file_table.setSortingEnabled(False)
        for file_path in valid_files:
            if any(d.get('path') == file_path for d in self.files_data.values()):
                continue
            row_position = self.file_table.rowCount()
            self.files_data[row_position] = {'path': file_path, 'dirty': False}
            self.file_table.insertRow(row_position)
            try:
                audio = mutagen.File(file_path, easy=True)
                if audio is None:
                    raise TypeError
                filename_item = QTableWidgetItem(os.path.basename(file_path))
                filename_item.setIcon(
                    qta.icon('fa5s.file-audio', color='#A0A0A0'))
                self.file_table.setItem(row_position, 0, filename_item)
                self.file_table.setItem(
                    row_position, 1, QTableWidgetItem(audio.get('title', [''])[0]))
                self.file_table.setItem(
                    row_position, 2, QTableWidgetItem(audio.get('artist', [''])[0]))
                self.file_table.setItem(
                    row_position, 3, QTableWidgetItem(audio.get('album', [''])[0]))
            except Exception:
                self.file_table.setItem(row_position, 0, QTableWidgetItem(
                    f"Error reading: {os.path.basename(file_path)}"))
        self.file_table.setSortingEnabled(True)
        self.status_bar.showMessage(f"{len(valid_files)} file(s) added.")

    def load_album_art(self, path):
        try:
            audio_raw = mutagen.File(path)
            artwork = None
            if audio_raw is None:
                raise ValueError("Could not load file.")
            if 'APIC:' in audio_raw:
                artwork = audio_raw.get('APIC:').data
            elif 'covr' in audio_raw:
                artwork = audio_raw.get('covr')[0]
            elif audio_raw.pictures:
                artwork = audio_raw.pictures[0].data
            if artwork:
                pixmap = QPixmap()
                pixmap.loadFromData(artwork)
                scaled_pixmap = pixmap.scaled(self.album_art_label.width(
                ), self.album_art_label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.album_art_label.setPixmap(scaled_pixmap)
                self.album_art_label.setText("")
            else:
                self.album_art_label.setText("No album art")
                self.album_art_label.setPixmap(QPixmap())
        except Exception as e:
            self.album_art_label.setText("Error loading art")
            self.album_art_label.setPixmap(QPixmap())
            print(f"Error in load_album_art: {e}")

    def change_album_art(self):
        image_path, _ = QFileDialog.getOpenFileName(
            self, "Select Album Art", "", "Image Files (*.jpg *.jpeg *.png)")
        if image_path:
            try:
                with open(image_path, 'rb') as f:
                    self.current_art_data = f.read()
                pixmap = QPixmap()
                pixmap.loadFromData(self.current_art_data)
                scaled_pixmap = pixmap.scaled(self.album_art_label.width(
                ), self.album_art_label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.album_art_label.setPixmap(scaled_pixmap)
                self.album_art_label.setText("")
                self.art_is_dirty = True
                selected_rows = list(
                    set(index.row() for index in self.file_table.selectedIndexes()))
                if selected_rows:
                    self.mark_row_as_dirty(selected_rows[0])
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Could not load image: {e}")

    def delete_album_art(self):
        reply = QMessageBox.question(
            self, "Confirm Deletion", "Are you sure you want to delete the cover art for this file?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.current_art_data = b''
            self.art_is_dirty = True
            self.album_art_label.setText("Art deleted")
            self.album_art_label.setPixmap(QPixmap())
            selected_rows = list(set(index.row()
                                 for index in self.file_table.selectedIndexes()))
            if selected_rows:
                self.mark_row_as_dirty(selected_rows[0])

    def save_metadata(self):
        selected_rows = list(set(index.row()
                             for index in self.file_table.selectedIndexes()))
        if not selected_rows:
            return
        self.progress_bar.setRange(0, len(selected_rows))
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        is_single_mode = len(selected_rows) == 1
        for i, row in enumerate(selected_rows):
            path = self.files_data[row]['path']
            try:
                audio = mutagen.File(path, easy=True)
                if audio is None:
                    continue
                for tag, field in self.fields.items():
                    if is_single_mode or self.checkboxes[tag].isChecked():
                        value = field.text()
                        key = self.get_mutagen_key(tag)
                        if value:
                            audio[key] = value
                        elif key in audio:
                            del audio[key]
                audio.save()
                if is_single_mode and self.art_is_dirty:
                    self.save_album_art_to_file(path, self.current_art_data)
                self.update_table_row(row, audio)
                self.mark_row_as_dirty(row)
            except Exception as e:
                self.status_bar.showMessage(
                    f"Error saving {os.path.basename(path)}: {e}")
            self.progress_bar.setValue(i + 1)
            QApplication.processEvents()
        if is_single_mode:
            self.art_is_dirty = False
        self.progress_bar.hide()
        self.status_bar.showMessage("Save complete!", 5000)

    def get_mutagen_key(self, tag_name):
        return {"Title": "title", "Artist": "artist", "Album": "album", "Album Artist": "albumartist", "Genre": "genre", "Year": "date", "Track": "tracknumber", "Comment": "comment"}.get(tag_name, tag_name.lower())

    def update_table_row(self, row, audio):
        self.file_table.setItem(
            row, 1, QTableWidgetItem(audio.get('title', [''])[0]))
        self.file_table.setItem(
            row, 2, QTableWidgetItem(audio.get('artist', [''])[0]))
        self.file_table.setItem(
            row, 3, QTableWidgetItem(audio.get('album', [''])[0]))

    def mark_row_as_dirty(self, row):
        item = self.file_table.item(row, 0)
        if not item:
            return
        item_text = item.text()
        if not item_text.endswith("(*)"):
            item.setText(f"{item_text} (*)")
        self.files_data[row]['dirty'] = True

    def rename_files_dialog(self):
        last_pattern = self.settings.value(
            "renamePattern", "%artist% - %title%")
        pattern, ok = QInputDialog.getText(
            self, "Rename Files", "Enter a pattern:\n%artist%, %album%, %title%, %track%, %year%", QLineEdit.Normal, last_pattern)
        if ok and pattern:
            self.settings.setValue("renamePattern", pattern)
            self.rename_files(pattern)

    def rename_files(self, pattern):
        selected_rows = list(set(index.row()
                             for index in self.file_table.selectedIndexes()))
        if not selected_rows:
            return
        self.progress_bar.setRange(0, len(selected_rows))
        self.progress_bar.show()
        renamed_count = 0
        for i, row in enumerate(selected_rows):
            path = self.files_data[row]['path']
            try:
                audio = mutagen.File(path, easy=True)
                if audio is None:
                    continue
                dirname, _ = os.path.split(path)
                track_num = audio.get('tracknumber', ['00'])[
                    0].split('/')[0].zfill(2)
                new_name = pattern.replace('%artist%', audio.get('artist', ['N_A'])[0]).replace('%album%', audio.get('album', ['N_A'])[0]).replace(
                    '%title%', audio.get('title', ['N_A'])[0]).replace('%track%', track_num).replace('%year%', audio.get('date', ['0000'])[0])
                new_name = "".join(
                    c for c in new_name if c not in r'<>:"/\|?*')
                new_path = os.path.join(
                    dirname, f"{new_name}{os.path.splitext(path)[1]}")
                if path != new_path:
                    os.rename(path, new_path)
                    self.files_data[row]['path'] = new_path
                    base_name = os.path.basename(new_path)
                    self.file_table.item(row, 0).setText(base_name)
                    self.mark_row_as_dirty(row)
                    renamed_count += 1
            except Exception as e:
                self.status_bar.showMessage(
                    f"Error renaming {os.path.basename(path)}: {e}")
            self.progress_bar.setValue(i + 1)
            QApplication.processEvents()
        self.progress_bar.hide()
        self.status_bar.showMessage(f"{renamed_count} files renamed.", 5000)

    def search_musicbrainz(self):
        selected_rows = list(set(index.row()
                             for index in self.file_table.selectedIndexes()))
        if not selected_rows:
            return
        dialog = SearchDialog(self)
        first_row_path = self.files_data[selected_rows[0]]['path']
        try:
            audio = mutagen.File(first_row_path, easy=True)
            if audio is not None:
                dialog.artist_input.setText(
                    audio.get('albumartist', audio.get('artist', ['']))[0])
                dialog.album_input.setText(audio.get('album', [''])[0])
        except Exception:
            pass
        if dialog.exec_() == QDialog.Accepted:
            release_id = dialog.get_selected_release_id()
            if release_id:
                self.fetch_release_data(release_id)

    def fetch_release_data(self, release_id):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.status_bar.showMessage("Fetching release data...")
        self.thread = QThread()
        self.worker = Worker(self._fetch_release_and_art, release_id)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.apply_musicbrainz_data)
        self.worker.error.connect(self.show_network_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def _fetch_release_and_art(self, release_id):
        release = musicbrainzngs.get_release_by_id(
            release_id, includes=["artists", "recordings", "artist-credits"])['release']
        art_data = None
        try:
            art_response = requests.get(
                f"https://coverartarchive.org/release/{release_id}/front-500", timeout=10)
            art_response.raise_for_status()
            art_data = art_response.content
        except Exception:
            pass
        return release, art_data

    def apply_musicbrainz_data(self, data):
        QApplication.restoreOverrideCursor()
        release, art_data = data
        selected_rows = sorted(list(set(index.row()
                               for index in self.file_table.selectedIndexes())))
        tracks = release['medium-list'][0]['track-list']
        if len(selected_rows) != len(tracks):
            QMessageBox.warning(
                self, "Track Mismatch", f"You selected {len(selected_rows)} files, but the release has {len(tracks)} tracks.")
            return
        album_artist = release['artist-credit-phrase']
        album_title = release['title']
        date = release['date'].split('-')[0] if 'date' in release else ''
        total_tracks = release['medium-list'][0].get(
            'track-count', len(tracks))
        for i, row in enumerate(selected_rows):
            path = self.files_data[row]['path']
            try:
                audio = mutagen.File(path, easy=True)
                if audio is None:
                    continue
                track_info = tracks[i]
                track_num = track_info['number']
                audio['title'] = track_info['recording']['title']
                audio['artist'] = track_info['artist-credit-phrase']
                audio['albumartist'] = album_artist
                audio['album'] = album_title
                audio['date'] = date
                audio['tracknumber'] = f"{track_num}/{total_tracks}"
                audio.save()
                if art_data:
                    self.save_album_art_to_file(path, art_data)
                self.update_table_row(row, audio)
                self.mark_row_as_dirty(row)
            except Exception as e:
                self.status_bar.showMessage(
                    f"Error applying to {os.path.basename(path)}: {e}")
        self.status_bar.showMessage(
            f"Metadata for '{album_title}' applied!", 5000)
        if selected_rows:
            self.file_table.clearSelection()
            self.file_table.selectRow(selected_rows[0])

    def save_album_art_to_file(self, file_path, art_data):
        audio = mutagen.File(file_path, easy=False)
        if audio is None:
            return
        delete_art = art_data == b''
        if file_path.lower().endswith('.mp3'):
            from mutagen.id3 import APIC
            audio.tags.delall('APIC')
            if not delete_art:
                audio.tags.add(APIC(encoding=3, mime='image/jpeg',
                               type=3, desc='Cover', data=art_data))
        elif file_path.lower().endswith('.flac'):
            from mutagen.flac import Picture
            audio.clear_pictures()
            if not delete_art:
                pic = Picture()
                pic.type, pic.mime, pic.desc, pic.data = 3, 'image/jpeg', 'Cover', art_data
                audio.add_picture(pic)
        elif file_path.lower().endswith('.m4a'):
            from mutagen.mp4 import MP4Cover
            if 'covr' in audio.tags:
                del audio.tags['covr']
            if not delete_art:
                audio.tags['covr'] = [
                    MP4Cover(art_data, imageformat=MP4Cover.FORMAT_JPEG)]
        audio.save()

    def show_network_error(self, e):
        QApplication.restoreOverrideCursor()
        self.status_bar.showMessage("Network error.", 5000)
        QMessageBox.critical(self, "Network Error",
                             f"A network error occurred:\n{e}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    editor = Metatag()
    editor.show()
    sys.exit(app.exec_())
