"""
Smooth the staircase-shaped V_...[N] force columns in CSV files like
AoFoam1.csv. Works on a single file OR on every matching CSV in a folder.

Why a plain moving-average/rolling-mean is NOT used:
The force sensors sample at a much lower rate than the rest of the data,
so each real reading is "held" constant for ~12 rows before jumping to the
next value (a staircase / zero-order-hold pattern). A rolling average would
just blur the corners of the staircase without removing the fundamental
step behavior, and it also introduces a lag relative to the true signal.

Approach used instead:
1. For each force column, detect contiguous blocks of (near-)identical
   values -> these correspond to the real underlying low-rate samples.
2. Take the time at the CENTER of each block together with that block's
   value -> this is our set of true (t, force) sample points.
3. Fit a smooth interpolator (cubic spline by default, PCHIP as a safer
   monotonic-preserving alternative) through those center points and
   evaluate it at every original timestamp -> smooth, continuous signal.
4. Recompute SumForce as the sum of the smoothed individual channels.

Usage:
    # Single file (same as before)
    python3 smooth_forces.py input.csv output.csv [pchip|cubic]

    # Whole folder: reads every *.csv in in_dir, writes smoothed copies
    # (same filenames) into out_dir, which is created if needed.
    python3 smooth_forces.py --folder in_dir out_dir [pchip|cubic] [pattern]

    # Examples:
    python3 smooth_forces.py --folder ./raw_csvs ./smoothed_csvs
    python3 smooth_forces.py --folder ./raw_csvs ./smoothed_csvs pchip "*.csv"
"""

import sys
import glob
import os
import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline, PchipInterpolator

FORCE_COLS = [
    "V_SidePalm[N]",
    "V_ThumbPalm[N]",
    "V_UpperPalm[N]",
    "V_Middle[N]",
    "V_Index[N]",
    "V_Thumb[N]",
]

TIME_COL = "time"
SUM_COL = "SumForce"


def detect_blocks(values, tol=1e-9):
    """Return list of (start_idx, end_idx_inclusive) for runs of near-equal values."""
    blocks = []
    start = 0
    n = len(values)
    for i in range(1, n + 1):
        if i == n or abs(values[i] - values[start]) > tol:
            blocks.append((start, i - 1))
            start = i
    return blocks


def smooth_column(t, v, method="pchip"):
    blocks = detect_blocks(v)

    # Sample point = center time & value of each held block
    centers_t = []
    centers_v = []
    for (s, e) in blocks:
        centers_t.append((t[s] + t[e]) / 2.0)
        centers_v.append(v[s])  # value is constant across the block

    centers_t = np.array(centers_t)
    centers_v = np.array(centers_v)

    if len(centers_t) < 3:
        # Not enough points to spline meaningfully; fall back to linear interp
        return np.interp(t, centers_t, centers_v)

    if method == "pchip":
        interp = PchipInterpolator(centers_t, centers_v, extrapolate=True)
    else:
        interp = CubicSpline(centers_t, centers_v, extrapolate=True)

    return interp(t)


def smooth_file(in_path, out_path, method="pchip"):
    """Smooth one CSV file and write the result to out_path."""
    df = pd.read_csv(in_path)

    if TIME_COL not in df.columns:
        print(f"  Skipping {in_path}: no '{TIME_COL}' column found.")
        return False

    t = df[TIME_COL].to_numpy()

    any_smoothed = False
    for col in FORCE_COLS:
        if col not in df.columns:
            continue
        v = df[col].to_numpy(dtype=float)
        smoothed = smooth_column(t, v, method=method)
        # Forces shouldn't go negative from spline overshoot; clip at 0
        smoothed = np.clip(smoothed, 0, None)
        df[col] = smoothed
        any_smoothed = True

    if not any_smoothed:
        print(f"  Skipping {in_path}: none of the expected V_...[N] columns found.")
        return False

    if SUM_COL in df.columns:
        present = [c for c in FORCE_COLS if c in df.columns]
        df[SUM_COL] = df[present].sum(axis=1)

    df.to_csv(out_path, index=False)
    return True


def process_folder(in_dir, out_dir, method="pchip", pattern="*.csv"):
    """Smooth every CSV matching `pattern` in in_dir, writing results
    (same filenames) into out_dir."""
    os.makedirs(out_dir, exist_ok=True)

    files = sorted(glob.glob(os.path.join(in_dir, pattern)))
    if not files:
        print(f"No files matching '{pattern}' found in {in_dir}")
        return

    ok, skipped = 0, 0
    for f in files:
        fname = os.path.basename(f)
        out_path = os.path.join(out_dir, fname)
        print(f"Processing {fname} ...")
        try:
            success = smooth_file(f, out_path, method=method)
        except Exception as e:
            print(f"  Error processing {fname}: {e}")
            success = False
        if success:
            ok += 1
            print(f"  -> wrote {out_path}")
        else:
            skipped += 1

    print(f"\nDone. Smoothed {ok} file(s), skipped {skipped}.")


def main(in_path, out_path, method="pchip"):
    smooth_file(in_path, out_path, method=method)
    print(f"Wrote smoothed CSV to: {out_path}")


if __name__ == "__main__":
    args = sys.argv[1:]

    if args and args[0] == "--folder":
        # python3 smooth_forces.py --folder in_dir out_dir [method] [pattern]
        if len(args) < 3:
            print("Usage: python3 smooth_forces.py --folder in_dir out_dir [pchip|cubic] [pattern]")
            sys.exit(1)
        in_dir = args[1]
        out_dir = args[2]
        method = args[3] if len(args) > 3 else "pchip"
        pattern = args[4] if len(args) > 4 else "*.csv"
        process_folder(in_dir, out_dir, method=method, pattern=pattern)
    else:
        # python3 smooth_forces.py input.csv output.csv [method]
        in_path = args[0] if len(args) > 0 else "AoFoam1.csv"
        out_path = args[1] if len(args) > 1 else "AoFoam1_smoothed.csv"
        method = args[2] if len(args) > 2 else "pchip"
        main(in_path, out_path, method)
