import threading
import time
import webview
from demo_server import app  # Aapka existing flask server


def start_server():
  """Background mein Flask server ko chalata hai."""
  app.run(host="127.0.0.1", port=8000, debug=False, use_reloader=False)


if __name__ == "__main__":
  # 1. Background thread mein backend server start karein
  t = threading.Thread(target=start_server, daemon=True)
  t.start()

  # 2. Server ready hone ke liye 1 second wait karein
  time.sleep(1)

  # 3. Native App Window open karein (No browser URL bar, pure native software look)
  window = webview.create_window(
      title="DHWANI-KAVACH — Live Voice Clone Shield",
      url="http://127.0.0.1:8000",
      width=1280,
      height=800,
      resizable=True,
      min_size=(1024, 700),
  )

  # 4. App start karein (Window close karne par server bhi automatically band ho jayega)
  webview.start()