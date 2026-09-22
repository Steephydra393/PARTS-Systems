import sys
import threading
import time
from state import SystemStateManager
import requests

# At the top of main.py:
import os
from database.models import init_db, process_file_state, get_pending_uploads, clear_uploaded_items
from utils.hashing import calculate_file_hash, extract_project_name, extract_project_list
from utils.filenames import is_valid_part_filename
from threads.api_workers import send_dump, upload_file
from threads.folder_watcher import FolderWatcher

# Instantiate our central state manager
state_manager = SystemStateManager()

# Shared event to cleanly signal all threads to stop running
exit_event = threading.Event()

def api_heartbeat_worker():
    """Thread 1: Handles regular API check-ins and listens for 205 resets."""
    print("[INIT] API Heartbeat Thread started.")

    while not exit_event.is_set():
        current_state = state_manager.current_state
        config = state_manager.get_config()

        # Placeholder: This is where your requests.post() logic will go
        heatbeat_payload = {
            "state": current_state,
            "config": config,
            "timestamp": time.time(),
        }
        print(f"[API] Sending Heartbeat... | State: {current_state}")
        response = requests.post("http://127.0.0.1:8001/qplink/heartbeat", json=heatbeat_payload)

        if response.status_code == 205:
            # GET the latest configuration from the API
            print("[API] Received 205 Reset. Fetching new configuration...")
            try:
                config_response = requests.get("http://127.0.0.1:8001/qplink/config")
                if config_response.status_code == 200:
                    new_config = config_response.json()
                    state_manager.update_config(new_config)
                else:
                    print(f"[API][ERROR] Failed to fetch new config. Status Code: {config_response.status_code}")
            except Exception as e:
                print(f"[API][ERROR] Exception while fetching new config: {e}")
        elif response.status_code != 200:
            print(f"[API][ERROR] Heartbeat failed. Status Code: {response.status_code}")
        else:
            print(f"[API] Heartbeat successful. Status Code: {response.status_code}")


        # Simulated API response evaluation
        # In production, check if 'Exit' is inside config['Commands']
        if "Exit" in config.get("Commands", []):
            print("[API] 'Exit' command received from API.")
            exit_event.set()
            break

        exit_event.wait(timeout=5)

    print("[SHUTDOWN] API Heartbeat Thread stopped.")


def _get_allowed_extensions():
    """Reads the live config so T-PDF/T-STL/T-DWG toggles take effect immediately."""
    config = state_manager.get_config()
    allowed = []
    if config["T-PDF"]:
        allowed.append(".pdf")
    if config["T-STL"]:
        allowed.append(".stl")
    if config["T-DWG"]:
        allowed.append(".dwg")
    return allowed


# Mutable holder so the watcher's event callback always sees the latest S-Dir,
# even though it's set up once and fires asynchronously between scanner ticks.
_current_base_dir = [None]


def _on_watched_file_event(full_path):
    config = state_manager.get_config()
    if not config["A-Up"] or config["S-Pause"]:
        return  # Paused - ignore events until resumed rather than queuing them

    filename = os.path.basename(full_path)
    if not is_valid_part_filename(filename):
        return  # Doesn't match PPP-YY-[P]NNNN.ext - never worth queuing

    base_dir = _current_base_dir[0]
    if not base_dir:
        return

    project = extract_project_name(base_dir, full_path)

    file_hash = calculate_file_hash(full_path)
    if not file_hash:
        return  # Skip if file was locked

    was_modified = process_file_state(full_path, project, file_hash)
    if was_modified:
        print(f"[SCANNER] Staged changed file: {filename} in Project: {project}")


def file_scanner_worker():
    """Thread 3: attaches to each project folder under S-Dir (via watchdog) instead of
    walking the whole tree every cycle, hashes changed files, records to SQLite, and
    uploads at A-Up-Speed."""
    print("[INIT] File Scanner Thread started.")

    watcher = FolderWatcher(_get_allowed_extensions, _on_watched_file_event)

    try:
        while not exit_event.is_set():
            config = state_manager.get_config()
            if config["A-Up"] and not config["S-Pause"] and config["S-Dir"]:
                base_dir = config["S-Dir"]
                _current_base_dir[0] = base_dir

                project_names = extract_project_list(base_dir)
                print("[SCANNER][DEBUG] Project Names: ", project_names)

                state_manager.set_state("SCANNING_FILES")

                project_folders = [os.path.join(base_dir, name) for name in project_names]
                watcher.sync(project_folders)

                pending_uploads = get_pending_uploads()
                if len(pending_uploads) > 0:
                    print(f"[SCANNER] Pending uploads: {len(pending_uploads)}")
                    requested = send_dump(pending_uploads)

                    if len(requested) > 0:
                        print(f"[SCANNER] API Requested: {len(requested)} files.")

                        # Create mapping from Filename -> pending upload info
                        upload_map = {item["Filename"]: item for item in pending_uploads}

                        # Upload requested files
                        for req in requested:
                            filename = req.get("filename")
                            item = upload_map.get(filename)
                            if item:
                                success = upload_file(item["Fullpath"], item["Project"])
                                if success:
                                    clear_uploaded_items([item["Fullpath"]])

                if state_manager.current_state == "SCANNING_FILES":
                    state_manager.set_state("IDLE")

            delay = max(0.1, config["A-Up-Speed"])
            exit_event.wait(timeout=delay)
    finally:
        watcher.stop()

    print("[SHUTDOWN] File Scanner Thread stopped.")

if __name__ == "__main__":
    state_manager.set_state("STARTING")

    if __name__ == "__main__":
        init_db()

    # Define our worker threads
    threads = [
        # threading.Thread(target=api_heartbeat_worker, name="API-Thread"),
        threading.Thread(target=file_scanner_worker, name="Scanner-Thread"),
    ]

    # Start all threads
    for thread in threads:
        thread.start()

    state_manager.set_state("IDLE")

    # Contextual Console instructions for testing this base layer local shell
    try:
        while not exit_event.is_set():
            # Keep primary main program thread alive
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[KeyboardInterrupt] Initiating graceful local shutdown...")
        exit_event.set()

    # Graceful Teardown
    state_manager.set_state("EXITING")
    for thread in threads:
        thread.join()

    print("All subsystems successfully terminated. Application out.")
    sys.exit(0)