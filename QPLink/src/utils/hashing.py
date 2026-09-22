import hashlib
import os


def calculate_file_hash(filepath: str) -> str:
    """Computes SHA-256 hash of a file by reading it in chunks to avoid high memory spikes."""
    sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):  # Read 8KB at a time
                sha256.update(chunk)
        return sha256.hexdigest()
    except (PermissionError, FileNotFoundError):
        # Return an empty indicator if a file is currently locked/in-use by another application
        return ""


def extract_project_name(base_dir: str, current_filepath: str) -> str:
    """Isolates the first sub-directory name relative to S-Dir to use as the Project name.

    Example:
      S-Dir:            "C:/Vault"
      Current File:     "C:/Vault/ProjectAlpha/Subfolder/drawing.dwg"
      Returns:          "ProjectAlpha"
    """
    relative_path = os.path.relpath(current_filepath, base_dir)
    parts = relative_path.split(os.sep)

    # If the file is right in the root of S-Dir without a subfolder, fallback to a global bucket
    return parts[0] if len(parts) > 1 else "RootProject"

def extract_project_list(base_dir: str) -> list[str]:
    """Finds all subfolders of the base directory to use as a list of Project names."""
    return [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]