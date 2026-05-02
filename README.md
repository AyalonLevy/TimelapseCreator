# Timelapse Creator

A tool for creating stabilized face timelapses. This tool automates the tedious work of alignment and exposure normalization.

## Features
*   **Intelligent Face Stabilization:** Uses 68-point facial landmarks to perfectly level eyes and center faces.
*   **Parallel Processing:** Multithreaded engine utilizes all available CPU cores for maximum speed.
*   **Auto-Rename:** Standardizes input files to `YYYYMMDD.jpg` based on file metadata.
*   **Exposure Normalization:** Built-in CLAHE auto-tuning to reduce flicker.
*   **Error Reporting:** Generates a detailed report of any images where a face couldn't be detected.
*   **Customizable Export:** Support for various resolutions (1080p, 4K, Portrait) and video formats.

## Known Limitations & Edge Cases
While the tool is designed to be robust, the underlying facial landmark detection (dlib) has specific requirements for high-accuracy alignment:

*   **Low-Light Environments:** Images with significant underexposure or high "noise" in the facial region may fail detection. The "Auto-Tune Exposure" feature can mitigate this, but extremely dark frames will be skipped and logged in the error report.
*   **Extreme Head Tilt:** The detector is optimized for upright or slightly tilted faces (up to ~45°). Faces rotated at or near 90° (landscape-style portraits) will likely not be recognized.
*   **Obstructions:** Heavy occlusions (large sunglasses, masks, or hands covering the eyes) may prevent the stabilization algorithm from calculating the correct eye-center coordinates.

## Installation & Requirements

### For Python Users
1. Clone the repository.
2. Install dependencies: `pip install -r requirements.txt`
3. **Important:** Download the landmark model:
   - Download `shape_predictor_68_face_landmarks.dat` from the [dlib-models repository](https://github.com/davisking/dlib-models).
   - Place it in the root directory of this project.

### For Windows Users (.exe)
1. Download the latest `TimelapseCreator.exe` from the **Releases** section.
2. Ensure `shape_predictor_68_face_landmarks.dat` is in the same folder as the `.exe`.

## Credits
*   Face detection and landmark prediction powered by **[dlib](http://dlib.net/)**.
*   Image processing via **OpenCV**.
*   UI components by **CustomTkinter**.

## License
Distributed under the MIT License. See `LICENSE` for more information.