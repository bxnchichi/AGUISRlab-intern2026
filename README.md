# AGUISRlab Intern 2026
The repo holds the code, sensor data, calibration files, and progress reports produced during the internship at AGUISRlab.

## Overview

The project pipeline roughly follows these stages:

1. **Motion capture** – Recording therapist hand motion with OptiTrack (via `NatNetClient`) and Manus haptic gloves (`.mcal` calibration files), to capture the trajectories and hand poses used in a massage.
2. **Force sensing** – Custom FSR (Force-Sensitive Resistor) hardware read over serial (Arduino `.ino` firmware) to capture contact force, with cross-talk correction, variance analysis, and Kalman-filter based smoothing.
3. **Data synchronization** – Aligning motion-capture and force-sensor streams (`synchronized_data.csv`, `synchronized_hand_data.csv`) into a single time-aligned dataset.
4. **Data processing & visualization** – Python utilities to clean, smooth, and plot the collected force/motion data (line plots, scatter plots, heatmaps).
5. **Robot execution** – A ROS-based C++ controller (`ben_massage.cpp`) for driving a JAKA robot arm, built on the recorded motion/force data.

## Repository structure

```
.
├── Data/                     # Data processing pipeline & collected datasets
│   ├── DataProcessor.py      # Batch-processes collected CSVs (adds SumForce, etc.)
│   ├── DataProcessor.ipynb   # Notebook version / exploratory analysis
│   ├── smooth_forces.py      # De-staircases raw FSR readings via spline interpolation
│   ├── package/               # Shared plotting/analysis utilities
│   │   ├── linePlotUtils.py
│   │   ├── scatterPlotUtils.py
│   │   └── HeatmapUtil.py
│   ├── FSRCalibration/        # FSR calibration datasets
│   ├── FinalDataCollection/   # Final collected trial data
│   ├── ForceBelowMat/         # Trials measuring force transmitted through a mat
│   ├── ThaiMassage/           # Thai-massage-specific recordings
│   └── otherCase/             # Miscellaneous / auxiliary recordings
│
├── ForceSensor/               # FSR sensor R&D
│   ├── 3D model/               # Sensor housing / mount CAD
│   ├── research paper/         # Reference papers
│   ├── CrossTalkSolved6FSR.csv
│   ├── Variance calculation.csv
│   └── kalmanDraft.jpg         # Kalman-filter design sketch
│
├── code/                      # Source code
│   ├── FSR/                    # Arduino firmware + Python serial tools for the FSR array
│   │   ├── FSR.ino
│   │   ├── FSRCalibation.py / FSRCalibation_working.py
│   │   ├── TryPyserial.py
│   │   └── terminalProcess.py
│   ├── mocapCode/               # OptiTrack motion-capture client & processing
│   │   ├── NatNetClient.py / MoCapData.py
│   │   ├── CheckGloveID.py
│   │   ├── SkeletonExtractor.py
│   │   └── FinalFinalMocapCode.py / _finalFinalFinalmoCap.py
│   ├── massagaeSep/              # Massage-motion segmentation experiments
│   ├── CFS_Sample_VC2008/        # Sample project (Visual C++)
│   └── ben_massage.cpp           # ROS/C++ controller for the JAKA robot arm
│
├── manusRecord/                # Manus glove calibration profiles (.mcal) & screenshots
├── presentation/                # Weekly progress reports & final report (PDF, Canva links)
│   └── _presentationLink.txt     # Links to all Canva progress-report decks
│
├── fsr_data.csv                 # Sample raw FSR data
├── hand_motion.csv               # Sample hand-motion data
├── synchronized_data.csv         # Force + motion data aligned in time
├── synchronized_hand_data.csv    # Full-resolution synchronized hand data
├── profile.csv                   # Session/profile metadata
└── DraftAndPlan.jpg / DraftAndPlan2.jpg   # Early project planning sketches
```

## Tech stack

- **Python** – data processing, plotting, calibration, serial communication (`pandas`, `numpy`, `scipy`)
- **Arduino (C/C++)** – FSR sensor firmware (`FSR.ino`)
- **Jupyter Notebook** – exploratory data analysis
- **OptiTrack NatNet SDK** – motion capture streaming
- **Manus gloves** – hand-pose/haptic capture (`.mcal` calibration profiles)

## Getting started

> This is a research/lab repo rather than a packaged library — most scripts are meant to be run individually against local sensor hardware or recorded datasets.

1. Clone the repo:
   ```bash
   git clone https://github.com/bxnchichi/AGUISRlab-intern2026.git
   cd AGUISRlab-intern2026
   ```
2. Install Python dependencies (not pinned in a requirements file yet — at minimum you'll need):
   ```bash
   pip install pandas numpy scipy matplotlib pyserial
   ```
3. **Force sensor pipeline**: flash `code/FSR/FSR.ino` to the microcontroller, then use `code/FSR/FSRCalibation.py` / `terminalProcess.py` to read/calibrate over serial.
4. **Motion capture**: run the scripts in `code/mocapCode/` against a live OptiTrack/NatNet stream, using the calibration files in `manusRecord/` for the Manus gloves.
5. **Data processing**: after collecting raw CSVs, run `Data/smooth_forces.py` to smooth staircase-shaped force readings, then `Data/DataProcessor.py` to compute derived columns and generate plots.

## Progress reports

Weekly progress reports (English and Japanese) and the final report are in [`presentation/`](./presentation), including PDFs and links to the corresponding Canva decks in [`_presentationLink.txt`](./presentation/_presentationLink.txt).
