import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np

def plot_force_and_penpos_z(
    filepath,
    force_col="LPF_Fz",
    pos_col="Penpos_z[mm]",
    min_z=275,
    max_z=450
):

    df = pd.read_csv(filepath)

    force = df[force_col].copy()
    z_pos = df[pos_col].copy()

    if 'pos' in pos_col.lower():
        mask = (z_pos >= min_z) & (z_pos <= max_z)

        force[~mask] = np.nan
        z_pos[~mask] = np.nan

    fig, ax1 = plt.subplots(figsize=(12, 6))

    ax1.plot(force, label=force_col)

    ax2 = ax1.twinx()
    ax2.plot(z_pos, color = 'red', label=pos_col)

    ax1.set_xlabel("Sample")
    ax1.set_ylabel(force_col)
    ax2.set_ylabel(pos_col)

    plt.title(f"{filepath.stem}: {force_col} vs {pos_col}")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot_three_signals(
    filepath,
    force_col="LPF_Fz",
    pos1_col="Penpos_z[mm]",
    pos2_col="velo_z[mm/s]",
    min_z=None,
    max_z=None
):

    df = pd.read_csv(filepath)

    force = df[force_col].copy()
    pos1 = df[pos1_col].copy()
    pos2 = df[pos2_col].copy()

    if min_z is not None:
        mask = pos1 >= min_z
        force[~mask] = np.nan
        pos1[~mask] = np.nan
        pos2[~mask] = np.nan

    if max_z is not None:
        mask = pos1 <= max_z
        force[~mask] = np.nan
        pos1[~mask] = np.nan
        pos2[~mask] = np.nan

    fig, ax1 = plt.subplots(figsize=(12, 6))

    # Force
    line1 = ax1.plot(
        force,
        linewidth=2,
        label=force_col
    )

    ax1.set_xlabel("Sample")
    ax1.set_ylabel("Force (N)")

    # Position axis
    ax2 = ax1.twinx()

    line2 = ax2.plot(
        pos1,
        '--',
        linewidth=2,
        label=pos1_col
    )

    line3 = ax2.plot(
        pos2,
        ':',
        linewidth=2,
        label=pos2_col
    )

    ax2.set_ylabel("Position (mm)")

    lines = line1 + line2 + line3
    labels = [l.get_label() for l in lines]

    ax1.legend(lines, labels, loc="best")

    plt.title(filepath.stem)
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plotFolder(folder, output ="Data/ForceBelowMat/Fz-PosZCompareResult"):
    if not folder.exists():
        print(f"Folder not found: {folder.resolve()}")
        return

    means = {}

    for filepath in sorted(folder.glob("*.csv")):

        print(f"Processing {filepath.name}")

        try:
            plot_aligned_force_and_pos(
                filepath,
                output,
                pos_col="LPF_Fy"
            )
        except Exception as e:
            print(f"Error processing {filepath.name}: {e}")

def plot_aligned_force_and_pos(filepath, output_folder,
    force_col="LPF_Fz",
    pos_col="Penpos_z[mm]",
    pre_samples=50,
    post_samples=150,
    on_threshold=10,
    off_threshold=5,
    min_gap=200
):

    df = pd.read_csv(filepath)

    force = df[force_col].to_numpy()
    pos = df[pos_col].to_numpy()

    # Detect rising edges
    edges = []
    armed = True
    last_edge = -np.inf

    for i, value in enumerate(force):

        if armed:
            if value >= on_threshold and (i - last_edge) > min_gap:
                edges.append(i)
                last_edge = i
                armed = False

        else:
            if value <= off_threshold:
                armed = True

    t = np.arange(-pre_samples, post_samples)

    fig, ax1 = plt.subplots(figsize=(12, 6))

    ax2 = ax1.twinx()

    for edge in edges:

        start = edge - pre_samples
        end = edge + post_samples

        if start < 0 or end > len(force):
            continue

        force_seg = force[start:end]
        pos_seg = pos[start:end]

        ax1.plot(
            t,
            force_seg,
            alpha=1
        )

        ax2.plot(
            t,
            pos_seg,
            '-',
            alpha=0.25
        )

    ax1.axvline(
        0,
        linestyle='--'
    )

    ax1.set_xlabel("Samples Relative to Rising Edge")
    ax1.set_ylabel(force_col)
    ax2.set_ylabel(pos_col)

    plt.title(filepath.stem)
    plt.grid(True)
    plt.legend(
        [ax1.lines[0], ax2.lines[0]], [force_col, pos_col]
    )

    save_path = f"{output_folder}/{Path(filepath).stem}.png"

    plt.savefig(
        save_path,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()

    print(f"Saved: {save_path}")

def plot_each_aligned_event(
    filepath,
    force_col="LPF_Fz",
    pos_col="Penpos_z[mm]",
    pre_samples=50,
    post_samples=150,
    on_threshold=10,
    off_threshold=5,
    min_gap=200
):

    df = pd.read_csv(filepath)

    force = df[force_col].to_numpy()
    pos = df[pos_col].to_numpy()

    # Detect rising edges
    edges = []
    armed = True
    last_edge = -np.inf

    for i, value in enumerate(force):

        if armed:
            if value >= on_threshold and (i - last_edge) > min_gap:
                edges.append(i)
                last_edge = i
                armed = False

        else:
            if value <= off_threshold:
                armed = True

    t = np.arange(-pre_samples, post_samples)

    for event_num, edge in enumerate(edges, start=1):

        start = edge - pre_samples
        end = edge + post_samples

        if start < 0 or end > len(force):
            continue

        force_seg = force[start:end]
        pos_seg = pos[start:end]

        fig, ax1 = plt.subplots(figsize=(10, 5))

        ax1.plot(
            t,
            force_seg,
            linewidth=2,
            label="LPF_Fz"
        )

        ax1.set_xlabel("Samples Relative to Rising Edge")
        ax1.set_ylabel("Force (N)")

        ax2 = ax1.twinx()

        ax2.plot(
            t,
            pos_seg,
            '--',
            linewidth=2,
            label="Penpos_z[mm]"
        )

        ax2.set_ylabel("Position (mm)")

        ax1.axvline(
            0,
            linestyle='--',
            linewidth=1
        )

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()

        ax1.legend(
            lines1 + lines2,
            labels1 + labels2,
            loc="best"
        )

        plt.title(
            f"{filepath.stem} - Event {event_num}"
        )

        plt.grid(True)
        plt.tight_layout()
        plt.show()


filepath = Path("Data/ForceBelowMat/CasesTakes/1106TestSidePalmHard2.csv")
# plot_force_and_penpos_z(filepath)
# plot_three_signals(filepath, min_z=275, max_z=450)
# plot_force_pos_vel(filepath, min_z=275, max_z=450)
folder = Path("Data/ForceBelowMat/CasesTakes")
plotFolder(folder, "Data/ForceBelowMat/Fz-FyCompareResult")
# plot_aligned_force_and_pos(filepath, output_folder="Data/ForceBelowMat/Fz-FyCompareResult", pos_col="LPF_Fy")
# plot_each_aligned_event(filepath)