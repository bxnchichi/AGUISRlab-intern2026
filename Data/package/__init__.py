import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

def detect_rising_edges(csv_file, processed_column, column="LPF_Fz", on_threshold=10.0, off_threshold=5.0, min_gap=100):
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

    Base_signal = pd.read_csv(csv_file)[column].to_numpy()
    Processed_signal = pd.read_csv(csv_file)[processed_column].to_numpy()
    

    edges = []
    armed = True
    last_edge = -np.inf

    for i, value in enumerate(Base_signal):

        if armed:
            if value >= on_threshold and (i - last_edge) > min_gap:
                edges.append(i)
                last_edge = i
                armed = False

        else:
            if value <= off_threshold:
                armed = True

    return Processed_signal, Base_signal, np.array(edges)

