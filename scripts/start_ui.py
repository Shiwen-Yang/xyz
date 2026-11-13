"""Start the local app, wait for readiness, then open the browser (Linux, WSL and Windows)."""
import http.client
from pathlib import Path
import shutil
import subprocess
import sys
import time
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8501"


def open_browser():
    """Open the app; in WSL prefer wslview (wslu) so the Windows browser is used."""
    wslview = shutil.which("wslview")
    if wslview:
        subprocess.run([wslview, URL], check=False)
    elif not webbrowser.open(URL):
        print("Open " + URL + " in your browser.")


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
        open_browser()
        return
    child = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
                              "--server.address=127.0.0.1", "--server.port=8501",
                              "--browser.gatherUsageStats=false"], cwd=ROOT)
    try:
        deadline = time.monotonic() + 45
        while child.poll() is None and time.monotonic() < deadline:
            if healthy():
                open_browser()
                print("Protocol Review is running at " + URL + ". Keep this window open; press Ctrl+C or close it to stop the app.")
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
