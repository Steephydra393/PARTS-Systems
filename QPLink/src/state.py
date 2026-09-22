import threading


class SystemStateManager:

    def __init__(self):
        self.lock = threading.Lock()

        # Initial system state
        self._current_state = "STARTING"

        # The default configuration structure required by PARTS API
        self._config = {
            "A-Up": True,
            "A-Up-Speed": 10,
            "T-PDF": True,
            "T-STL": True,
            "T-DWG": False,
            "S-Pause": False,
            "S-Dir": r"C:\Users\Cromi\Quarry",
            "Commands": [],
        }

    @property
    def current_state(self):
        with self.lock:
            return self._current_state

    def set_state(self, new_state: str):
        with self.lock:
            self._current_state = new_state
            print(f"[STATE CHANGE] -> {new_state}")

    def get_config(self) -> dict:
        with self.lock:
            # Returns a shallow copy to prevent external accidental modification
            return self._config.copy()

    def update_config(self, incoming_config: dict):
        with self.lock:
            # Only update keys that actually exist in our allowed configuration
            for key, value in incoming_config.items():
                if key in self._config:
                    self._config[key] = value
            print(f"[CONFIG UPDATE] Configuration synchronized with API.")