import os
import sys
import subprocess
import threading
import queue
import logging

# --- AUTOMATIC GUI DEPENDENCY MANAGEMENT ---
try:
    import customtkinter as ctk
except ImportError:
    print("The 'customtkinter' module is missing. Installing it automatically...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk

# Import the existing downloader architecture from your stable file
from nasa_image_downloader import ModernNASADownloader, setup_logging, parse_args

# Custom Logging Handler to redirect logs directly into the GUI Textbox text area
class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record) + "\n")

class ModernNASAGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- WINDOW CONFIGURATION ---
        # Expanded height slightly to perfectly fit the new limit input field
        self.title("NASA Gallery Downloader - Modern Edition")
        self.geometry("700x620")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Core thread queue handling
        self.log_queue = queue.Queue()
        self.target_dir = os.path.join(os.path.expanduser("~"), "Downloads", "nasa_gui_downloads")

        # --- MANDATORY PROTOCOL DESTRUCTION INTERCEPTOR ---
        # This forces the operating system to forcefully kill all Python child threads when the GUI window 'X' is clicked.
        self.protocol("WM_DELETE_WINDOW", self._force_terminate_lifecycle)

        # --- UI LAYOUT DESIGN ---
        # 1. Header Title
        self.title_label = ctk.CTkLabel(self, text="NASA IMAGE STREAMING PIPELINE", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_label.pack(pady=(20, 10))

        # 2. Search Parameter Input
        self.query_label = ctk.CTkLabel(self, text="Search Keyword (e.g., mars, apollo, nebula):", font=ctk.CTkFont(size=13))
        self.query_label.pack(pady=(10, 0))
        self.query_entry = ctk.CTkEntry(self, width=400, placeholder_text="Enter keyword here...")
        self.query_entry.insert(0, "nebula")
        self.query_entry.pack(pady=(0, 10))

        # NEW ENHANCEMENT: Max Image Limit Input Field
        self.limit_label = ctk.CTkLabel(self, text="Maximum Image Download Limit:", font=ctk.CTkFont(size=13))
        self.limit_label.pack(pady=(5, 0))
        self.limit_entry = ctk.CTkEntry(self, width=400, placeholder_text="Enter maximum image count (e.g., 50, 200, 500)...")
        self.limit_entry.insert(0, "200") # Defaulted to 200 to test pagination loops out of the box
        self.limit_entry.pack(pady=(0, 15))

        # 3. Directory Configuration Panel
        self.dir_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.dir_frame.pack(pady=10)
        self.dir_label = ctk.CTkLabel(self.dir_frame, text=f"Output Path: ...{self.target_dir[-40:]}", font=ctk.CTkFont(size=12))
        self.dir_label.pack(side="left", padx=10)
        self.dir_button = ctk.CTkButton(self.dir_frame, text="Browse Folder", width=120, command=self._browse_folder)
        self.dir_button.pack(side="right", padx=10)

        # 4. Multithreading Worker Pool Slider Control
        self.slider_label = ctk.CTkLabel(self, text="Active Background Worker Threads: 3", font=ctk.CTkFont(size=13))
        self.slider_label.pack(pady=(15, 0))
        self.worker_slider = ctk.CTkSlider(self, from_=1, to=10, number_of_steps=9, command=self._update_slider_text)
        self.worker_slider.set(3)
        self.worker_slider.pack(pady=(0, 15))

        # 5. Operational Terminal Log Monitor (Live view)
        self.log_textbox = ctk.CTkTextbox(self, width=600, height=180, font=ctk.CTkFont(family="Courier", size=11))
        self.log_textbox.pack(pady=15)
        self.log_textbox.configure(state="disabled")

        # 6. Action Execution Button
        self.start_button = ctk.CTkButton(self, text="START ASYNCHRONOUS DOWNLOAD", font=ctk.CTkFont(size=14, weight="bold"), height=40, command=self._start_download_lifecycle)
        self.start_button.pack(pady=(10, 20))

        # Initialize background periodic queue check loop
        self.after(100, self._check_log_queue)

    def _force_terminate_lifecycle(self):
        """Hard exit event handler to release ports and flush thread pools instantly from the OS layer."""
        print("\n[SHUTDOWN] Hard intercept triggered. Terminating background runtime pipelines...")
        self.destroy()
        
        # OS-level hard kill: shuts down the entire process instantly from the Windows kernel
        import os
        import signal
        os.kill(os.getpid(), signal.SIGTERM)
        
    def _update_slider_text(self, value):
        self.slider_label.configure(text=f"Active Background Worker Threads: {int(value)}")

    def _browse_folder(self):
        selected_dir = ctk.filedialog.askdirectory()
        if selected_dir:
            self.target_dir = selected_dir
            self.dir_label.configure(text=f"Output Path: ...{self.target_dir[-40:]}")

    def _append_gui_log(self, text):
        """Appends log messages to the GUI text area while maintaining scroll position."""
        is_at_bottom = self.log_textbox.yview()[1] >= 0.9

        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", text)
        
        if is_at_bottom:
            self.log_textbox.see("end")
            
        self.log_textbox.configure(state="disabled")

    def _check_log_queue(self):
        """Reads log variables pushed from the background threads without locking the GUI window."""
        while not self.log_queue.empty():
            try:
                log_msg = self.log_queue.get_nowait()
                self._append_gui_log(log_msg)
            except queue.Empty:
                break
        self.after(100, self._check_log_queue)

    def _run_downloader_thread(self, args, logger):
        """Isolated background thread handling blocking network IO drops cleanly."""
        try:
            from nasa_image_downloader import ModernNASADownloader
            downloader = ModernNASADownloader(args, logger)
            downloader.run()
        except Exception as e:
            logger.critical(f"GUI Thread runner suffered critical crash framework mapping: {e}")
        finally:
            # Re-enable the interface controls safely upon pipeline exit
            self.after(0, self._reset_ui_state)

    def _reset_ui_state(self):
        self.start_button.configure(state="normal", text="START ASYNCHRONOUS DOWNLOAD")
        self.query_entry.configure(state="normal")
        self.limit_entry.configure(state="normal") # Added to reset routine
        self.dir_button.configure(state="normal")
        self.worker_slider.configure(state="normal")

    def _start_download_lifecycle(self):
        # Prevent parallel process double activation
        self.start_button.configure(state="disabled", text="STREAMING ACTIVE...")
        self.query_entry.configure(state="disabled")
        self.limit_entry.configure(state="disabled") # Added to disabling routine
        self.dir_button.configure(state="disabled")
        self.worker_slider.configure(state="disabled")

        os.makedirs(self.target_dir, exist_ok=True)

        # Parse user limit safely, fallback to 100 if input is invalid text string
        try:
            image_limit = int(self.limit_entry.get())
        except ValueError:
            image_limit = 100

        # Mock argument parameters parsing engine seamlessly to feed into your original class structure
        import argparse
        args = argparse.Namespace(
            query=self.query_entry.get(),
            dir=self.target_dir,
            workers=int(self.worker_slider.get()),
            retries=3,
            retry_failed=False,
            min_size=100,
            max_images=image_limit # Dynamic input injection
        )

        # Intercept main log structures and bind custom QueueHandler
        logger = logging.getLogger("nasa_scraper")
        logger.setLevel(logging.INFO)
        
        # Format configurations
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Attach the UI real-time queue pipe handler
        q_handler = QueueHandler(self.log_queue)
        q_handler.setFormatter(formatter)
        logger.addHandler(q_handler)

        # Instantly spawn the blocking execution routine to a dedicated core thread pool background
        threading.Thread(target=self._run_downloader_thread, args=(args, logger), daemon=True).start()

if __name__ == "__main__":
    app = ModernNASAGUI()
    app.mainloop()
