import time
import requests
import win32gui
import win32process
import psutil

SERVER_URL = "http://localhost:8000/event"

def get_active_window():
    hwnd = win32gui.GetForegroundWindow()
    title = win32gui.GetWindowText(hwnd)

    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    try:
        process = psutil.Process(pid)
        name = process.name()
    except:
        name = "unknown"

    return {
        "app": name,
        "title": title,
        "timestamp": time.time()
    }

def send_event(event):
    try:
        requests.post(SERVER_URL, json=event)
    except:
        pass

if __name__ == "__main__":
    while True:
        event = get_active_window()
        print(event)
        send_event(event)
        time.sleep(1)