#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Metagify: An enhanced audio metadata (tag) editor.

This version improves the user interface with:
- An interactive file list that allows reordering and multi-selection.
- A contextual information system that displays descriptions on hover.
- An improved color palette for a more professional look.
"""

import base64
import datetime
import hashlib
import json
import os
import sys
import time
from pathlib import Path

# Third-party imports
import musicbrainzngs
import mutagen
import qtawesome as qta
import requests
from mutagen.flac import Picture
from mutagen.id3 import (APIC, COMM, ID3, TALB, TCON, TDRC, TIT2, TMOO, TPE1,
                         TXXX)
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4Cover
from PyQt5.QtCore import (QBuffer, QByteArray, QObject, QSettings, QSize, Qt,
                          QThread, pyqtSignal)
from PyQt5.QtGui import QColor, QIcon, QPixmap
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QCheckBox,
                             QComboBox, QDialog, QFileDialog, QFormLayout,
                             QFrame, QHBoxLayout, QHeaderView, QInputDialog,
                             QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QMainWindow, QMenu, QMessageBox, QProgressBar,
                             QPushButton, QScrollArea, QStatusBar,
                             QTableWidget, QTableWidgetItem, QToolButton,
                             QVBoxLayout, QWidget)

# --- APPLICATION CONSTANTS ---
APP_NAME = "Metagify"
APP_VERSION = "1.0"
CONTACT_EMAIL = "negroayub97@gmail.com"  # IMPORTANT: Change this email!

SETTINGS_ORG = "Metagify"
SETTINGS_APP = "Metagify"

# --- UI AND STYLING ---
STYLESHEET = """
    QMainWindow, QDialog { background-color: #1E1E1E; }
    QWidget { color: #D4D4D4; font-family: 'Segoe UI', 'Roboto', 'Arial'; font-size: 14px; }
    QScrollArea { border: none; background-color: #1E1E1E; }
    QWidget#editorPanel { background-color: #1E1E1E; }
    QTableWidget {
        background-color: #252526;
        border: 1px solid #3E3E40;
        border-radius: 8px;
        gridline-color: #3E3E40;
        selection-background-color: #007ACC;
        selection-color: white;
    }
    QTableWidget::item { padding: 8px; border-bottom: 1px solid #3E3E40; }
    QHeaderView::section {
        background-color: #333333;
        color: #F0F0F0;
        padding: 6px;
        border: 1px solid #3E3E40;
        font-weight: bold;
    }
    QLineEdit, QComboBox {
        background-color: #333333;
        border: 1px solid #505050;
        border-radius: 5px;
        padding: 8px;
        color: #F0F0F0;
    }
    QLineEdit:focus, QComboBox:focus { border: 1px solid #007ACC; }
    QLineEdit:disabled, QComboBox:disabled { background-color: #2D2D2D; color: #707070; }
    QPushButton, QToolButton {
        background-color: #007ACC;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 10px 15px;
        font-weight: bold;
    }
    QPushButton:hover, QToolButton:hover { background-color: #005A9E; }
    QPushButton:disabled, QToolButton:disabled { background-color: #454545; color: #808080; }
    QListWidget {
        background-color: #252526;
        border: 1px solid #3E3E40;
        border-radius: 8px;
        padding: 5px;
        show-decoration-selected: 1; /* Allows icons on selected items */
    }
    QListWidget::item { padding: 8px; border-radius: 4px; }
    QListWidget::item:hover { background-color: #35373A; }
    QListWidget::item:selected { background-color: #007ACC; color: white; }
    QLabel#titleLabel { font-size: 18px; font-weight: bold; padding-bottom: 10px; }
    QLabel#albumArtLabel { border: 2px dashed #505050; border-radius: 10px; }
    QLabel#submissionInfoLabel { font-size: 12px; color: #AAAAAA; font-style: italic; }
    QStatusBar, QProgressBar { color: #A0A0A0; }
    QProgressBar { text-align: center; }

    /* MusicBrainz dropdown menu styles */
    QMenu {
        background-color: #2C2C2C; /* Dark gray background */
        border: 1px solid #505050;
        border-radius: 5px;
        padding: 5px;
    }
    QMenu::item {
        color: white; /* White text */
        padding: 8px 25px 8px 20px;
    }
    QMenu::item:selected {
        background-color: #007ACC; /* Blue background on hover */
        color: white; /* White text */
    }
    QMenu::separator {
        height: 1px;
        background: #505050;
        margin: 5px 0;
    }

    QLabel#infoLabel {
        color: #A0A0A0;
        font-size: 12px;
        font-style: italic;
        padding: 5px;
        border: 1px solid #3E3E40;
        background-color: #252526;
        border-radius: 5px;
        margin: 10px 0;
        min-height: 20px;
    }
"""

VALID_AUDIO_EXTENSIONS = ('.mp3', '.flac', '.m4a', '.ogg')

# Extended tag dictionary
TAG_MAP = {
    "Title": "title",
    "Artist": "artist",
    "Album": "album",
    "Album Artist": "albumartist",
    "Year": "date",
    "Genre": "genre",
    "Track Number": "tracknumber",
    "Composer": "composer",
    "Producer": "producer",
    "Copyright": "copyright",
    "Comment": "comment",
    "BPM": "bpm",
    "ISRC": "isrc",
    "Catalog Number": "catalognumber",
}

# Contextual help dictionary for the interface
HELP_TEXT = {
    "load_button": "Load one or more audio files for editing.",
    "musicbrainz_button": "Access MusicBrainz features: search for metadata to apply to your files or submit a new release.",
    "search_action": "Search for a release in the MusicBrainz database to automatically fetch tags.",
    "submit_action": "Submit metadata for your files to MusicBrainz for community review.",
    "file_list": "This is the list of loaded files. You can drag and drop to reorder or select multiple files for batch editing.",
    "remove_button": "Remove selected files from the list.",
    "clear_button": "Remove all files from the current list.",
    "save_button": "Save metadata changes and album art to the audio file.",
    "album_art_label": "Displays the album art. If there is none, you can add one.",
    "change_art_button": "Select an image from your computer to use as the album art.",
    "delete_art_button": "Delete the album art from the audio file.",
    "title_input": "Enter the song title.",
    "artist_input": "Enter the name of the main artist.",
    "album_input": "Enter the album name.",
    "album_artist_input": "Enter the album artist name (useful for compilations).",
    "genre_input": "Enter the musical genre.",
    "year_input": "Enter the year of release.",
    "track_input": "Enter the track number.",
    "composer_input": "Enter the composer of the track.",
    "producer_input": "Enter the producer of the track.",
    "copyright_input": "Enter the copyright information.",
    "comment_input": "Add a comment or personal note to the file.",
    "bpm_input": "Enter the beats per minute (BPM).",
    "isrc_input": "Enter the International Standard Recording Code (ISRC).",
    "catalognumber_input": "Enter the record label's catalog number.",
}


# --- THREAD HELPER CLASSES ---

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


def run_in_thread(parent, target_fn, on_success, on_error, args=(), kwargs={}):
    thread = QThread(parent)
    worker = Worker(target_fn, *args, **kwargs)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(on_success)
    worker.error.connect(on_error)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    parent.thread = thread
    parent.worker = worker


class FileProcessor(QObject):
    processing_progress = pyqtSignal(int, int)
    processing_finished = pyqtSignal(dict)
    processing_error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stop_requested = False

    def process_and_save(self, file_paths, tags_to_save, art_data, art_mime):
        self.stop_requested = False
        self.processing_progress.emit(0, len(file_paths))
        saved_count = 0
        errors = []

        for i, path in enumerate(file_paths):
            if self.stop_requested:
                break
            try:
                audio = mutagen.File(path, easy=True)
                if audio is None:
                    raise TypeError("File could not be opened by mutagen.")

                # Save metadata
                for tag_display, value in tags_to_save.items():
                    key = TAG_MAP[tag_display]
                    if value:
                        audio[key] = value
                    elif key in audio:
                        del audio[key]
                audio.save()

                # Save album art
                if art_data is not None:
                    self._save_album_art_to_file(path, art_data, art_mime)

                saved_count += 1
            except Exception as e:
                errors.append(f"Error saving {os.path.basename(path)}: {e}")

            self.processing_progress.emit(i + 1, len(file_paths))

        self.processing_finished.emit({
            "saved_count": saved_count,
            "total_files": len(file_paths),
            "errors": errors
        })

    def process_and_save_musicbrainz(self, file_paths, release_data, art_data, art_mime):
        self.stop_requested = False
        self.processing_progress.emit(0, len(file_paths))
        errors = []
        applied_count = 0

        try:
            tracks = release_data['medium-list'][0]['track-list']
            album_artist = release_data['artist-credit-phrase']
            album_title = release_data['title']
            date = release_data.get('date', '').split('-')[0]
            total_tracks = release_data['medium-list'][0].get(
                'track-count', len(tracks))
            resized_art_data = None
            if art_data:
                pixmap = QPixmap()
                pixmap.loadFromData(art_data)
                resized_pixmap = pixmap.scaled(
                    500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                byte_array = QByteArray()
                buffer = QBuffer(byte_array)
                buffer.open(QBuffer.WriteOnly)
                resized_pixmap.save(buffer, art_mime.split('/')[1].upper())
                resized_art_data = byte_array.data()

            for i, path in enumerate(file_paths):
                if self.stop_requested:
                    break
                try:
                    audio = mutagen.File(path, easy=True)
                    if audio is None:
                        continue
                    track_info = tracks[i]
                    track_num = track_info['number']
                    audio['title'] = track_info['recording']['title']
                    audio['artist'] = track_info.get(
                        'artist-credit-phrase', album_artist)
                    audio['albumartist'] = album_artist
                    audio['album'] = album_title
                    audio['date'] = date
                    audio['tracknumber'] = f"{track_num}/{total_tracks}"
                    audio.save()
                    if resized_art_data:
                        self._save_album_art_to_file(
                            path, resized_art_data, art_mime)
                    applied_count += 1
                except Exception as e:
                    errors.append(
                        f"Error applying data to {os.path.basename(path)}: {e}")
                self.processing_progress.emit(i + 1, len(file_paths))
        except Exception as e:
            errors.append(f"MusicBrainz data application failed: {e}")
            self.processing_error.emit(f"MusicBrainz application failed: {e}")

        self.processing_finished.emit({
            "saved_count": applied_count,
            "total_files": len(file_paths),
            "errors": errors
        })

    def _save_album_art_to_file(self, file_path, art_data, art_mime):
        audio = mutagen.File(file_path, easy=False)
        if audio is None:
            return
        delete_art = (art_data == b'')
        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext == '.mp3':
                audio.tags.delall('APIC')
                if not delete_art:
                    audio.tags.add(APIC(encoding=3, mime=art_mime,
                                        type=3, desc='Cover', data=art_data))
            elif ext == '.flac':
                audio.clear_pictures()
                if not delete_art:
                    pic = Picture()
                    pic.type, pic.mime, pic.desc, pic.data = 3, art_mime, 'Cover', art_data
                    audio.add_picture(pic)
            elif ext == '.m4a':
                image_format = 14 if art_mime == 'image/png' else 13
                audio.tags['covr'] = []
                if not delete_art:
                    audio.tags['covr'] = [
                        MP4Cover(art_data, imageformat=image_format)]
            elif ext == '.ogg':
                audio.pop("metadata_block_picture", None)
                if not delete_art:
                    pic = Picture()
                    pic.type, pic.mime, pic.desc, pic.data = 3, art_mime, 'Cover', art_data
                    pic_data = base64.b64encode(pic.write()).decode('ascii')
                    audio['metadata_block_picture'] = [pic_data]
            audio.save()
        except Exception as e:
            raise RuntimeError(f"Failed to save album art: {e}")


class SubmissionDialog(QDialog):
    def __init__(self, file_paths, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.setWindowTitle("Submit New Release to MusicBrainz")
        self.setMinimumSize(700, 600)
        self.setStyleSheet(STYLESHEET)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
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
        layout.addWidget(QLabel("Tracks:"))
        self.track_table = QTableWidget()
        self.track_table.setColumnCount(3)
        self.track_table.setHorizontalHeaderLabels(
            ["Track #", "Title", "Duration"])
        self.track_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.track_table)
        info_text = ("<b>Note:</b> This creates an edit on MusicBrainz for community review.<br>"
                     "<b>Security Warning:</b> Entering your password here sends it over the network. "
                     "For maximum security, use a dedicated MusicBrainz password and not one you use elsewhere.")
        info_label = QLabel(info_text)
        info_label.setObjectName("submissionInfoLabel")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        self.submit_button = QPushButton("Authenticate and Submit")
        self.submit_button.setIcon(qta.icon('fa5s.upload', color='white'))
        layout.addWidget(self.submit_button)
        self.submit_button.clicked.connect(self.submit_data)
        self.populate_from_files()

    def populate_from_files(self):
        if not self.file_paths:
            return
        try:
            first_audio = mutagen.File(self.file_paths[0], easy=True)
            if first_audio:
                self.album_artist_input.setText(first_audio.get('albumartist', [''])[
                    0] or first_audio.get('artist', [''])[0])
                self.album_title_input.setText(
                    first_audio.get('album', [''])[0])
                date_str = first_audio.get('date', [''])[0]
                if date_str:
                    self.release_date_input.setText(date_str)
        except Exception as e:
            print(f"Error reading first file for defaults: {e}")
        self.track_table.setRowCount(len(self.file_paths))
        for i, f_path in enumerate(self.file_paths):
            try:
                audio = mutagen.File(f_path, easy=True)
                audio_info = mutagen.File(f_path)
                if not audio or not audio_info:
                    raise ValueError("Could not read file metadata.")
                track_num = audio.get(
                    'tracknumber', [str(i + 1)])[0].split('/')[0]
                title = audio.get('title', [Path(f_path).stem])[0]
                duration_sec = audio_info.info.length
                duration_str = str(datetime.timedelta(
                    seconds=int(duration_sec)))
                if duration_str.startswith("0:"):
                    duration_str = duration_str[2:]
                self.track_table.setItem(i, 0, QTableWidgetItem(track_num))
                self.track_table.setItem(i, 1, QTableWidgetItem(title))
                self.track_table.setItem(i, 2, QTableWidgetItem(duration_str))
                self.track_table.item(i, 2).setData(
                    Qt.UserRole, int(duration_sec * 1000))
            except Exception as e:
                error_item = QTableWidgetItem(
                    f"Error reading file: {os.path.basename(f_path)}")
                error_item.setForeground(Qt.red)
                self.track_table.setItem(i, 1, error_item)
                print(f"Error populating track {i}: {e}")

    def submit_data(self):
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
                tracks.append({"title": self.track_table.item(i, 1).text(
                ), "length": self.track_table.item(i, 2).data(Qt.UserRole)})
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
        run_in_thread(self, target_fn=self._perform_submission, on_success=self.submission_finished,
                      on_error=self.submission_error, args=(user, password, release_data))

    def _perform_submission(self, user, password, data):
        musicbrainzngs.auth(user, password)
        client_id = f"{APP_NAME}-{APP_VERSION}"
        musicbrainzngs.submit_release(data, client=client_id)
        return True

    def submission_error(self, e):
        QApplication.restoreOverrideCursor()
        self.submit_button.setText("Authenticate and Submit")
        self.submit_button.setEnabled(True)
        error_message = str(e)
        if isinstance(e, musicbrainzngs.AuthenticationError):
            error_message = "Authentication failed. Please check your username and password."
        elif isinstance(e, musicbrainzngs.ResponseError):
            error_message = f"MusicBrainz API error:\n{e.cause}"
        QMessageBox.critical(self, "Submission Failed", error_message)


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
        self.artist_input.setObjectName("artist_input")
        self.album_input = QLineEdit()
        self.album_input.setObjectName("album_input")
        self.search_button = QPushButton("Search")
        self.search_button.setObjectName("search_button")
        search_layout.addWidget(QLabel("Artist:"))
        search_layout.addWidget(self.artist_input)
        search_layout.addWidget(QLabel("Album:"))
        search_layout.addWidget(self.album_input)
        search_layout.addWidget(self.search_button)
        self.results_list = QListWidget()
        self.results_list.setObjectName("results_list")
        self.apply_button = QPushButton("Apply Tags")
        self.apply_button.setObjectName("apply_button")
        self.apply_button.setEnabled(False)
        layout.addLayout(search_layout)
        layout.addWidget(self.results_list)
        layout.addWidget(self.apply_button)
        self.search_button.clicked.connect(self.search)
        self.apply_button.clicked.connect(self.accept)
        self.results_list.itemSelectionChanged.connect(
            lambda: self.apply_button.setEnabled(True))
        self.results_list.itemDoubleClicked.connect(self.accept)
        self.artist_input.textChanged.connect(self.toggle_search_button)
        self.album_input.textChanged.connect(self.toggle_search_button)
        self.toggle_search_button()

    def toggle_search_button(self):
        can_search = bool(self.artist_input.text().strip()
                          or self.album_input.text().strip())
        self.search_button.setEnabled(can_search)

    def search(self):
        artist = self.artist_input.text().strip()
        album = self.album_input.text().strip()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.results_list.clear()
        self.results_list.addItem("Searching...")
        query_parts = []
        if artist:
            query_parts.append(f'artist:"{artist}"')
        if album:
            query_parts.append(f'release:"{album}"')
        query = " AND ".join(query_parts)
        run_in_thread(self, target_fn=musicbrainzngs.search_releases, on_success=self.show_results,
                      on_error=self.show_error, kwargs={'query': query, 'limit': 25})

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
            track_count = release.get('medium-track-count', '?')
            country = release.get('country', '')
            status = release.get('status', '')
            info = f"({date}"
            if country:
                info += f", {country}"
            if status:
                info += f", {status}"
            info += f") [{track_count} tracks]"
            item_text = f"{artist} - {title} {info}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, release['id'])
            item.setToolTip(item_text)
            self.results_list.addItem(item)

    def show_error(self, e):
        self.results_list.clear()
        QApplication.restoreOverrideCursor()
        QMessageBox.critical(self, "Network Error",
                             f"Could not connect to MusicBrainz:\n{e}")

    def get_selected_release_id(self):
        current_item = self.results_list.currentItem()
        return current_item.data(Qt.UserRole) if current_item and current_item.data(Qt.UserRole) else None


class Metagify(QMainWindow):
    processing_thread = None
    file_processor_worker = None
    processing_progress = pyqtSignal(int, int)  # Add this line

    def __init__(self):
        super().__init__()
        self.settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self.file_paths = []
        self.current_art_data = None
        self.current_art_mime = None
        self.art_is_dirty = False
        self.info_label = QLabel()  # Contextual information label
        self.info_label.setObjectName("infoLabel")
        self.info_label.setText(
            "Hover over an element to see its description.                                                                                                Made by Iván E. C. Ayub. @Ivan-Ayub97 on Github")
        self.init_threads()
        self.init_ui()
        self.load_settings()

    def init_threads(self):
        self.processing_thread = QThread(self)
        self.file_processor_worker = FileProcessor()
        self.file_processor_worker.moveToThread(self.processing_thread)
        self.file_processor_worker.processing_progress.connect(
            self.on_processing_progress)
        self.file_processor_worker.processing_finished.connect(
            self.on_processing_finished)
        self.file_processor_worker.processing_error.connect(
            self.on_processing_error)
        self.processing_thread.start()

    def open_submission_dialog(self):
        if not self.file_paths:
            QMessageBox.warning(
                self, "No Files Selected", "Please select the files for the release you want to submit.")
            return
        dialog = SubmissionDialog(self.file_paths, self)
        dialog.exec_()

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        if self.processing_thread.isRunning():
            self.file_processor_worker.stop_requested = True
            self.processing_thread.quit()
            self.processing_thread.wait(5000)
        super().closeEvent(event)

    def init_ui(self):
        self.setWindowTitle(
            f"{APP_NAME} {APP_VERSION} - Audio Metadata Editor")
        self.setWindowIcon(qta.icon('fa5s.tags', color='#007ACC'))
        self.setStyleSheet(STYLESHEET)
        self.setMinimumSize(1100, 700)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)

        table_actions_layout = QHBoxLayout()
        # Assign buttons to class attributes
        self.load_button = QPushButton(" Load Files")
        self.load_button.setIcon(qta.icon('fa5s.folder-open', color='white'))
        self.load_button.setObjectName("load_button")

        self.musicbrainz_button = QToolButton()
        self.musicbrainz_button.setText(" MusicBrainz")
        self.musicbrainz_button.setPopupMode(QToolButton.InstantPopup)
        self.musicbrainz_button.setObjectName("musicbrainz_button")
        musicbrainz_menu = QMenu(self)
        search_action = musicbrainz_menu.addAction(
            qta.icon('fa5b.searchengin', color='orange'), "Search Release")
        search_action.setObjectName("search_action")
        submit_action = musicbrainz_menu.addAction(
            qta.icon('fa5s.upload', color='purple'), "Submit New Release")
        submit_action.setObjectName("submit_action")
        self.musicbrainz_button.setMenu(musicbrainz_menu)

        self.remove_button = QPushButton(" Remove Selected")
        self.remove_button.setIcon(
            qta.icon('fa5s.minus-circle', color='white'))
        self.remove_button.setObjectName("remove_button")

        self.clear_button = QPushButton(" Clear List")
        self.clear_button.setIcon(qta.icon('fa5s.redo-alt', color='white'))
        self.clear_button.setObjectName("clear_button")

        table_actions_layout.addWidget(self.load_button)
        table_actions_layout.addWidget(self.musicbrainz_button)
        table_actions_layout.addWidget(self.remove_button)
        table_actions_layout.addStretch()
        table_actions_layout.addWidget(self.clear_button)

        self.file_list = QListWidget()
        self.file_list.setObjectName("file_list")
        self.file_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.setAcceptDrops(True)
        self.file_list.setDropIndicatorShown(True)

        left_panel.addLayout(table_actions_layout)
        left_panel.addWidget(self.file_list)

        self.editor_panel = QWidget()
        self.editor_panel.setObjectName("editorPanel")
        editor_layout = QVBoxLayout(self.editor_panel)
        editor_layout.setContentsMargins(15, 15, 15, 15)
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
        # Assign buttons to class attributes
        self.change_art_button = QPushButton(" Change/Add")
        self.change_art_button.setIcon(qta.icon('fa5s.image', color='white'))
        self.change_art_button.setObjectName("change_art_button")

        self.delete_art_button = QPushButton(" Delete")
        self.delete_art_button.setIcon(
            qta.icon('fa5s.trash-alt', color='white'))
        self.delete_art_button.setObjectName("delete_art_button")

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

        for tag, key in TAG_MAP.items():
            self.checkboxes[tag] = QCheckBox()
            self.checkboxes[tag].setVisible(False)
            line_edit = QLineEdit()
            line_edit.setObjectName(f"{key}_input")
            self.fields[tag] = line_edit
            field_container_layout = QHBoxLayout()
            field_container_layout.setContentsMargins(0, 0, 0, 0)
            field_container_layout.setSpacing(5)
            field_container_layout.addWidget(self.checkboxes[tag])
            field_container_layout.addWidget(line_edit)
            self.form_layout.addRow(QLabel(f"{tag}:"), field_container_layout)

        # Assign button to class attribute
        self.save_button = QPushButton(" Save Changes")
        self.save_button.setIcon(qta.icon('fa5s.save', color='white'))
        self.save_button.setObjectName("save_button")

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

        # Connect buttons
        self.load_button.clicked.connect(self.open_file_dialog)
        self.clear_button.clicked.connect(self.clear_file_list)
        search_action.triggered.connect(self.search_musicbrainz)
        submit_action.triggered.connect(self.open_submission_dialog)
        self.remove_button.clicked.connect(self.remove_selected_files)
        self.file_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.save_button.clicked.connect(self.save_metadata)
        self.change_art_button.clicked.connect(self.change_album_art)
        self.delete_art_button.clicked.connect(self.delete_album_art)

        # Connect contextual help
        self.setMouseTracking(True)
        for name, widget in [
            ("load_button", self.load_button),
            ("musicbrainz_button", self.musicbrainz_button),
            ("remove_button", self.remove_button),
            ("clear_button", self.clear_button),
            ("save_button", self.save_button),
            ("album_art_label", self.album_art_label),
            ("change_art_button", self.change_art_button),
            ("delete_art_button", self.delete_art_button),
            ("file_list", self.file_list)
        ]:
            if hasattr(widget, 'enterEvent'):
                widget.enterEvent = lambda event, name=name: self.update_info_label(
                    event, name)
            if hasattr(widget, 'leaveEvent'):
                widget.leaveEvent = lambda event: self.clear_info_label(event)

        for tag, key in TAG_MAP.items():
            if key in self.fields:
                self.fields[tag].enterEvent = lambda event, name=f"{key}_input": self.update_info_label(
                    event, name)
                self.fields[tag].leaveEvent = lambda event: self.clear_info_label(
                    event)

        # Initialize UI
        self.musicbrainz_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        self.save_button.setEnabled(False)

        self.progress_bar = QProgressBar()
        self.progress_bar.hide()

        # Add widgets directly to the status bar instead of a layout
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.addPermanentWidget(self.info_label, 1)
        self.status_bar.addPermanentWidget(self.progress_bar, 0)

        self.status_bar.showMessage(
            "Ready to work. Drag and drop files or use 'Load Files'.")
        self.setAcceptDrops(True)

    def update_info_label(self, event, name):
        """Updates the info box with the widget's description."""
        help_text = HELP_TEXT.get(
            name, "No information available for this element.")
        self.info_label.setText(help_text)

    def clear_info_label(self, event):
        """Clears the info box when the mouse leaves the widget."""
        self.info_label.setText(
            "Hover over an element to see its description.")

    def on_processing_started(self):
        self.save_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        self.progress_bar.show()
        QApplication.setOverrideCursor(Qt.WaitCursor)

    def on_processing_progress(self, current, total):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)

    def on_processing_finished(self, results):
        QApplication.restoreOverrideCursor()
        self.progress_bar.hide()

        if "saved_count" in results:
            saved_count = results["saved_count"]
            total_files = results["total_files"]
            errors = results["errors"]

            self.refresh_file_list_after_save()

            if errors:
                error_msg = "\n".join(errors)
                QMessageBox.warning(
                    self, "Partial Save", f"Saved {saved_count} of {total_files} files.\n\nSome errors occurred:\n{error_msg}")

            self.status_bar.showMessage(
                f"Saved {saved_count} of {total_files} file(s) successfully!", 5000)
            self.art_is_dirty = False

        self.on_selection_changed()

    def on_processing_error(self, message):
        QApplication.restoreOverrideCursor()
        self.progress_bar.hide()
        self.on_selection_changed()
        QMessageBox.critical(self, "Processing Error", str(message))
        self.status_bar.showMessage("Operation failed.", 5000)

    def refresh_file_list_after_save(self):
        """Refreshes the metadata of the list items after saving."""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            path = item.data(Qt.UserRole)
            try:
                audio = mutagen.File(path, easy=True)
                if audio:
                    title = audio.get('title', [''])[0]
                    artist = audio.get('artist', [''])[0]
                    item.setText(
                        f"{os.path.basename(path)} - {title} by {artist}")
            except Exception as e:
                print(f"Failed to refresh list item for {path}: {e}")

    def clear_file_list(self):
        reply = QMessageBox.question(
            self, "Clear File List", "Are you sure you want to remove all files from the list?\nThis action cannot be undone.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.file_list.clear()
            self.file_paths.clear()
            self.scroll_area.setVisible(False)
            self.musicbrainz_button.setEnabled(False)
            self.clear_button.setEnabled(False)
            self.remove_button.setEnabled(False)
            self.save_button.setEnabled(False)
            self.status_bar.showMessage("File list cleared.")

    def remove_selected_files(self):
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Files Selected",
                                "Please select the files you want to remove.")
            return

        reply = QMessageBox.question(
            self, "Remove Files", f"Are you sure you want to remove {len(selected_items)} file(s) from the list?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            paths_to_remove = [item.data(Qt.UserRole)
                               for item in selected_items]
            for path in paths_to_remove:
                if path in self.file_paths:
                    self.file_paths.remove(path)

            for item in selected_items:
                self.file_list.takeItem(self.file_list.row(item))

            self.on_selection_changed()
            self.status_bar.showMessage(
                f"{len(selected_items)} file(s) removed from the list.", 5000)

    def on_selection_changed(self):
        selected_items = self.file_list.selectedItems()
        num_selected = len(selected_items)
        is_enabled = num_selected > 0

        # Enable/disable main buttons
        self.musicbrainz_button.setEnabled(is_enabled)
        self.save_button.setEnabled(is_enabled)
        self.remove_button.setEnabled(is_enabled)
        self.clear_button.setEnabled(self.file_list.count() > 0)

        # Logic for editing
        if num_selected == 0:
            self.scroll_area.setVisible(False)
        else:
            self.scroll_area.setVisible(True)
            self.save_button.setEnabled(True)
            self.musicbrainz_button.setEnabled(True)

            if num_selected == 1:
                self.art_is_dirty = False
                self.current_art_data = None
                self.current_art_mime = None
                self.update_editor_for_single(
                    selected_items[0].data(Qt.UserRole))
            else:
                self.art_is_dirty = False
                self.current_art_data = None
                self.current_art_mime = None
                self.update_editor_for_batch(num_selected)

    def on_item_moved(self, source_row, target_row):
        """Updates the internal list of file paths when an item is moved."""
        if source_row != target_row:
            item_data = self.file_paths.pop(source_row)
            self.file_paths.insert(target_row, item_data)
            # No need to reload the UI, just the internal list

    def update_editor_for_single(self, path):
        if not path:
            return
        self.title_label.setText(f"Editing: {os.path.basename(path)}")
        for tag_name in self.fields:
            self.checkboxes[tag_name].setVisible(False)
            self.fields[tag_name].setPlaceholderText("")
        self.art_buttons_widget.setVisible(True)
        self.scroll_area.setVisible(True)
        try:
            audio = mutagen.File(path, easy=True)
            if audio is None:
                raise ValueError("Could not load audio file with mutagen.")
            for display_name, key in TAG_MAP.items():
                if key in audio:
                    self.fields[display_name].setText(audio.get(key, [''])[0])
                else:
                    self.fields[display_name].clear()
            self.load_album_art(path)
        except Exception as e:
            self.status_bar.showMessage(
                f"Could not read file: {os.path.basename(path)} - {e}", 5000)
            self.scroll_area.setVisible(False)

    def update_editor_for_batch(self, count):
        self.title_label.setText(f"Batch Editing {count} Files")
        self.album_art_label.setText(
            "Album art can be changed\nfor all selected files")
        self.album_art_label.setPixmap(QPixmap())
        self.art_buttons_widget.setVisible(True)
        for tag_name in self.fields:
            self.checkboxes[tag_name].setVisible(True)
            self.checkboxes[tag_name].setChecked(False)
            self.fields[tag_name].clear()
            self.fields[tag_name].setPlaceholderText(
                "Check box to apply change")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = [url.toLocalFile() for url in event.mimeData().urls()]
        self.add_files_to_list(urls)

    def open_file_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Audio Files", "", f"Audio Files (*{' *'.join(VALID_AUDIO_EXTENSIONS)})")
        if files:
            self.add_files_to_list(files)

    def add_files_to_list(self, files):
        new_files = [f for f in files if f.lower().endswith(
            VALID_AUDIO_EXTENSIONS) and f not in self.file_paths]

        if not new_files:
            return

        self.status_bar.showMessage(f"Loading {len(new_files)} files...")
        self.progress_bar.show()

        # Disable UI during loading
        self.set_ui_enabled(False)

        run_in_thread(self, target_fn=self._load_files_in_thread, on_success=self.on_files_loaded,
                      on_error=self.on_processing_error, args=(new_files,))

    def set_ui_enabled(self, enabled):
        self.load_button.setEnabled(enabled)
        self.musicbrainz_button.setEnabled(enabled)
        self.remove_button.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)
        self.save_button.setEnabled(enabled)
        self.file_list.setEnabled(enabled)

    def _load_files_in_thread(self, file_paths):
        results = []
        for i, file_path in enumerate(file_paths):
            try:
                audio = mutagen.File(file_path, easy=True)
                if audio is None:
                    raise TypeError("Could not open file with mutagen.")

                title = audio.get('title', [''])[0]
                artist = audio.get('artist', [''])[0]

                results.append({
                    'path': file_path,
                    'title': title,
                    'artist': artist,
                })
            except Exception as e:
                results.append(
                    {'path': file_path, 'error': str(e), 'success': False})

            self.processing_progress.emit(i + 1, len(file_paths))
        return results

    def on_files_loaded(self, results):
        self.progress_bar.hide()

        for result in results:
            if 'error' not in result:
                self.file_paths.append(result['path'])

                # Create item and set data and text
                item = QListWidgetItem()
                item.setData(Qt.UserRole, result['path'])
                item.setText(
                    f"{os.path.basename(result['path'])} - {result['title']} by {result['artist']}")
                item.setIcon(qta.icon('fa5s.file-audio', color='#A0A0A0'))
                self.file_list.addItem(item)
            else:
                self.status_bar.showMessage(
                    f"Error adding file {result['path']}: {result['error']}", 5000)

        self.set_ui_enabled(True)
        self.clear_button.setEnabled(self.file_list.count() > 0)
        self.remove_button.setEnabled(self.file_list.count() > 0)
        self.save_button.setEnabled(self.file_list.count() > 0)
        self.status_bar.showMessage(f"{len(self.file_paths)} file(s) added.")

    def load_album_art(self, path):
        try:
            audio_raw = mutagen.File(path)
            if audio_raw is None:
                raise ValueError("Could not load the file.")

            artwork = None
            if 'APIC:' in audio_raw:
                artwork = audio_raw.get('APIC:').data
            elif 'covr' in audio_raw:
                artwork = audio_raw.get('covr')[0]
            elif audio_raw.pictures:
                artwork = audio_raw.pictures[0].data

            if artwork:
                pixmap = QPixmap()
                pixmap.loadFromData(artwork)
                scaled_pixmap = pixmap.scaled(self.album_art_label.width(),
                                              self.album_art_label.height(),
                                              Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.album_art_label.setPixmap(scaled_pixmap)
                self.album_art_label.setText("")
            else:
                self.album_art_label.setText("No Album Art")
                self.album_art_label.setPixmap(QPixmap())

        except Exception as e:
            self.album_art_label.setText("Error Loading Art")
            self.album_art_label.setPixmap(QPixmap())
            self.status_bar.showMessage(
                f"Error in load_album_art for {os.path.basename(path)}: {e}", 4000)

    def change_album_art(self):
        image_path, _ = QFileDialog.getOpenFileName(
            self, "Select Album Art", "", "Image Files (*.jpg *.jpeg *.png)")
        if image_path:
            try:
                pixmap = QPixmap(image_path)
                if pixmap.isNull():
                    raise ValueError("Invalid image file.")

                resized_pixmap = pixmap.scaled(
                    500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                byte_array = QByteArray()
                buffer = QBuffer(byte_array)
                buffer.open(QBuffer.WriteOnly)
                resized_pixmap.save(buffer, "PNG")

                self.current_art_data = byte_array.data()
                self.current_art_mime = 'image/png'

                scaled_for_display = resized_pixmap.scaled(
                    self.album_art_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.album_art_label.setPixmap(scaled_for_display)
                self.album_art_label.setText("")
                self.art_is_dirty = True
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Could not load or resize image: {e}")

    def delete_album_art(self):
        reply = QMessageBox.question(
            self, "Confirm Deletion", "Are you sure you want to delete the album art for the selected file(s)?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.current_art_data = b''
            self.current_art_mime = None
            self.art_is_dirty = True
            self.album_art_label.setText("Art will be deleted on save")
            self.album_art_label.setPixmap(QPixmap())

    def save_metadata(self):
        selected_paths = [item.data(Qt.UserRole)
                          for item in self.file_list.selectedItems()]
        if not selected_paths:
            return

        tags_to_save = {}
        is_batch_mode = len(selected_paths) > 1

        if is_batch_mode:
            for tag_display, checkbox in self.checkboxes.items():
                if checkbox.isChecked():
                    tags_to_save[tag_display] = self.fields[tag_display].text()
        else:
            for tag_display, field in self.fields.items():
                tags_to_save[tag_display] = field.text()

        art_data = self.current_art_data if self.art_is_dirty else None
        art_mime = self.current_art_mime if self.art_is_dirty else None

        self.file_processor_worker.process_and_save(
            selected_paths, tags_to_save, art_data, art_mime)

    def search_musicbrainz(self):
        selected_paths = [item.data(Qt.UserRole)
                          for item in self.file_list.selectedItems()]
        if not selected_paths:
            QMessageBox.warning(
                self, "No Files Selected", "Please select a file to pre-fill the MusicBrainz search.")
            return

        dialog = SearchDialog(self)
        try:
            audio = mutagen.File(selected_paths[0], easy=True)
            if audio is not None:
                dialog.artist_input.setText(
                    audio.get('albumartist', audio.get('artist', ['']))[0])
                dialog.album_input.setText(audio.get('album', [''])[0])
                if dialog.artist_input.text() or dialog.album_input.text():
                    dialog.search()
        except Exception as e:
            self.status_bar.showMessage(
                f"Could not pre-fill search: {e}", 3000)

        if dialog.exec_() == QDialog.Accepted:
            release_id = dialog.get_selected_release_id()
            if release_id:
                self.fetch_release_data(release_id)

    def fetch_release_data(self, release_id):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.status_bar.showMessage(
            "Fetching release data from MusicBrainz...")
        run_in_thread(self, target_fn=self._fetch_release_and_art,
                      on_success=self.apply_musicbrainz_data, on_error=self.show_network_error, args=(release_id,))

    def _fetch_release_and_art(self, release_id):
        includes = ["artists", "recordings", "artist-credits",
                    "release-groups", "url-rels", "labels"]
        release = musicbrainzngs.get_release_by_id(
            release_id, includes=includes)['release']
        art_data, art_mime = None, None
        try:
            headers = {
                'User-Agent': f'{APP_NAME}/{APP_VERSION} ({CONTACT_EMAIL})'}
            art_response = requests.get(
                f"https://coverartarchive.org/release/{release_id}/front-500", timeout=15, headers=headers)
            art_response.raise_for_status()
            art_data = art_response.content
            art_mime = art_response.headers.get('Content-Type', 'image/jpeg')
        except requests.exceptions.RequestException:
            pass
        return release, art_data, art_mime

    def apply_musicbrainz_data(self, data):
        QApplication.restoreOverrideCursor()
        release, art_data, art_mime = data
        selected_paths = [item.data(Qt.UserRole)
                          for item in self.file_list.selectedItems()]

        tracks = release['medium-list'][0]['track-list']
        if len(selected_paths) != len(tracks):
            QMessageBox.warning(self, "Track Mismatch", f"You selected {len(selected_paths)} files, but the MusicBrainz release has {len(tracks)} tracks. "
                                "Please select the correct number of files and ensure they are sorted by track number.")
            self.status_bar.showMessage(
                "MusicBrainz tagging cancelled due to track mismatch.", 5000)
            return

        # Order files to ensure tags are applied correctly
        selected_paths.sort(key=lambda p: os.path.basename(p))

        self.status_bar.showMessage("Applying metadata. Please wait...")
        self.file_processor_worker.process_and_save_musicbrainz(
            selected_paths, release, art_data, art_mime)

    def show_network_error(self, e):
        QApplication.restoreOverrideCursor()
        self.status_bar.showMessage("Network error.", 5000)
        QMessageBox.critical(self, "Network Error",
                             f"A network error occurred:\n{e}")

    def load_settings(self):
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)


def get_or_request_contact_email(settings):
    saved_email = settings.value("userContactEmail", None)
    if saved_email:
        return saved_email
    parent = QWidget()
    parent.setStyleSheet(STYLESHEET)
    QMessageBox.information(parent, "MusicBrainz Configuration", "To use MusicBrainz features, the app requires a contact email.\n\n"
                            "Please enter your email address. It will only be used to identify you to the MusicBrainz API, as required by their terms of service.", QMessageBox.Ok)
    email, ok = QInputDialog.getText(
        parent, "Contact Email for MusicBrainz", "Enter your email address:")
    if ok and email and "@" in email:
        settings.setValue("userContactEmail", email)
        return email
    elif ok:
        QMessageBox.warning(parent, "Invalid Email",
                            "You have not entered a valid email address. MusicBrainz features will be disabled.")
        return None
    else:
        QMessageBox.warning(parent, "Configuration Canceled",
                            "MusicBrainz features will be disabled until you set up a contact email.")
        return None


if __name__ == '__main__':
    from PyQt5.QtCore import QBuffer, QByteArray
    app = QApplication(sys.argv)
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    contact_email = get_or_request_contact_email(settings)
    if contact_email:
        musicbrainzngs.set_useragent(APP_NAME, APP_VERSION, contact_email)
    editor = Metagify()
    if not contact_email:
        editor.musicbrainz_button.setEnabled(False)
        editor.musicbrainz_button.setToolTip(
            "Configure a contact email to activate this feature.")
    editor.show()
    sys.exit(app.exec_())
