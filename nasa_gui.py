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

# --- AUTOMATIC DEPENDENCY MANAGEMENT ---
try:
    import requests
except ImportError:
    print("Required 'requests' module is missing. Installing it automatically...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

try:
    from PIL import Image
except ImportError:
    print("Required 'pillow' module is missing. Installing it automatically...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
    from PIL import Image

# Import the existing downloader architecture from your stable file
from nasa_image_downloader import ModernNASADownloader, setup_logging, parse_args

# Custom Logging Handler to redirect logs directly into the GUI Textbox text area
class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record) + "\n")

class TaskTab(ctk.CTkFrame):
    """Represents a single, completely independent download task container."""
    def __init__(self, master, tab_id, app_master):
        super().__init__(master, fg_color="transparent")
        self.tab_id = tab_id
        self.app_master = app_master

        # Core thread queue handling locked to this specific tab instance
        self.log_queue = queue.Queue()
        self.image_queue = queue.Queue() # High-speed channel for pre-processed images
        self.target_dir = os.path.join(os.path.expanduser("~"), "Downloads", f"nasa_{tab_id.lower().replace(' ', '_')}")
        # --- THE MASTER SCROLLABLE VIEWPORT SOLUTION ---
        self.scroll_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_container.pack(fill="both", expand=True, padx=5, pady=5)

        # --- UI LAYOUT DESIGN (Preserved exactly from your original style) ---
        # 1. Search Parameter Input
        self.query_label = ctk.CTkLabel(self.scroll_container, text="Search Keyword (e.g., mars, apollo, nebula):", font=ctk.CTkFont(size=13))
        self.query_label.pack(pady=(10, 0))
        self.query_entry = ctk.CTkEntry(self.scroll_container, width=400, placeholder_text="Enter keyword here...")
        self.query_entry.insert(0, "nebula")
        self.query_entry.pack(pady=(0, 10))

        # NEW ENHANCEMENT: Max Image Limit Input Field
        self.limit_label = ctk.CTkLabel(self.scroll_container, text="Maximum Image Download Limit:", font=ctk.CTkFont(size=13))
        self.limit_label.pack(pady=(5, 0))
        self.limit_entry = ctk.CTkEntry(self.scroll_container, width=400, placeholder_text="Enter maximum image count (e.g., 50, 200, 500)...")
        self.limit_entry.insert(0, "200") 
        self.limit_entry.pack(pady=(0, 15))

        # 2. Directory Configuration Panel
        self.dir_frame = ctk.CTkFrame(self.scroll_container, fg_color="transparent")
        self.dir_frame.pack(pady=10)
        self.dir_label = ctk.CTkLabel(self.dir_frame, text=f"Output Path: ...{self.target_dir[-40:]}", font=ctk.CTkFont(size=12))
        self.dir_label.pack(side="left", padx=10)
        self.dir_button = ctk.CTkButton(self.dir_frame, text="Browse Folder", width=120, command=self._browse_folder)
        self.dir_button.pack(side="right", padx=10)

        # 3. Multithreading Worker Pool Slider Control
        self.slider_label = ctk.CTkLabel(self.scroll_container, text="Active Background Worker Threads: 3", font=ctk.CTkFont(size=13))
        self.slider_label.pack(pady=(15, 0))
        self.worker_slider = ctk.CTkSlider(self.scroll_container, from_=1, to=10, number_of_steps=9, command=self._update_slider_text)
        self.worker_slider.set(3)
        self.worker_slider.pack(pady=(0, 15))

        # 4. Operational Terminal Log Monitor (Live view)
        self.log_textbox = ctk.CTkTextbox(self.scroll_container, width=600, height=180, font=ctk.CTkFont(family="Courier", size=11))
        self.log_textbox.pack(pady=15)
        self.log_textbox.bind("<Enter>", lambda e: self.app_master.unbind_all("<MouseWheel>"))
        self.log_textbox.bind("<Leave>", lambda e: self.app_master.bind_all("<MouseWheel>", lambda ev: self.app_master.tab_view.tab(self.app_master.tab_view.get()).winfo_children()[0]._orchestrate_global_scroll(ev) if self.app_master.tab_view.get() else None))
        self.log_textbox.bind("<MouseWheel>", self._orchestrate_textbox_scroll)
        self.log_textbox.configure(state="disabled")

        # 5. Action Execution Button
        self.start_button = ctk.CTkButton(self.scroll_container, text="START ASYNCHRONOUS DOWNLOAD", font=ctk.CTkFont(size=14, weight="bold"), height=40, command=self._start_download_lifecycle)
        self.start_button.pack(pady=(10, 20))

                # --- MODERN LIVE GALLERY GRID ---
        self.gallery_label = ctk.CTkLabel(self.scroll_container, text="DOWNLOADED IMAGES GALLERY", font=ctk.CTkFont(size=14, weight="bold"))
        self.gallery_label.pack(pady=(20, 10))

        self.gallery_frame = ctk.CTkFrame(self.scroll_container, fg_color="transparent")
        self.gallery_frame.pack(pady=10, fill="x", expand=True)
        self.gallery_frame.grid_columnconfigure((0, 1, 2), weight=1, uniform="column")
        
        self.loaded_images = []
        self.image_counter = 0

        # Initialize background periodic queue check loop for this tab
        self.app_master.after(500, self._check_log_queue)
        self.app_master.after(500, self._check_image_queue)

    def _update_slider_text(self, value):
        self.slider_label.configure(text=f"Active Background Worker Threads: {int(value)}")

    def _browse_folder(self):
        selected_dir = ctk.filedialog.askdirectory()
        if selected_dir:
            self.target_dir = selected_dir
            self.dir_label.configure(text=f"Output Path: ...{self.target_dir[-40:]}")

    def _append_gui_log(self, text):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", text)
        # We remove the aggressive 'see(end)' command during active download streaming 
        # to let the Windows graphics engine focus 100% on rendering images smoothly.
        self.log_textbox.configure(state="disabled")


    def _check_log_queue(self):
        """Pure text logging registry queue loop."""
        while not self.log_queue.empty():
            try:
                log_msg = self.log_queue.get_nowait()
                self._append_gui_log(log_msg)
            except queue.Empty:
                break
        self.app_master.after(500, self._check_log_queue)

    def _check_image_queue(self):
        """High-speed hardware rendering pump utilizing lightweight action buttons to guarantee 0% lag."""
        while not self.image_queue.empty():
            try:
                file_path, _ = self.image_queue.get_nowait()
                file_name = os.path.basename(file_path)
                
                row = self.image_counter // 3
                col = self.image_counter % 3
                self.image_counter += 1
                
                img_button = ctk.CTkButton(
                    self.gallery_frame, 
                    text=f"Image #{self.image_counter}\n{file_name[:20]}...",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    height=45,
                    fg_color="#2E4053",
                    hover_color="#34495E",
                    command=lambda p=file_path: self._open_file_safely(p)
                )
                img_button.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")
                
            except queue.Empty:
                break
            except Exception:
                pass
        self.app_master.after(250, self._check_image_queue)

    def _orchestrate_global_scroll(self, event):
        """Universal high-speed canvas scroll engine that synchronizes old and new UI elements."""
        try:
            speed_multiplier = 50  # Adjust this multiplier to control scroll speed 
            
            self.scroll_container._parent_canvas.yview("scroll", int(-1 * (event.delta / 120) * speed_multiplier), "units")
        except Exception:
            pass

    def _open_file_safely(self, path):
        """Opens the downloaded asset using the host OS default viewer application."""
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.call(["open", path])
            else:
                subprocess.call(["xdg-open", path])
        except Exception as e:
            self._append_gui_log(f"[ERROR] Could not open image file: {e}\n")

    def _orchestrate_textbox_scroll(self, event):
        """Intelligent scroll handler for the log text area that falls back to global scroll if not scrollable."""
        try:
            start, end = self.log_textbox.yview()
            
            if start == 0.0 and end == 1.0:
                self._orchestrate_global_scroll(event)
            else:
                move = int(-1 * (event.delta / 120)) if event.delta else (1 if event.num == 5 else -1)
                self.log_textbox.yview_scroll(move * 2, "units")
        except Exception:
            pass

    def _display_new_thumbnail(self, file_path):
        """Safely injects a new high-speed action button into the grid layer."""
        try:
            if not os.path.exists(file_path):
                return

            file_name = os.path.basename(file_path)
            
            row = self.image_counter // 3
            col = self.image_counter % 3
            self.image_counter += 1
            
            img_button = ctk.CTkButton(
                self.gallery_frame, 
                text=f"Image #{self.image_counter}\n{file_name[:20]}...",
                font=ctk.CTkFont(size=11, weight="bold"),
                height=45,
                fg_color="#2E4053",
                hover_color="#34495E",
                command=lambda p=file_path: self._open_file_safely(p)
            )
            # Sűrű sorköz (padx=3, pady=3) a gyorsabb renderelésért
            img_button.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")
            
        except Exception:
            pass

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
            self.app_master.after(0, self._reset_ui_state)

    def _reset_ui_state(self):
        self.start_button.configure(state="normal", text="START ASYNCHRONOUS DOWNLOAD")
        self.query_entry.configure(state="normal")
        self.limit_entry.configure(state="normal")
        self.dir_button.configure(state="normal")
        self.worker_slider.configure(state="normal")

    def _start_download_lifecycle(self):
        # Prevent parallel process double activation
        self.start_button.configure(state="disabled", text="STREAMING ACTIVE...")
        self.query_entry.configure(state="disabled")
        self.limit_entry.configure(state="disabled")
        self.dir_button.configure(state="disabled")
        self.worker_slider.configure(state="disabled")

        os.makedirs(self.target_dir, exist_ok=True)

        try:
            image_limit = int(self.limit_entry.get())
        except ValueError:
            image_limit = 100

        import argparse
        args = argparse.Namespace(
            query=self.query_entry.get(),
            dir=self.target_dir,
            workers=int(self.worker_slider.get()),
            retries=3,
            retry_failed=False,
            min_size=100,
            max_images=image_limit,
            gui_parent=self,
        )

        # Crucial: Use a fully unique logger sub-channel identifier per tab to eliminate cross-talk muting
        logger = logging.getLogger(f"nasa_scraper_runtime_{self.tab_id.lower().replace(' ', '_')}")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()

        # Switch timers from 100ms to 250ms to drastically relieve event loop stress during fast scrolls
        self.app_master.after(500, self._check_log_queue)
        self.app_master.after(500, self._check_image_queue)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        q_handler = QueueHandler(self.log_queue)
        q_handler.setFormatter(formatter)
        logger.addHandler(q_handler)

        threading.Thread(target=self._run_downloader_thread, args=(args, logger), daemon=True).start()


class ModernNASAGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- WINDOW CONFIGURATION ---
        self.title("NASA Gallery Downloader - Multi-Task Workstation")
        self.geometry("750x780") # Slightly wider/taller to accommodate tabs perfectly
        ctk.set_appearance_mode("system")  # Use system theme (light/dark) by default
        ctk.set_default_color_theme("blue")

        self.tab_counter = 1

        # --- MANDATORY PROTOCOL DESTRUCTION INTERCEPTOR ---
        self.protocol("WM_DELETE_WINDOW", self._force_terminate_lifecycle)

        # --- MAIN UI FRAME LAYOUT ---
        # 1. Header Title
        self.title_label = ctk.CTkLabel(self, text="NASA MULTI-INSTANCE PIPELINE INTERFACE", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_label.pack(pady=(15, 5))

        # 2. Control Bar for adding tabs
        self.control_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.control_frame.pack(pady=5, fill="x")
        self.add_tab_button = ctk.CTkButton(self.control_frame, text="+ Open New Task Tab", font=ctk.CTkFont(size=12, weight="bold"), width=160, command=self._add_new_instance_tab)
        self.add_tab_button.pack(pady=5)

        # 3. Master Visual Tab View Module Container
        self.tab_view = ctk.CTkTabview(self, width=710)
        self.tab_view.pack(pady=(5, 15), padx=20, fill="both", expand=True)

        self.bind_all("<MouseWheel>", lambda e: self.tab_view.tab(self.tab_view.get()).winfo_children()[0]._orchestrate_global_scroll(e) if (self.tab_view.get() and self.tab_view.tab(self.tab_view.get()).winfo_children()) else None)

        self._add_new_instance_tab()

    def _add_new_instance_tab(self):
        """Spawns an entirely isolated parameter dashboard frame locked to a clean UI tab panel layout."""
        tab_title = f"Task Pipeline {self.tab_counter}"
        self.tab_counter += 1

        self.tab_view.add(tab_title)
        
        # Instantiate the design component container directly inside the newly created tab
        tab_content = TaskTab(self.tab_view.tab(tab_title), tab_title, self)
        tab_content.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Shift active interface focus to the newly spawned tab workspace
        self.tab_view.set(tab_title)

    def _force_terminate_lifecycle(self):
        """Hard exit event handler to release ports and flush thread pools instantly from the OS layer."""
        print("\n[SHUTDOWN] Hard intercept triggered. Terminating background runtime pipelines...")
        self.destroy()
        
        import os
        import signal
        os.kill(os.getpid(), signal.SIGTERM)


if __name__ == "__main__":
    app = ModernNASAGUI()
    app.mainloop()
