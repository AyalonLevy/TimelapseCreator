import re
import os
import sys
import cv2
import dlib
import multiprocessing

import numpy as np

from concurrent.futures import ProcessPoolExecutor
from datetime import datetime


def process_image_worker(task_data):
    """
    Global worker function executed by individual CPU cores. 
    Handles the compute-intensive task of face detection and image warping.
    task_data: tuple containing (in_path, out_path, settings_dict)
    """
    in_path, out_path, settings = task_data

    # 1. If file exists and force is False -> skip immediately
    if os.path.exists(out_path) and not settings['force']:
        return True, in_path
    
    # 2. Initialize dlib LOCALLY in this process
    # (Predictor path is passed via settings)
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(settings['predictor_path'])

    img = cv2.imread(in_path)
    if img is None:
        return False, in_path

    # 3. Auto-tune (CLAHE)
    if settings['auto_tune']:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        limg = cv2.merge((cl, a, b))
        img = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    
    # 4. Alignment Logic
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    rects = detector(gray, 0)

    if len(rects) == 0:
        return False, in_path   # Face not found
    
    # Get landmarks for the first face detected
    shape = predictor(gray, rects[0])

    # Extract left and right eye coordinates (indices 36-41 and 42-47)
    left_eye = np.mean([(shape.part(i).x, shape.part(i).y) for i in range(36, 42)], axis=0)
    right_eye = np.mean([(shape.part(i).x, shape.part(i).y) for i in range(42, 48)], axis=0)

    # Calculate angle and distance
    d_y = (right_eye[1] - left_eye[1])
    d_x = (right_eye[0] - left_eye[0])
    angle = np.degrees(np.arctan2(d_y, d_x))

    # Calculate scale factor
    scale = settings['output_size'][1] / float(h)

    # Calculate center point between eyes
    eye_center = (float((left_eye[0] + right_eye[0]) // 2),
                float((left_eye[1] + right_eye[1]) // 2))
    
    # Build the transformation matrix
    rot_mat = cv2.getRotationMatrix2D(eye_center, angle, scale)

    # Adjust the translation to center the eyes in the output frame
    rot_mat[0, 2] += (settings['output_size'][0] * 0.5 - eye_center[0])
    rot_mat[1, 2] += (settings['output_size'][1] * settings['offset_y'] - eye_center[1])

    output = cv2.warpAffine(img, rot_mat, settings['output_size'], borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))

    # Save output
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cv2.imwrite(out_path, output)
    
    return True, in_path


class FaceTimelapse:
    VIDEO_PROFILES = {
        "MP4 (Universal)": {"ext": "mp4", "fourcc": "mp4v"},
        "AVI (Legacy)": {"ext": "avi", "fourcc": "XVID"},
        "MOV (Apple)": {"ext": "mov", "fourcc": "mp4v"}
    }

    def __init__(self, input_dir, output_dir, force=False, auto_tune=True, resolution=(1920, 1080)):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.force = force
        self.auto_tune = auto_tune
        self.output_size = resolution
        self.offset_y = 0.45
        self.predictor_path = "shape_predictor_68_face_landmarks.dat"

        self.image_map = []
        self.failed_images = []

    def rename_input_files(self):
        """
        Standardizes input filenames to YYYYMMDD across all subfolders.
        """
        valid_name_pattern = re.compile(r"^\d{8}\.(jpg|jpeg)$", re.IGNORECASE)
        renamed_count = 0

        # os.walk ensures we dive into subdirectories like /2025/08/
        for root, _, files in os.walk(self.input_dir):
            for filename in files:
                # Filter for JPEGs only
                if not filename.lower().endswith((".jpg", ".jpeg", ".RC2")):
                    continue
                
                # Skip if already in YYYYMMDD format
                if valid_name_pattern.match(filename):
                    continue
                
                file_path = os.path.join(root, filename)
                
                try:
                    # Get file metadata (Modification Date)
                    m_time = os.path.getmtime(file_path)
                    date_prefix = datetime.fromtimestamp(m_time).strftime("%Y%m%d")
                    
                    ext = os.path.splitext(filename)[1].lower()
                    new_filename = f"{date_prefix}{ext}"
                    new_file_path = os.path.join(root, new_filename)

                    # Collision Handling: If 20260502.jpg exists, create 20260502_1.jpg
                    counter = 1
                    base_name = date_prefix
                    while os.path.exists(new_file_path):
                        new_filename = f"{base_name}_{counter}{ext}"
                        new_file_path = os.path.join(root, new_filename)
                        counter += 1

                    os.rename(file_path, new_file_path)
                    renamed_count += 1
                    
                except Exception as e:
                    # Log error to console for debugging without crashing the UI
                    print(f"[Rename Error] {filename}: {e}")

        print(f"Renaming complete. {renamed_count} files standardized.")

    def scan_images(self):
        """
        Walks through the directory and builds a list of JPGs.
        """
        print(f"Scanning {self.input_dir}...")
        temp_list = []
        for root, _, files in os.walk(self.input_dir):
            for f in files:
                if f.lower().endswith(("jpg", "jpeg")):
                    full_input_path = os.path.join(root, f)

                    # Recreate the relative path for the output
                    rel_path = os.path.relpath(full_input_path, self.input_dir)
                    full_output_path = os.path.join(self.output_dir, rel_path)
                    temp_list.append((full_input_path, full_output_path))
        
        # Sort by filename (YYYMMDD)
        self.image_map = sorted(temp_list, key=lambda x: os.path.basename(x[0]))
        print(f"Found {len(self.image_map)} images.")

    def run_alignment(self, progress_callback=None):
        """
        Executes alingment in parallel using all available cores.
        progress_callback: A function that accepts (current_index, total) to update a UI
        """
        num_cores = max(1, multiprocessing.cpu_count() - 1)
        total = len(self.image_map)

        # Prepare the settings dictionary for the workers
        settings = {
            'force': self.force,
            'auto_tune': self.auto_tune,
            'output_size': self.output_size,
            'offset_y': self.offset_y,
            'predictor_path': self.predictor_path
        }

        # Pack data for executor
        tasks = [(in_p, out_p, settings) for in_p, out_p in self.image_map]

        print(f"Using {num_cores} CPU cores for processing...")

        # ProcessPoolExecutor manages the core switching
        with ProcessPoolExecutor(max_workers=num_cores) as executor:
            for i, (success, path) in enumerate(executor.map(process_image_worker, tasks)):
                if not success:
                    self.failed_images.append(path)
                    print(f"\n[Warning] {path} failed to recognise a face")
                
                if progress_callback:
                    progress_callback(i + 1, total)
                else:
                    percent = ((i + 1) / total) * 100
                    sys.stdout.write(f"\rProgress: {percent:.2f}% ({i + 1}/{total})")
                    sys.stdout.flush()
        
        if self.failed_images:
            with open(os.path.join(self.output_dir, "failed_images_report.txt"), "w") as f:
                f.write("\n".join(self.failed_images))

        print("Alignment complete.")
    
    def generate_video(self, video_name="Timelapse", profile="MP4 (Universal)", fps=24):
        """
        Stitches the aligned images into a video.
        """
        if profile not in self.VIDEO_PROFILES:
            raise ValueError(f"Unsupported video profile: {profile}")
        
        selected = self.VIDEO_PROFILES.get(profile, self.VIDEO_PROFILES["MP4 (Universal)"])

        full_video_name = f"{video_name}.{selected['ext']}"

        # Define the codec and create VideoWriter object
        fourcc = cv2.VideoWriter_fourcc(*selected['fourcc'])
        video = cv2.VideoWriter(full_video_name, fourcc, fps, self.output_size)

        if not video.isOpened():
            raise RuntimeError(f"Failed to open VideoWriter with codec {selected['fourcc']}")
        
        print(f"Encoding to {full_video_name} using {selected['fourcc']}...")
        for _, out_path in self.image_map:
            if os.path.exists(out_path):
                frame = cv2.imread(out_path)
                if frame is not None:
                    video.write(frame)
        
        video.release()
        print("Video generation complete.")
        return full_video_name


if __name__ == "__main__":
    timelapse = FaceTimelapse(
        input_dir="testing",
        output_dir="results",
        force=True,
        auto_tune=True
    )

    timelapse.scan_images()
    timelapse.run_alignment()
    timelapse.generate_video(video_name="Timelapse_Test", profile="MP4 (Universal)", fps=24)
