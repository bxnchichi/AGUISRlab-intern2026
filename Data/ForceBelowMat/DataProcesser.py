import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt


def detect_rising_edges(csv_file, column="LPF_Fz", on_threshold=10.0, off_threshold=5.0, min_gap=100):
    """
    Detect contact onset using hysteresis.

    Parameters
    ----------
    on_threshold : float
        Signal must exceed this value to trigger.
    off_threshold : float
        Signal must fall below this value before
        another trigger is allowed.
    min_gap : int
        Minimum samples between events.

    Returns
    -------
    signal : ndarray
    edge_indices : ndarray
    """

    signal = pd.read_csv(csv_file)[column].to_numpy()

    edges = []
    armed = True
    last_edge = -np.inf

    for i, value in enumerate(signal):

        if armed:
            if value >= on_threshold and (i - last_edge) > min_gap:
                edges.append(i)
                last_edge = i
                armed = False

        else:
            if value <= off_threshold:
                armed = True

    return signal, np.array(edges)



def align_events(
    signal,
    edge_indices,
    pre_samples=100,
    post_samples=300,
    peak_fraction=0.9,
    plateau_samples=20,
    max_plateau_std=2.75
):
    """
    Keep only events that reach a stable plateau and
    reject events with high plateau fluctuations.
    """

    aligned = []

    for edge in edge_indices:

        start = edge - pre_samples
        end = edge + post_samples

        if start < 0 or end > len(signal):
            continue

        segment = signal[start:end]

        post_region = signal[edge:end]

        if len(post_region) < plateau_samples:
            continue

        peak = np.max(post_region)
        plateau_threshold = peak * peak_fraction

        plateau_start = None

        for i in range(len(post_region) - plateau_samples):

            window = post_region[i:i + plateau_samples]

            if np.all(window >= plateau_threshold):
                plateau_start = i
                break

        if plateau_start is None:
            continue

        # Analyze plateau stability
        plateau_region = post_region[plateau_start:]

        if len(plateau_region) < plateau_samples:
            continue

        plateau_std = np.std(plateau_region)

        if plateau_std > max_plateau_std:
            continue

        aligned.append(segment)

    aligned = np.array(aligned)

    time_axis = np.arange(-pre_samples, post_samples)

    return aligned, time_axis

def findMeans(aligned):
    mean_profile = np.mean(aligned, axis=0)
    return mean_profile

def plot_aligned(aligned, time_axis, mean_profile, name):
    plt.figure(figsize=(10, 6))

    # Individual trials
    for segment in aligned:
        plt.plot(time_axis, segment, alpha=0.3)

    # Plot mean as dashed line
    plt.plot(
        time_axis,
        mean_profile,
        'k--',          # black dashed line
        linewidth=1.5,
        label='Mean'
    )

    # # Alignment point
    # plt.axvline(
    #     0,
    #     color='r',
    #     linestyle='--',
    #     linewidth=2,
    #     label='Rising Edge'
    # )

    plt.xlabel("Samples Relative to Edge")
    plt.ylabel("LPF_Fz")
    plt.title(name)
    plt.legend()
    plt.grid(True)
    plt.show()

import numpy as np

import numpy as np

def find_rise_time_and_plateau(
    signal,
    edge_indices,
    post_samples=300,
    peak_fraction=0.9,
    plateau_samples=20,
    fs=100
):

    rise_times = []
    plateau_means = []

    for edge in edge_indices:

        end = min(edge + post_samples, len(signal))

        post_region = signal[edge:end]

        if len(post_region) < plateau_samples:
            continue

        peak = np.max(post_region)
        plateau_threshold = peak * peak_fraction

        plateau_start = None

        for i in range(len(post_region) - plateau_samples):

            window = post_region[i:i + plateau_samples]

            if np.all(window >= plateau_threshold):
                plateau_start = i
                break

        if plateau_start is None:
            continue

        plateau_region = post_region[plateau_start:]

        plateau_mean = np.mean(plateau_region)

        rise_time = plateau_start / fs

        rise_times.append(rise_time)
        plateau_means.append(plateau_mean)

    return np.array(rise_times), np.array(plateau_means)


def plotFile(filepath):
    signal, edges = detect_rising_edges(filepath, min_gap=200)

    print("Detected edges:", edges)

    rise_times, plateau_means = find_rise_time_and_plateau(
        signal,
        edges,
        fs=100
    )

    print("Rise times (s):")
    print(rise_times)

    print("Plateau means (N):")
    print(plateau_means)

    print(f"Average rise time: {np.mean(rise_times):.3f} s")
    print(f"Average plateau force: {np.mean(plateau_means):.2f} N")

    aligned, t = align_events(
        signal,
        edges,
        pre_samples=50,
        post_samples=150
    )
    mean =findMeans(aligned)
    # plot_aligned(aligned, t, mean, filepath.stem)
    return mean

def plotFolder(folder):
    if not folder.exists():
        print(f"Folder not found: {folder.resolve()}")
        return

    means = {}

    for filepath in sorted(folder.glob("*.csv")):

        print(f"Processing {filepath.name}")

        try:
            mean = plotFile(filepath)

            if mean is not None and len(mean) > 0:
                means[filepath.stem] = mean

        except Exception as e:
            print(f"Failed: {filepath.name}")
            print(e)
    return means

def plotMeanByTestPiece(means):

    names = list(means.keys())

    odd_pair_indices = []
    even_pair_indices = []

    for pair in range(len(names) // 2):

        start = pair * 2

        if pair % 2 == 0:
            odd_pair_indices.extend([start, start + 1])
        else:
            even_pair_indices.extend([start, start + 1])

    # ---------- Odd pairs ----------
    plt.figure(figsize=(12, 6))

    odd_colors = [
        plt.cm.Reds(0.5),
        plt.cm.Reds(0.8),

        plt.cm.Oranges(0.5),
        plt.cm.Oranges(0.8),

        plt.cm.Greys(0.5),
        plt.cm.Greys(0.8),
    ]

    for color_idx, idx in enumerate(odd_pair_indices):

        if idx >= len(names):
            continue

        name = names[idx]
        mean_curve = means[name]

        plt.plot(
            np.arange(len(mean_curve)),
            mean_curve,
            color=odd_colors[color_idx],
            linewidth=2,
            label=name
        )

    plt.title("Tests on Hard Pieces")
    plt.xlabel("Aligned Sample")
    plt.ylabel("LPF_Fz")
    plt.xlim(0, 175)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    # ---------- Even pairs ----------
    plt.figure(figsize=(12, 6))

    even_colors = [
        plt.cm.Blues(0.5),
        plt.cm.Blues(0.8),

        plt.cm.Greens(0.5),
        plt.cm.Greens(0.8),

        plt.cm.Purples(0.5),
        plt.cm.Purples(0.8),
    ]

    for color_idx, idx in enumerate(even_pair_indices):

        if idx >= len(names):
            continue

        name = names[idx]
        mean_curve = means[name]

        plt.plot(
            np.arange(len(mean_curve)),
            mean_curve,
            color=even_colors[color_idx],
            linewidth=2,
            label=name
        )

    plt.title("Tests on Soft Pieces")
    plt.xlabel("Aligned Sample")
    plt.ylabel("LPF_Fz")
    plt.xlim(0, 175)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    plt.show()


def plotMeanByContactSurface(means):

    names = list(means.keys())

    files_per_graph = 4

    for graph_idx in range(0, len(names), files_per_graph):

        plt.figure(figsize=(10, 6))

        graph_names = names[graph_idx:graph_idx + files_per_graph]

        # Second pair: blue shades
        pair2_colors = plt.cm.Blues([0.5, 0.8])

        # First pair: red shades
        pair1_colors = plt.cm.Reds([0.5, 0.8])

        colors = [
            pair1_colors[0],
            pair1_colors[1],
            pair2_colors[0],
            pair2_colors[1]
        ]

        for i, name in enumerate(graph_names):

            mean_curve = means[name]
            t = np.arange(len(mean_curve))

            plt.plot(
                t,
                mean_curve,
                color=colors[i],
                linewidth=2,
                label=name
            )

        plt.xlabel("Aligned Sample")
        plt.ylabel("LPF_Fz")
        plt.title(
            f"Mean Force Profiles (Files {graph_idx+1}-{graph_idx+len(graph_names)})"
        )
        plt.grid(True)
        plt.legend()
        plt.xlim(0, 175)
        plt.tight_layout()

    plt.show()


def main():

    folder = Path("Data/ForceBelowMat/ForceBelowEX")
    means = plotFolder(folder) #plot all files and get means
    plotMeanByContactSurface(means)
    plotMeanByTestPiece(means)
    


if __name__ == "__main__":
    main()