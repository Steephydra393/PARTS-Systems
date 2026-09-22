import os
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class _ExtensionEventHandler(FileSystemEventHandler):
    """Filters raw filesystem events down to ones matching an allowed extension list."""

    def __init__(self, allowed_extensions_getter, on_file_event):
        self._get_allowed = allowed_extensions_getter
        self._on_file_event = on_file_event

    def _maybe_handle(self, path):
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        if ext in self._get_allowed():
            self._on_file_event(os.path.normpath(path))

    def on_created(self, event):
        if not event.is_directory:
            self._maybe_handle(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._maybe_handle(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._maybe_handle(event.dest_path)


class FolderWatcher:
    """Attaches a watchdog observer to each project subfolder under a base directory,
    instead of repeatedly walking the whole tree on a timer. New project folders are
    attached automatically as they appear; folders that disappear are detached.

    allowed_extensions_getter: zero-arg callable returning the current list of
        allowed extensions (read live so config toggles take effect immediately).
    on_file_event: callable(full_path: str) invoked for every matching file, both
        for pre-existing files (one-time backfill on attach) and live changes.
    """

    def __init__(self, allowed_extensions_getter, on_file_event):
        self._observer = Observer()
        self._observer.start()
        self._watches = {}  # folder path -> watchdog ObservedWatch
        self._handler = _ExtensionEventHandler(allowed_extensions_getter, on_file_event)
        self._get_allowed = allowed_extensions_getter
        self._on_file_event = on_file_event
        self._lock = threading.Lock()

    def sync(self, project_folders):
        """project_folders: absolute paths to the currently-known project subfolders."""
        with self._lock:
            current = set(project_folders)
            watched = set(self._watches.keys())

            for folder in current - watched:
                if not os.path.isdir(folder):
                    continue
                self._backfill(folder)
                watch = self._observer.schedule(self._handler, folder, recursive=True)
                self._watches[folder] = watch
                print(f"[WATCHER] Attached to folder: {folder}")

            for folder in watched - current:
                watch = self._watches.pop(folder, None)
                if watch:
                    self._observer.unschedule(watch)
                    print(f"[WATCHER] Detached from folder: {folder}")

    def _backfill(self, folder):
        """One-time indexing of files that already existed before we attached a watch -
        watchdog only reports changes that happen after scheduling, not the current state."""
        allowed = self._get_allowed()
        for root, _dirs, files in os.walk(folder):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in allowed:
                    self._on_file_event(os.path.normpath(os.path.join(root, f)))

    def stop(self):
        self._observer.stop()
        self._observer.join()
