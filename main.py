import os
import threading

import customtkinter as ctk

from tkinter import filedialog, messagebox

from engine import FaceTimelapse


class TimelapseUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Timelapse Creator")
        self.geometry("650x600")
        self.minsize(650, 600)
        ctk.set_appearance_mode("dark")

        # Configuration Variables
        self.input_dir = ctk.StringVar()
        self.output_dir = ctk.StringVar()
        self.video_name = ctk.StringVar(value="MyTimelapse")
        self.fps = ctk.StringVar(value="24")
        self.auto_tune = ctk.BooleanVar(value=True)
        self.force_reprocess = ctk.BooleanVar(value=False)
        self.rename_files = ctk.BooleanVar(value=False)
        
        # Get the list of supported profiles directly from the Engine class
        self.available_profiles = list(FaceTimelapse.VIDEO_PROFILES.keys())
        self.format_profile = ctk.StringVar(value=self.available_profiles[0])
        
        # Resolution Handling
        self.res_options = {
            "1080p (16:9)": (1920, 1080),
            "720p (16:9)": (1280, 720),
            "4K (16:9)": (3840, 2160),
            "1080p (Portrait)": (1080, 1920),
            "Custom": None
        }
        self.res_selection = ctk.StringVar(value="1080p (16:9)")
        self.width = ctk.StringVar(value="1920")
        self.height = ctk.StringVar(value="1080")

        self.last_generated_path = None     # To store the path for the Play button

        self.setup_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        # Main Container to hold everything
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # 1. Header
        ctk.CTkLabel(main_container, text="Timelapse Creator", font=("Roboto", 24, "bold")).pack(pady=(0, 20))

        # 2. IO Section
        io_frame = ctk.CTkFrame(main_container)
        io_frame.pack(fill="x", pady=5)

        self.create_path_section(io_frame, "Input Folder:", self.input_dir, self.browse_input)
        self.create_path_section(io_frame, "Output Folder:", self.output_dir, self.browse_output)
        
        name_row = ctk.CTkFrame(io_frame, fg_color="transparent")
        name_row.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(name_row, text="Save Name:", width=100, anchor="e").pack(side="left", padx=5)
        ctk.CTkEntry(name_row, textvariable=self.video_name).pack(side="left", fill="x", expand=False, padx=5)

        # 3. Export Settings
        settings_frame = ctk.CTkFrame(main_container)
        settings_frame.pack(fill="x", pady=5)

        # For alingment
        ctk.CTkLabel(settings_frame, text="Export Settings", font=("Roboto", 16, "bold"), text_color="gray").pack(pady=10)

        # Resolution
        res_row = ctk.CTkFrame(settings_frame, fg_color="transparent")
        res_row.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(res_row, text="Resolution:", width=100, anchor="e").pack(side="left", padx=5)
        ctk.CTkOptionMenu(res_row, variable=self.res_selection, values=list(self.res_options.keys()), command=self.on_res_change).pack(side="left", padx=10)
        
        ctk.CTkLabel(res_row,text="", width=28, anchor="e").pack(side="left", padx=5)

        self.w_entry = ctk.CTkEntry(res_row, textvariable=self.width, width=60, state="disabled")
        self.w_entry.pack(side="left", padx=5)
        ctk.CTkLabel(res_row, text="x").pack(side="left")
        self.h_entry = ctk.CTkEntry(res_row, textvariable=self.height, width=60, state="disabled")
        self.h_entry.pack(side="left", padx=5)
        
        # FPS & Format
        tech_row = ctk.CTkFrame(settings_frame, fg_color="transparent")
        tech_row.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(tech_row, text="FPS:", width=100, anchor="e").pack(side="left", padx=5)
        ctk.CTkEntry(tech_row, textvariable=self.fps, width=60).pack(side="left", padx=10)
        
        ctk.CTkLabel(tech_row, text="Format:", width=100, anchor="e").pack(side="left", padx=5)
        self.format_profile = ctk.StringVar(value=list(FaceTimelapse.VIDEO_PROFILES.keys())[0])
        ctk.CTkOptionMenu(tech_row, variable=self.format_profile, values=list(FaceTimelapse.VIDEO_PROFILES.keys())).pack(side="left", padx=10)

        ## Extra Section (Checkboxes)
        extras_frame = ctk.CTkFrame(main_container)
        extras_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(extras_frame, text="Advanced & Extras", font=("Roboto", 16, "bold"), text_color="gray").pack(pady=10)
        check_container = ctk.CTkFrame(extras_frame, fg_color="transparent")
        check_container.pack()
        ctk.CTkCheckBox(check_container, text="Auto-Tune Exposure", variable=self.auto_tune).pack(side="left", padx=15)
        ctk.CTkCheckBox(check_container, text="Force Reprocess", variable=self.force_reprocess).pack(side="left", padx=15)
        ctk.CTkCheckBox(check_container, text="Auto-Rename Input (YYYYMMDD)", variable=self.rename_files).pack(side="left", padx=15)

        ## Execution Section
        self.progress_bar = ctk.CTkProgressBar(main_container, width=600)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=25)

        self.status_label = ctk.CTkLabel(main_container, text="System Ready", font=("Roboto", 14))
        self.status_label.pack()

        # Action Buttons Button
        btn_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        btn_frame.pack(pady=20)

        self.start_btn = ctk.CTkButton(btn_frame, text="Start Process", font=("Roboto", 18, "bold"),
                                       fg_color="green", hover_color="#006400",
                                       command=self.start_work_thread, width=200)
        self.start_btn.grid(row=0, column=0, padx=10)

        self.play_btn = ctk.CTkButton(btn_frame, text="Play Video", font=("Roboto", 18, "bold"),
                                      state="disabled", fg_color="#1f538d", hover_color="#0d3563",
                                      command=self.play_video, width=200)
        self.play_btn.grid(row=0, column=1, padx=10)

    def create_path_section(self, parent, label_text, var, cmd):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(row, text=label_text, width=100, anchor="e").pack(side="left", padx=5)
        ctk.CTkEntry(row, textvariable=var).pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(row, text="Browse", width=80, command=cmd).pack(side="left", padx=5)

    def add_path_row(self, frame, label_text, var, row):
        ctk.CTkLabel(frame, text=label_text).grid(row=row, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkEntry(frame, textvariable=var, width=400).grid(row=row, column=1, padx=10)
        cmd = self.browse_input if row == 0 else self.browse_output
        ctk.CTkButton(frame, text="Browse", width=80, command=cmd).grid(row=row, column=2, padx=10)

    def browse_input(self):
        path = filedialog.askdirectory()
        if path:
            self.input_dir.set(path)

    def browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)
    
    def on_res_change(self, choice):
        if choice == "Custom":
            self.w_entry.configure(state="normal")
            self.h_entry.configure(state="normal")
        else:
            self.w_entry.configure(state="disabled")
            self.h_entry.configure(state="disabled")
            w, h = self.res_options[choice]
            self.width.set(str(w))
            self.height.set(str(h))

    def update_progress(self, current, total):
        # Calculate percentage for progress bar (0.0 to 1.0)
        percent = current / total
        self.progress_bar.set(percent)
        self.status_label.configure(text=f"Processing image {current} of {total} ({(percent * 100):.1f}%)")
    
    def start_work_thread(self):
        # Validate paths
        if not self.input_dir.get() or not self.output_dir.get():
            self.status_label.configure(text="Error: Please select folders first!", text_color="red")
            return messagebox.showerror("Error", "Folders missing!")
        
        self.start_btn.configure(state="disabled")
        self.status_label.configure(text_color="white")

        # Start engine in background thread
        threading.Thread(target=self.run_engine, daemon=True).start()
    
    def play_video(self):
        """
        Opens the generated video with the system default player.
        """
        if self.last_generated_path and os.path.exists(self.last_generated_path):
            os.startfile(self.last_generated_path)
        else:
            messagebox.showerror("Error", "Video file not found!")
    
    def run_engine(self):
        try:
            # Disable play button at start of new run
            self.play_btn.configure(state="disabled")

            # 1. Initialize Engine
            engine = FaceTimelapse(
                input_dir=self.input_dir.get(),
                output_dir=self.output_dir.get(),
                force=self.force_reprocess.get(),
                auto_tune=self.auto_tune.get(),
                resolution=(int(self.width.get()), int(self.height.get()))
            )

            # 2. Rename files
            if self.rename_files.get():
                self.status_label.configure(text="Cleaning filenames...")
                engine.rename_input_files()

            # 3. Scan
            self.status_label.configure(text="Scanning directories...")
            engine.scan_images()

            # 4. Align
            self.status_label.configure(text="Aligning faces in parallel...")
            engine.run_alignment(progress_callback=self.update_progress)

            if engine.failed_images:
                messagebox.showwarning("Incomplete", f"{len(engine.failed_images)} images failed face detection. See report in output folder.")

            # 5. Video
            self.status_label.configure(text="Generating final video file...")
            final_path = engine.generate_video(
                video_name=self.video_name.get(),
                profile=self.format_profile.get(),
                fps=int(self.fps.get())
            )

            # 6. Store path and enable play button
            self.last_generated_path = os.path.abspath(final_path)
            self.play_btn.configure(state="normal")

            self.status_label.configure(text="Process Complete!", text_color="green")

        except Exception as e:
            self.status_label.configure(text=f"Error: {str(e)}", text_color="red")
        
        finally:
            self.start_btn.configure(state="normal")

    def on_closing(self):
        # Check if the start button is disabled (which means a process is likely active)
        if self.start_btn.cget("state") == "disabled":
            msg = "A timelapse is currently being generated. Closing now will stop all progress. Exit anyway?"
        else:
            msg = "Are you sure you want to close the application?"

        if messagebox.askokcancel("Confirm Exit", msg):
            print("Shutting down processes...")
            self.destroy()
            os._exit(0)

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support() 
    
    app = TimelapseUI()
    app.mainloop()
