# TTi TF930 Production Tester GUI

A **Python GUI tool** for testing and monitoring the **TTi TF930 frequency counter**. Designed for lab and production environments, it provides **single frequency readings**, **timed automated tests**, and **real-time statistics**.

---

## Features

- **Single Read & Timed Test:** Quickly measure frequency or run extended tests with configurable duration.  
- **Pass/Fail Evaluation:** Automatically checks readings against a target frequency with tolerance in Hz or ppm.  
- **Real-Time Statistics:** Displays minimum, maximum, average, delta (max-min), and ppm drift.  
- **Threaded Operations:** Ensures GUI remains responsive during long measurement runs.  
- **COM Port Management:** Auto-detects available ports, supports connect, disconnect, and refresh.  
- **Progress & Status Updates:** Timed tests include progress bar and real-time status messages.  
- **Clearable Stats:** Reset measurements between tests without restarting the app.  
