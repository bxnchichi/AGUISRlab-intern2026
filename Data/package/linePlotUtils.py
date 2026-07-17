import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt, savgol_filter
import time

sampling_rate = 100 

#NAI
#------------------------------------------------------------------------------------------------------------
#    █████████   ████   ███                                                  
#   ███░░░░░███ ░░███  ░░░                                               
#  ░███    ░███  ░███  ████   ███████ ████████                             
#  ░███████████  ░███ ░░███  ███░░███░░███░░███                             
#  ░███░░░░░███  ░███  ░███ ░███ ░███ ░███ ░███                            
#  ░███    ░███  ░███  ░███ ░███ ░███ ░███ ░███                            
#  █████   █████ █████ █████░░███████ ████ █████                         
# ░░░░░   ░░░░░ ░░░░░ ░░░░░  ░░░░░███░░░░ ░░░░░                           
#                            ███ ░███                                                 
#                           ░░██████                                                  
#                            ░░░░░░                                                   
#-----------------------------------------------------------------------------------------------------------------------------

def detect_rising_edges(df, processed_column, column="LPF_Fcz", on_threshold=15.0, off_threshold=15.0, min_gap=100):
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

    Base_signal = df[column].to_numpy()
    Processed_signal = df[processed_column].to_numpy()
    

    rising_edges = []
    edge_length = []
    armed = True
    last_edge = -np.inf

    for i, value in enumerate(Base_signal):

        if armed:
            if value >= on_threshold and (i - last_edge) > min_gap:
                if i != 0:
                    rising_edges.append(i)
                last_edge = i
                armed = False

        else:
            if value <= off_threshold:
                if i != 0 and len(rising_edges) > 0:
                    if i - rising_edges[-1] < min_gap:
                        rising_edges.pop()  # Remove the last edge if it's too close
                    else:
                        edge_length.append(i - rising_edges[-1]) 
                armed = True

    return Processed_signal, Base_signal, np.array(rising_edges), np.array(edge_length)

def detect_touching_point(df, column, on_threshold=2, off_threshold=5, min_gap=100):

    Base_signal = df[column].to_numpy()
    

    touching_points = []
    edge_length = []
    armed = True
    last_edge = -np.inf

    for i, value in enumerate(Base_signal):

        if armed:
            if value <= on_threshold and (i - last_edge) > min_gap:
                if i != 0:
                    touching_points.append(i)
                last_edge = i
                armed = False
        else:
            if value >= off_threshold:
                if i != 0 and len(touching_points) > 0:
                    if i - touching_points[-1] < min_gap:
                        touching_points.pop()  # Remove the last touching point if it's too close
                    else:
                        edge_length.append(i - touching_points[-1]) 
                armed = True

    return np.array(touching_points), np.array(edge_length)

def signal_has_plateau(
    signal,
    edge_indices,
    post_samples=300,
    peak_fraction=0.9,
    plateau_samples=20,
    max_plateau_std=20,
    min_plateau_ratio=0.5
):
    """
    Determine whether the overall trial contains plateaus.

    Returns
    -------
    bool
        True if enough events contain plateaus.
    """

    plateau_count = 0

    for edge in edge_indices:

        end = min(edge + post_samples, len(signal))
        post_region = signal[edge:end]

        if len(post_region) < plateau_samples:
            continue

        peak = np.max(post_region)
        threshold = peak * peak_fraction

        found_plateau = False

        for i in range(len(post_region) - plateau_samples):

            window = post_region[i:i+plateau_samples]

            if np.all(window >= threshold):

                plateau_region = post_region[i:]

                if np.std(plateau_region) <= max_plateau_std:
                    found_plateau = True
                    break

        if found_plateau:
            plateau_count += 1

    ratio = plateau_count / max(len(edge_indices), 1)

    return ratio >= min_plateau_ratio

def align_events(
    signal,
    edge_indices,
    pre_samples=50,
    post_samples=300,
    peak_fraction=0.9,
    plateau_samples=20,
    max_plateau_std=35
):

    aligned = []

    has_plateau = signal_has_plateau(
        signal,
        edge_indices,
        post_samples=post_samples,
        peak_fraction=peak_fraction,
        plateau_samples=plateau_samples,
        max_plateau_std=max_plateau_std
    )

    # -------------------------
    # Plateau Trial
    # -------------------------
    if has_plateau:

        print("Plateau trial detected")

        for edge in edge_indices:
            

            end = min(edge + post_samples, len(signal))
            post_region = signal[edge:end]

            peak = np.max(post_region)
            threshold = peak * peak_fraction

            plateau_start = None

            for i in range(len(post_region) - plateau_samples):

                window = post_region[i:i+plateau_samples]

                if np.all(window >= threshold):

                    plateau_region = post_region[i:]

                    if np.std(plateau_region) <= max_plateau_std:
                        plateau_start = i
                        break

            if plateau_start is None:
                continue

            align_idx = edge

            start = align_idx - pre_samples
            end = align_idx + post_samples

            if start < 0 or end > len(signal):
                continue

            aligned.append(signal[start:end])

        time_axis = np.arange(-pre_samples, post_samples)

    # -------------------------
    # Non-Plateau Trial
    # -------------------------
    else:

        print("Non-plateau trial detected")

        for edge in edge_indices:

            start = edge
            end = edge + post_samples

            if end > len(signal):
                continue

            aligned.append(signal[start:end])

        time_axis = np.arange(post_samples)

    return np.array(aligned), time_axis

def align_plateau_events(
    signal,
    edge_indices,
    pre_samples=100,
    post_samples=300,
    peak_fraction=0.9,
    plateau_samples=20,
    max_plateau_std=20,
    nonplateau_method="slope"  # "slope" or "peak"
):
    """
    Detect whether each event contains a stable plateau.

    Plateau event:
        align at plateau onset

    Non-plateau event:
        align at max slope or peak

    Returns
    -------
    aligned : ndarray
    time_axis : ndarray
    labels : list
        'plateau' or 'non_plateau'
    """

    aligned = []
    labels = []

    for edge in edge_indices:

        search_end = min(edge + post_samples, len(signal))
        post_region = signal[edge:search_end]

        if len(post_region) < plateau_samples:
            continue

        peak = np.max(post_region)
        plateau_threshold = peak * peak_fraction

        plateau_start = None

        # ---------- Plateau Detection ----------
        for i in range(len(post_region) - plateau_samples):

            window = post_region[i:i + plateau_samples]

            if np.all(window >= plateau_threshold):

                plateau_region = post_region[i:]

                if np.std(plateau_region) <= max_plateau_std:
                    plateau_start = i
                    break

        # ---------- Choose Alignment Point ----------

        if plateau_start is not None:

            align_idx = edge + plateau_start
            labels.append("plateau")

        else:

            labels.append("non_plateau")

            if nonplateau_method == "slope":

                slope = np.gradient(post_region)
                align_idx = edge + np.argmax(slope)

            elif nonplateau_method == "peak":

                align_idx = edge + np.argmax(post_region)

            else:
                raise ValueError(
                    "nonplateau_method must be 'slope' or 'peak'"
                )

        # ---------- Extract Segment ----------

        start = align_idx - pre_samples
        end = align_idx + post_samples

        if start < 0 or end > len(signal):
            continue

        aligned.append(signal[start:end])

    aligned = np.array(aligned)
    time_axis = np.arange(-pre_samples, post_samples)

    return aligned, time_axis, labels

#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#    █████████            ████                      ████             █████            
#   ███░░░░░███          ░░███                     ░░███            ░░███             
#  ███     ░░░   ██████   ░███   ██████  █████ ████ ░███   ██████   ███████    ██████ 
# ░███          ░░░░░███  ░███  ███░░███░░███ ░███  ░███  ░░░░░███ ░░░███░    ███░░███
# ░███           ███████  ░███ ░███ ░░░  ░███ ░███  ░███   ███████   ░███    ░███████ 
# ░░███     ███ ███░░███  ░███ ░███  ███ ░███ ░███  ░███  ███░░███   ░███ ███░███░░░  
#  ░░█████████ ░░████████ █████░░██████  ░░████████ █████░░████████  ░░█████ ░░██████ 
#   ░░░░░░░░░   ░░░░░░░░ ░░░░░  ░░░░░░    ░░░░░░░░ ░░░░░  ░░░░░░░░    ░░░░░   ░░░░░░  
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def findMeans(aligned):
    mean_profile = np.mean(aligned, axis=0)
    return mean_profile

def average_curves(curve1, curve2):

    min_len = min(len(curve1), len(curve2))

    return (curve1[:min_len] + curve2[:min_len]) / 2

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
    plateau_std = []

    for edge in edge_indices:

        end = min(edge + post_samples, len(signal))

        post_region = signal[edge:end]

        if len(post_region) < plateau_samples:
            continue

        peak = np.max(post_region)
        plateau_threshold = peak * peak_fraction
        # print(peak)
        plateau_start = None

        for i in range(len(post_region) - plateau_samples):

            window = post_region[i:i + plateau_samples]

            if np.all(window >= plateau_threshold):
                plateau_start = i
                break
        
        if plateau_start is None:
            continue

        plateau_end = None

        for i in range(len(post_region) - plateau_samples - plateau_start):

            window = post_region[plateau_start + i: i  + plateau_start + plateau_samples]

            if np.any(window <= plateau_threshold):
                plateau_end = i + plateau_start
                break

        
        
        plateau_region = post_region[plateau_start:plateau_end]


        plateau_mean = np.mean(plateau_region)

        rise_time = plateau_start / fs

        rise_times.append(rise_time)
        plateau_means.append(plateau_mean)
        plateau_std.append(np.std(plateau_region))

    return np.array(rise_times), np.array(plateau_means), np.array(plateau_std)

#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#  ███████████  ████            █████       ████      █████████   ███                                ████ 
# ░░███░░░░░███░░███           ░░███       ░░███     ███░░░░░███ ░░░                                ░░███ 
#  ░███    ░███ ░███   ██████  ███████      ░███    ░███    ░░░  ████   ███████ ████████    ██████   ░███ 
#  ░██████████  ░███  ███░░███░░░███░       ░███    ░░█████████ ░░███  ███░░███░░███░░███  ░░░░░███  ░███ 
#  ░███░░░░░░   ░███ ░███ ░███  ░███        ░███     ░░░░░░░░███ ░███ ░███ ░███ ░███ ░███   ███████  ░███ 
#  ░███         ░███ ░███ ░███  ░███ ███    ░███     ███    ░███ ░███ ░███ ░███ ░███ ░███  ███░░███  ░███ 
#  █████        █████░░██████   ░░█████     █████   ░░█████████  █████░░███████ ████ █████░░████████ █████
# ░░░░░        ░░░░░  ░░░░░░     ░░░░░     ░░░░░     ░░░░░░░░░  ░░░░░  ░░░░░███░░░░ ░░░░░  ░░░░░░░░ ░░░░░ 
#                                                                      ███ ░███                           
#                                                                     ░░██████                            
#                                                                      ░░░░░░                                                                                                                                                      
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

#both
def plot_aligned(aligned, time_axis, mean_profile, filepath, command, processed_column="LPF_Fz", output_folder = None):
    plt.figure(figsize=(10, 6))

    # Individual trials
    # i = 1
    for segment in aligned:
        # print(f"Trial no.{i} -> S.D. = {np.std(segment)}")
        plt.plot(time_axis, segment, alpha=0.5)
        # i += 1

    # Plot mean as dashed line
    plt.plot(
        time_axis,
        mean_profile,
        'k--',          # black dashed line
        linewidth=1.5,
        label='Mean'
    )

    # Alignment point
    plt.axvline(
        0,
        color='r',
        linestyle='--',
        linewidth=2,
        label='Rising Edge'
    )

    plt.xlabel("Samples Relative to Edge")
    plt.ylabel(processed_column)
    plt.title(filepath.stem)
    plt.legend()
    plt.grid(True)
    visualizePlot(command, output_folder=output_folder, filepath = filepath)

def plotAlignedFile(filepath, command, processed_column="LPF_Fz", output_folder=None):
    print(f"Processing {filepath}")
    Processed_signal, signal, edges = detect_rising_edges(filepath, processed_column, min_gap=200)

    # print("Detected edges:", edges)

    rise_times, plateau_means, plateau_std = find_rise_time_and_plateau(
        signal,
        edges,
        fs=100
    )

    print("Rise times (s):")
    print(rise_times)

    print("Plateau means (N):")
    print(plateau_means)

    print("Plateau standard deviation (N):")
    print(plateau_std)

    print(f"Average rise time: {np.mean(rise_times):.3f} s")
    print(f"Average plateau force: {np.mean(plateau_means):.2f} N")
    print(f"Average plateau S.D.: {np.mean(plateau_std):.2f} N")



    aligned, t = align_events(
        Processed_signal,
        edges,
        pre_samples=50,
        post_samples=300
    )
    mean = findMeans(aligned)
    # plot_aligned(aligned, t, mean, filepath, command, processed_column=processed_column, output_folder = output_folder)
    return mean

def plotAlignedFolder(folder, command,  processed_column, output_folder = None):
    if not folder.exists():
        print(f"Folder not found: {folder.resolve()}")
        return

    means = {}

    for filepath in sorted(folder.glob("*.csv")):

        print(f"Processing {filepath.name}")

        try:
            mean = plotAlignedFile(filepath, command, processed_column=processed_column, output_folder=output_folder)

            if mean is not None and len(mean) > 0:
                means[filepath.stem] = mean

        except Exception as e:
            print(f"Failed: {filepath.name}")
            print(e)
    return means

def plotMeanByTestPiece(means, command, processed_column="LPF_Fz", output_folder = None):

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
    plt.ylabel(processed_column)
    plt.xlim(0, 175)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    visualizePlot(command, output_folder=output_folder, name = 'AllCSVMatHard')

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
    plt.ylabel(processed_column)
    plt.xlim(0, 175)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    visualizePlot(command, output_folder=output_folder, name = "AllCSVMatSoft")

def plotMeanByContactSurface(means, command, processed_column="LPF_Fz", output_folder = None):

    names = list(means.keys())

    files_per_graph = 4

    nameList = ['AllCSVSidePalm', 'AllCSVThump', 'AllCSVUpperPalm']
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
        plt.ylabel(processed_column)
        plt.title(
            f"Mean Force Profiles (Files {graph_idx+1}-{graph_idx+len(graph_names)})"
        )
        plt.grid(True)
        plt.legend()
        plt.xlim(0, 175)
        plt.tight_layout()
        visualizePlot(command, output_folder=output_folder, name = nameList[graph_idx//4])

def plotMeanByTestPieceCases(means, command, processed_column="LPF_Fz", output_folder = None):

    names = list(means.keys())

    odd_pairs = []
    even_pairs = []

    for pair in range(len(names) // 2):

        idx1 = pair * 2
        idx2 = idx1 + 1

        if idx2 >= len(names):
            continue

        pair_mean = average_curves(
            means[names[idx1]],
            means[names[idx2]]
        )

        pair_name = f"{names[idx1]} + {names[idx2]}"

        if pair % 2 == 0:
            odd_pairs.append((pair_name, pair_mean))
        else:
            even_pairs.append((pair_name, pair_mean))

    # ---------- Odd ----------
    plt.figure(figsize=(12, 6))

    colors = [
        plt.cm.Reds(0.7),
        plt.cm.Oranges(0.7),
        plt.cm.Greys(0.7),
    ]

    

    for i, (name, curve) in enumerate(odd_pairs):

        plt.plot(
            np.arange(len(curve)),
            curve,
            color=colors[i],
            linewidth=2,
            label=name
        )

    plt.title("Tests on Hard Pieces")
    plt.xlabel("Aligned Sample")
    plt.ylabel(processed_column)
    plt.grid(True)
    plt.xlim(0, 175)
    plt.legend()
    plt.tight_layout()
    visualizePlot(command, output_folder=output_folder, name = "MeanCaseMatHard")

    # ---------- Even ----------
    plt.figure(figsize=(12, 6))

    colors = [
        plt.cm.Blues(0.7),
        plt.cm.Greens(0.7),
        plt.cm.Purples(0.7),
    ]

    for i, (name, curve) in enumerate(even_pairs):

        plt.plot(
            np.arange(len(curve)),
            curve,
            color=colors[i],
            linewidth=2,
            label=name
        )

    plt.title("Tests on Soft Pieces")
    plt.xlabel("Aligned Sample")
    plt.ylabel(processed_column)
    plt.grid(True)
    plt.xlim(0, 175)
    plt.legend()
    plt.tight_layout()
    visualizePlot(command, output_folder=output_folder, name = "MeanCaseMatSoft")

def plotMeanByContactSurfaceCases(means, command, processed_column="LPF_Fz", output_folder = None):

    names = list(means.keys())

    nameList = ['MeanCaseSidePalm', 'MeanCaseThump', 'MeanCaseUpperPalm']
    for graph_idx in range(0, len(names), 4):

        if graph_idx + 3 >= len(names):
            break

        plt.figure(figsize=(10, 6))

        mean1 = average_curves(
            means[names[graph_idx]],
            means[names[graph_idx + 1]]
        )

        mean2 = average_curves(
            means[names[graph_idx + 2]],
            means[names[graph_idx + 3]]
        )

        plt.plot(
            np.arange(len(mean1)),
            mean1,
            color=plt.cm.Reds(0.7),
            linewidth=2,
            label="Hard Surface"
        )

        plt.plot(
            np.arange(len(mean2)),
            mean2, 
            linewidth=2,
            label="Soft Surface"
        )

        surface_titles = [
            "SidePalm",
            "Thumb",
            "UpperPalm"
        ]

        title_idx = graph_idx // 4

        if title_idx < len(surface_titles):
            plt.title(surface_titles[title_idx])
        else:
            plt.title(f"Surface {title_idx + 1}")
        plt.xlabel("Aligned Sample")
        plt.ylabel(processed_column)
        plt.grid(True)
        plt.xlim(0, 175)
        plt.legend()
        plt.tight_layout()
        visualizePlot(command, output_folder=output_folder, name = nameList[graph_idx//4])
    plt.show()

#---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#    █████████                                                                     ███████████  ████            █████   
#   ███░░░░░███                                                                   ░░███░░░░░███░░███           ░░███    
#  ███     ░░░   ██████  █████████████   ████████   ██████   ████████   ██████     ░███    ░███ ░███   ██████  ███████  
# ░███          ███░░███░░███░░███░░███ ░░███░░███ ░░░░░███ ░░███░░███ ███░░███    ░██████████  ░███  ███░░███░░░███░   
# ░███         ░███ ░███ ░███ ░███ ░███  ░███ ░███  ███████  ░███ ░░░ ░███████     ░███░░░░░░   ░███ ░███ ░███  ░███    
# ░░███     ███░███ ░███ ░███ ░███ ░███  ░███ ░███ ███░░███  ░███     ░███░░░      ░███         ░███ ░███ ░███  ░███ ███
#  ░░█████████ ░░██████  █████░███ █████ ░███████ ░░████████ █████    ░░██████     █████        █████░░██████   ░░█████ 
#   ░░░░░░░░░   ░░░░░░  ░░░░░ ░░░ ░░░░░  ░███░░░   ░░░░░░░░ ░░░░░      ░░░░░░     ░░░░░        ░░░░░  ░░░░░░     ░░░░░  
#                                        ░███                                                                           
#                                        █████                                                                          
#                                       ░░░░░       
# ----------------------------------------------------------------------------------------------------------------------------------------------------------

#plt.show only
def plot2SignalAllCSV(
    df,
    force_col="LPF_Fz",
    pos_col="Penpos_z[mm]",
    min_z=275,
    max_z=450
):

    

    force = df[force_col].copy()
    z_pos = df[pos_col].copy()

    # if 'pos' in pos_col.lower():
    #     mask = (z_pos >= min_z) & (z_pos <= max_z)

    #     force[~mask] = np.nan
    #     z_pos[~mask] = np.nan

    fig, ax1 = plt.subplots(figsize=(12, 6))

    ax1.plot(force, color='blue', label=force_col)

    ax2 = ax1.twinx()
    ax2.plot(z_pos, color = 'red', label=pos_col)

    ax1.set_xlabel("Sample")
    ax1.set_ylabel(force_col)
    ax2.set_ylabel(pos_col)
    plt.legend()
    plt.title(f"{force_col} vs {pos_col}")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot3SignalsAllCSV(
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

def plot2SignalSeperateTrial(
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

#plt.save only
def plotAligned2SignalFolder(folder, force_col = "LPF_Fz", pos_col="Penpos_z[mm]", output ="Data/ForceBelowMat/Fz-PosZCompareResult"):
    if not folder.exists():
        print(f"Folder not found: {folder.resolve()}")
        return

    means = {}

    for filepath in sorted(folder.glob("*.csv")):

        print(f"Processing {filepath.name}")

        try:
            plotAligned2Signal(
                filepath,
                output,
                force_col=force_col,
                pos_col=pos_col,
            )
        except Exception as e:
            print(f"Error processing {filepath.name}: {e}")

def plotAligned2Signal(filepath, output_folder,
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

#both
def visualizePlot(command, output_folder = None, filepath = None, name = None):
    match command:
        case "save":
            if output_folder is None or (filepath is None and name is None):
                raise ValueError("output_folder and filepath are required for save mode")

            output_folder = Path(output_folder)
            output_folder.mkdir(parents=True, exist_ok=True)

            if filepath is None:
                save_path = Path(f"{output_folder}/{name}.png")
            else:
                save_path = Path(f"{output_folder}/{Path(filepath).stem}.png")
            plt.savefig(
                save_path,
                dpi=300,
                bbox_inches="tight"
            )
            print(f"Save graph to {save_path}")
            plt.close()
        case "show":
            plt.show()
            plt.close()
        case _:
            raise ValueError(f"Invalid visualize command: {command}")



