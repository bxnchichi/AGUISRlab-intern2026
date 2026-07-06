import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

import numpy as np

def smooth_transition(n, start, end):
    """S-curve from start to end."""
    if n <= 1:
        return np.array([end])

    t = np.linspace(0, 1, n)
    s = t * t * (3 - 2 * t)      # Smoothstep

    return start + (end - start) * s


def create_profile(total_samples, segments):

    profile = np.zeros(total_samples)

    previous_height = 0.0
    previous_change_end = 0

    for i, seg in enumerate(segments):

        # Hold previous value
        profile[previous_change_end:seg["change_start"]] = previous_height

        # Rise
        profile[seg["change_start"]:seg["plateau_start"]] = smooth_transition(
            seg["plateau_start"] - seg["change_start"],
            previous_height,
            seg["height"]
        )

        # Plateau
        profile[seg["plateau_start"]:seg["plateau_end"]] = seg["height"]

        # Next target
        if i == len(segments) - 1:
            next_height = 0
        else:
            next_height = segments[i + 1]["height"]

        # Fall / transition to next plateau
        profile[seg["plateau_end"]:seg["change_end"]] = smooth_transition(
            seg["change_end"] - seg["plateau_end"],
            seg["height"],
            next_height
        )

        previous_height = next_height
        previous_change_end = seg["change_end"]

    profile[previous_change_end:] = 0

    return profile

DraftNo = None
# # Draft1
# DraftNo = 1
# segments = [
#     {
#         "change_start": 0,
#         "plateau_start": 200,
#         "plateau_end": 250,
#         "change_end": 300,
#         "height": 0.8,
#     },
#     {
#         "change_start": 310,
#         "plateau_start": 315,
#         "plateau_end": 425,
#         "change_end": 500,
#         "height": 1.0,
#     },
# ]

# # Draft1_2
# DraftNo = '1_2'
# segments = [
#     {
#         "change_start": 0,
#         "plateau_start": 200,
#         "plateau_end": 250,
#         "change_end": 400,
#         "height": 0.8,
#     },
#     {
#         "change_start": 400,
#         "plateau_start": 475,
#         "plateau_end": 525,
#         "change_end": 600,
#         "height": 1.0,
#     },
# ]

# # Draft2
# DraftNo = 2
# segments = [
#     {
#         "change_start": 0,
#         "plateau_start": 300,
#         "plateau_end": 425,
#         "change_end": 500,
#         "height": 1.0,
#     },
# ]

# # Draft3
# DraftNo = 3
# segments = [
#     {
#         "change_start": 0,
#         "plateau_start": 100,
#         "plateau_end": 105,
#         "change_end": 165,
#         "height": 0.6,
#     },
#     {
#         "change_start": 165,
#         "plateau_start": 170,
#         "plateau_end": 175,
#         "change_end": 250,
#         "height": 0.5,
#     },
#     {
#         "change_start": 250,
#         "plateau_start": 300,
#         "plateau_end": 250+125,
#         "change_end": 250+125+75,
#         "height": 1,
#     },
# ]

# # Draft4
# DraftNo = 4
# segments = [
#     {
#         "change_start": 0,
#         "plateau_start": 50,
#         "plateau_end": 60,
#         "change_end": 150,
#         "height": 0.3,
#     },
#     {
#         "change_start": 150,
#         "plateau_start": 160,
#         "plateau_end": 161,
#         "change_end": 230,
#         "height": 0.9,
#     },
#     {
#         "change_start": 230,
#         "plateau_start": 231,
#         "plateau_end": 232,
#         "change_end": 300,
#         "height": 0.85,
#     },
#     {
#         "change_start": 300,
#         "plateau_start": 360,
#         "plateau_end": 300+125,
#         "change_end": 300+125+75,
#         "height": 1,
#     },
# ]

# # Draft4_2
# DraftNo = '4_2'
# segments = [
#     {
#         "change_start": 0,
#         "plateau_start": 50,
#         "plateau_end": 60,
#         "change_end": 150,
#         "height": 0.3,
#     },
#     {
#         "change_start": 150,
#         "plateau_start": 160,
#         "plateau_end": 161,
#         "change_end": 250,
#         "height": 0.9,
#     },
#     {
#         "change_start": 250,
#         "plateau_start": 251,
#         "plateau_end": 252,
#         "change_end": 370,
#         "height": 0.85,
#     },
#     {
#         "change_start": 370,
#         "plateau_start": 380,
#         "plateau_end": 370+125,
#         "change_end": 370+125+75,
#         "height": 1,
#     },
# ]

# # Draft5
# DraftNo = 5
# segments = [
#     {
#         "change_start": 0,
#         "plateau_start": 160,
#         "plateau_end": 161,
#         "change_end": 200,
#         "height": 1,
#     },
#     {
#         "change_start": 200,
#         "plateau_start": 201,
#         "plateau_end": 202,
#         "change_end": 325,
#         "height": 0.9,
#     },
#     {
#         "change_start": 325,
#         "plateau_start": 335,
#         "plateau_end": 345,
#         "change_end": 570,
#         "height": 0.95,
#     },
# ]

# # Draft5_2
# DraftNo = '5_2'
# segments = [
#     {
#         "change_start": 0,
#         "plateau_start": 160,
#         "plateau_end": 161,
#         "change_end": 200,
#         "height": 1,
#     },
#     {
#         "change_start": 200,
#         "plateau_start": 201,
#         "plateau_end": 202,
#         "change_end": 325,
#         "height": 0.9,
#     },
#     {
#         "change_start": 325,
#         "plateau_start": 335,
#         "plateau_end": 345,
#         "change_end": 570,
#         "height": 0.85,
#     },
# ]


profile = create_profile(570, segments)
x = np.arange(len(profile))
plt.plot(x, profile)
plt.title("Generated Profile")
plt.show()
print("Profile generated successfully.")
# result_df = pd.DataFrame({"profile": profile})
result_df = pd.DataFrame(profile)
output_path = Path(f"Data/ThaiMassage/profileDraft{DraftNo}.csv")
result_df.to_csv(output_path, index=False)
print("Profile saved to:", output_path)