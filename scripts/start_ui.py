"""Start the local app, wait for readiness, then open the browser (Windows launcher)."""
import http.client
from pathlib import Path
import subprocess
import sys
import time
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8501"


def healthy():
    connection = http.client.HTTPConnection("127.0.0.1", 8501, timeout=1)
    try:
        connection.request("GET", "/_stcore/health")
        return connection.getresponse().status == 200
    except OSError:
        return False
    finally:
        connection.close()


def main():
    if healthy():
        print("A Streamlit app is already running at " + URL + ". Opening it without starting another server.")
        webbrowser.open(URL)
        return
    child = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
                              "--server.address=127.0.0.1", "--server.port=8501",
                              "--browser.gatherUsageStats=false"], cwd=ROOT)
    try:
        deadline = time.monotonic() + 45
        while child.poll() is None and time.monotonic() < deadline:
            if healthy():
                webbrowser.open(URL)
                print("Protocol Review is open. Keep this window open; close it to stop the app.")
                child.wait()
                return
            time.sleep(0.3)
        if child.poll() is not None:
            raise SystemExit("The app could not start. Check the messages above.")
        raise SystemExit("The app did not become ready. Check that port 8501 is available.")
    except KeyboardInterrupt:
        pass
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()


if __name__ == "__main__":
    main()
