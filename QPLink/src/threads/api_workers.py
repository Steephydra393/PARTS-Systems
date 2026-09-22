import os
import requests

def send_dump(pending_uploads):
    """Sends the pending uploads to the server."""
    send = []
    for upload in pending_uploads:
        send.append({
            "filepath": str(upload["Fullpath"]),
            "hash": str(upload["Hash"]),
            "timestamp": float(upload["Timestamp"]),
        })

    print(f"[API_WORKER] Sending {len(send)} pending uploads to server...")
    
    response = requests.post("http://127.0.0.1:8001/qplink/dump_check", json=send)

    if response.status_code == 200:
        print(response.json())
        return response.json() 
    else:
        print(f"[API_WORKER] Failed to send uploads to server. Status code: {response.status_code}")
        try:
            print(f"Validation Error Details: {response.json()}") # <-- Add this line
        except Exception:
            print(f"Raw Response: {response.text}")
        return []

def upload_file(filepath, project):
    """Uploads a single file to the PARTS server."""
    print(f"[API_WORKER] Uploading file: {filepath} for project: {project}...")
    try:
        if not os.path.exists(filepath):
            print(f"[API_WORKER][ERROR] File does not exist locally: {filepath}")
            return False
            
        with open(filepath, "rb") as f:
            files = {"file": (os.path.basename(filepath), f)}
            data = {"project_name": project}
            response = requests.post("http://127.0.0.1:8001/qplink/upload_file", files=files, data=data)
            
        if response.status_code == 200:
            print(f"[API_WORKER] Successfully uploaded {filepath}")
            return True
        else:
            print(f"[API_WORKER] Failed to upload {filepath}. Status code: {response.status_code}")
            try:
                print(f"Validation Error Details: {response.json()}")
            except Exception:
                print(f"Raw Response: {response.text}")
            return False
    except Exception as e:
        print(f"[API_WORKER] Exception during upload of {filepath}: {e}")
        return False