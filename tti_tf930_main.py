import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import threading
import time

# --- Configuration Constants ---
BAUDRATE = 115200
TIMEOUT = 1
FONT_LARGE_FREQ = ("Arial", 32, "bold")
FONT_PASS_FAIL = ("Arial", 40, "bold")
FONT_STATS = ("Arial", 11)
FONT_STATUS_BAR = ("Arial", 10)


class TF930GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TTi TF930 Production Tester")
        self.root.geometry("600x600")

        # --- Style Configuration ---
        self.style = ttk.Style()
        self.style.configure("Pass.TLabel", foreground="green")
        self.style.configure("Fail.TLabel", foreground="red")
        self.style.configure("Info.TLabel", foreground="black")
        self.style.configure("Success.TLabel", foreground="blue")
        self.style.configure("Error.TLabel", foreground="red")

        # --- Variables ---
        self.serial_conn = None
        self.stop_event = threading.Event()
        self.single_read_measurements = []
        self.timed_test_measurements = []
        self.timed_test_running = False

        # --- Test Parameters ---
        self.target_freq = tk.DoubleVar(value=10_000.0)
        self.tolerance = tk.DoubleVar(value=10.0)
        self.tolerance_unit = tk.StringVar(value="Hz")

        # --- Layout Frames ---
        self._create_layout()

    # ===============================================================
    # GUI Setup
    # ===============================================================
    def _create_layout(self):
        frame_top = ttk.Frame(self.root)
        frame_top.pack(fill="x", padx=10, pady=5)

        self.frame_port = ttk.LabelFrame(frame_top, text="1. Connection")
        self.frame_port.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        self.frame_params = ttk.LabelFrame(frame_top, text="2. Test Parameters")
        self.frame_params.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        self.frame_measure = ttk.LabelFrame(self.root, text="3. Measurement")
        self.frame_measure.pack(fill="both", expand=True, padx=10, pady=10)

        self.frame_control = ttk.LabelFrame(self.root, text="4. Timed Test")
        self.frame_control.pack(padx=10, pady=5) # <-- Removed fill="x"

        self.frame_stats = ttk.LabelFrame(self.root, text="5. Statistics")
        self.frame_stats.pack(padx=10, pady=5) # <-- Removed fill="x"

        self.status_bar = ttk.Label(
            self.root,
            text="STATUS: Disconnected",
            style="Info.TLabel",
            relief="sunken",
            anchor="w",
            font=FONT_STATUS_BAR,
        )
        self.status_bar.pack(fill="x", side="bottom", ipady=2)

        self._setup_port_frame()
        self._setup_params_frame()
        self._setup_measurement_frame()
        self._setup_control_frame()
        self._setup_stats_frame()

    # ===============================================================
    # Section Setup
    # ===============================================================
    def _setup_port_frame(self):
        ttk.Label(self.frame_port, text="COM Port:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.port_combo = ttk.Combobox(self.frame_port, values=self._get_com_ports(), width=15)
        self.port_combo.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(self.frame_port, text="Refresh", command=self._refresh_ports).grid(row=0, column=2, padx=5)
        self.connect_btn = ttk.Button(self.frame_port, text="Connect", command=self._connect_serial)
        self.connect_btn.grid(row=1, column=0, columnspan=3, pady=5, sticky="ew")

    def _setup_params_frame(self):
        ttk.Label(self.frame_params, text="Target (Hz):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(self.frame_params, textvariable=self.target_freq, width=15).grid(row=0, column=1, columnspan=2, padx=5, pady=5)

        ttk.Label(self.frame_params, text="Tolerance:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(self.frame_params, textvariable=self.tolerance, width=8).grid(row=1, column=1, padx=5, pady=5)
        ttk.Combobox(self.frame_params, textvariable=self.tolerance_unit, values=["ppm", "Hz"], width=5, state="readonly").grid(row=1, column=2, padx=5, pady=5)

    def _setup_measurement_frame(self):
        self.pass_fail_label = ttk.Label(self.frame_measure, text="---", font=FONT_PASS_FAIL, anchor="center")
        self.pass_fail_label.pack(pady=(20, 10), fill="x")
        self.freq_label = ttk.Label(self.frame_measure, text="--- Hz", font=FONT_LARGE_FREQ, anchor="center")
        self.freq_label.pack(pady=10, fill="x")
        self.read_btn = ttk.Button(self.frame_measure, text="Single Read", command=self._start_single_read_thread, state=tk.DISABLED)
        self.read_btn.pack(pady=(10, 20), ipadx=10)

    def _setup_control_frame(self):
        ttk.Label(self.frame_control, text="Duration (s):").grid(row=0, column=0, padx=5, pady=5)
        self.duration_entry = ttk.Entry(self.frame_control, width=10)
        self.duration_entry.insert(0, "10")
        self.duration_entry.grid(row=0, column=1, padx=5)
        self.start_btn = ttk.Button(self.frame_control, text="Start Timed Test", command=self._start_timed_test_thread, state=tk.DISABLED)
        self.start_btn.grid(row=0, column=2, padx=5)
        self.stop_btn = ttk.Button(self.frame_control, text="Stop", command=self._stop_timed_test, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=3, padx=5)
        self.progress = ttk.Progressbar(self.frame_control, orient="horizontal", mode="determinate", length=300)
        self.progress.grid(row=1, column=0, columnspan=4, pady=5, padx=5, sticky="ew")

    def _setup_stats_frame(self):
        self.min_label = ttk.Label(self.frame_stats, text="Min: ---", font=FONT_STATS)
        self.max_label = ttk.Label(self.frame_stats, text="Max: ---", font=FONT_STATS)
        self.avg_label = ttk.Label(self.frame_stats, text="Avg: ---", font=FONT_STATS)
        self.delta_label = ttk.Label(self.frame_stats, text="Δ (Max-Min): ---", font=FONT_STATS)
        self.ppm_label = ttk.Label(self.frame_stats, text="Drift: --- ppm", font=FONT_STATS)
        self.clear_btn = ttk.Button(self.frame_stats, text="Clear Stats", command=self._clear_stats)

        self.min_label.grid(row=0, column=0, padx=10, sticky="w")
        self.max_label.grid(row=0, column=1, padx=10, sticky="w")
        self.avg_label.grid(row=1, column=0, padx=10, sticky="w")
        self.delta_label.grid(row=1, column=1, padx=10, sticky="w")
        self.ppm_label.grid(row=2, column=0, padx=10, sticky="w")
        self.clear_btn.grid(row=0, column=2, rowspan=3, padx=10, sticky="e")

    # ===============================================================
    # Serial Handling
    # ===============================================================
    def _get_com_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]

    def _refresh_ports(self):
        self.port_combo["values"] = self._get_com_ports()
        self._log_status("Port list refreshed.", "info")

    def _connect_serial(self):
        port = self.port_combo.get()
        if not port:
            messagebox.showwarning("Warning", "Please select a COM port.")
            return
        try:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
            self.serial_conn = serial.Serial(port, baudrate=BAUDRATE, timeout=TIMEOUT)
            self._log_status(f"✅ Connected to TF930 on {port}", "success")
            self.connect_btn.config(text="Disconnect", command=self._disconnect_serial)
            self.read_btn.config(state=tk.NORMAL)
            self.start_btn.config(state=tk.NORMAL)
        except serial.SerialException as e:
            self._log_status(f"Connection error: {e}", "error")

    def _disconnect_serial(self):
        if self.serial_conn:
            try:
                self.serial_conn.close()
            except Exception:
                pass
        self._log_status("Disconnected.", "info")
        self.connect_btn.config(text="Connect", command=self._connect_serial)
        self.read_btn.config(state=tk.DISABLED)
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED)

    # ===============================================================
    # Reading
    # ===============================================================
    def _parse_frequency(self, response):
        try:
            clean = response.strip().replace("Hz", "").replace(" ", "")
            return float(clean)
        except ValueError:
            return None

    def _read_frequency_sync(self):
        if not self.serial_conn or not self.serial_conn.is_open:
            self._log_status("No serial connection!", "error")
            return None
        try:
            self.serial_conn.write(b"FREQ?\r\n")
            time.sleep(0.25)
            resp = self.serial_conn.readline().decode(errors="ignore").strip()
            freq = self._parse_frequency(resp)
            return freq
        except Exception as e:
            self._log_status(f"Read error: {e}", "error")
            return None

    def _start_single_read_thread(self):
        threading.Thread(target=self._single_read, daemon=True).start()

    def _single_read(self):
        freq = self._read_frequency_sync()
        if freq is not None:
            self.single_read_measurements.append(freq)
        self.root.after(0, self._update_ui, freq)

    # ===============================================================
    # Timed Test
    # ===============================================================
    def _start_timed_test_thread(self):
        self.timed_test_running = True
        self.stop_event.clear()
        self.timed_test_measurements.clear()
        self._update_stats_display()

        self.start_btn.config(state=tk.DISABLED)
        self.read_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        threading.Thread(target=self._timed_test, daemon=True).start()

    def _stop_timed_test(self):
        self.stop_event.set()
        self.stop_btn.config(state=tk.DISABLED)

    def _timed_test(self):
        try:
            duration = float(self.duration_entry.get())
        except Exception:
            duration = 10.0
            self.root.after(0, lambda: self._log_status("Invalid duration, using 10s.", "error"))

        start_time = time.time()
        end_time = start_time + duration

        self.root.after(0, lambda: self._log_status("Timed test running...", "info"))
        self.root.after(0, lambda: self.progress.config(value=0))

        try:
            while not self.stop_event.is_set() and time.time() < end_time:
                freq = self._read_frequency_sync()
                if freq is not None:
                    # Append immediately to the timed test list
                    self.timed_test_measurements.append(freq)
                    # Update UI
                    self.root.after(0, self._update_ui, freq)

                elapsed = time.time() - start_time
                progress_value = min(100, (elapsed / duration) * 100)
                self.root.after(0, lambda v=progress_value: self.progress.config(value=v))

                # Poll stop event for responsiveness
                wait_start = time.time()
                while time.time() - wait_start < 1.0:
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.05)

        finally:
            self.timed_test_running = False
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.read_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.progress.config(value=100))
            
            if self.stop_event.is_set():
                self.root.after(0, lambda: self._log_status("Timed test stopped by user.", "info"))
            else:
                self.root.after(0, lambda: self._log_status("Timed test complete.", "success"))

            self.root.after(0, self._update_stats_display)

    # ===============================================================
    # Stats & Display
    # ===============================================================
    def _update_ui(self, freq):
        if freq is None:
            self.freq_label.config(text="ERROR")
            self.pass_fail_label.config(text="FAIL", style="Fail.TLabel")
            return

        self.freq_label.config(text=f"{freq:.8f} Hz")
        result, style = self._check_pass_fail(freq)
        self.pass_fail_label.config(text=result, style=style)

        # Just update stats display, do not append here
        self._update_stats_display()

    def _check_pass_fail(self, freq):
        try:
            target = self.target_freq.get()
            tol_val = self.tolerance.get()
            unit = self.tolerance_unit.get()
            abs_tol = (tol_val / 1_000_000) * target if unit == "ppm" else tol_val
            if (target - abs_tol) <= freq <= (target + abs_tol):
                return "PASS", "Pass.TLabel"
            else:
                return "FAIL", "Fail.TLabel"
        except Exception:
            return "ERROR", "Error.TLabel"

    def _update_stats_display(self):
        data = self.timed_test_measurements if self.timed_test_measurements else self.single_read_measurements
        if not data:
            for lbl in [self.min_label, self.max_label, self.avg_label, self.delta_label, self.ppm_label]:
                lbl.config(text=lbl.cget("text").split(":")[0] + ": ---")
            return

        min_val, max_val = min(data), max(data)
        avg_val = sum(data) / len(data)
        delta_val = max_val - min_val
        ppm_val = (delta_val / avg_val) * 1_000_000 if avg_val != 0 else 0

        self.min_label.config(text=f"Min: {min_val:.6f}")
        self.max_label.config(text=f"Max: {max_val:.6f}")
        self.avg_label.config(text=f"Avg: {avg_val:.6f}")
        self.delta_label.config(text=f"Δ (Max-Min): {delta_val:.6f}")
        self.ppm_label.config(text=f"Drift: {ppm_val:.3f} ppm")

    def _clear_stats(self):
        self.single_read_measurements.clear()
        self.timed_test_measurements.clear()
        self._update_stats_display()
        self.freq_label.config(text="--- Hz")
        self.pass_fail_label.config(text="---", style="Info.TLabel")
        self._log_status("Stats cleared.", "info")

    # ===============================================================
    # Status Bar
    # ===============================================================
    def _log_status(self, msg, level="info"):
        style_map = {
            "info": "Info.TLabel",
            "success": "Success.TLabel",
            "error": "Error.TLabel",
        }
        self.status_bar.config(text=f"STATUS: {msg}", style=style_map.get(level, "Info.TTLabel"))
        print(f"[{level.upper()}] {msg}")


# ===============================================================
# Main
# ===============================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = TF930GUI(root)
    root.mainloop()
