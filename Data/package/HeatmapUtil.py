"""
Build annotated heat maps of normalized mean contact force
(force / max_force) for each contact surface, from the All_Data dict
produced by your segmentation pipeline.

    All_Data = {
        "<filename>.csv": {
            "ForHeatMap":   [DataFrame, DataFrame, ...],  # one per detected touch
            "ForForceTime": [DataFrame, DataFrame, ...],
        },
        ...
    }

Layout of each heat map:
    rows    = Tester
    columns = Material + Trial number
    cell    = normalized mean force for that contact surface
              (mean force during contact) / (max force ever seen on that surface)
"""

import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


def default_parse_filename(filename):
    """
    Default filename parser. ADJUST THIS to match your actual naming
    convention — this is the only part of the pipeline that depends on
    how your files are named.

    Assumes something like: "Alice_Foam1_Trial2.csv" ->
        tester = "Alice", material_trial = "Foam1_Trial2"

    Must return a (tester, material_trial) tuple of strings.
    """
    stem = filename.replace(".csv", "")
    parts = stem.split("_")
    tester = parts[0] if len(parts) > 0 else "Unknown"
    material_trial = "_".join(parts[1:]) if len(parts) > 1 else stem
    return tester, material_trial


def parse_filename_tester_material_trial(filename):
    """
    Parser for filenames like "AoFoam1.csv" where the pattern is:
        <Tester><Material><TrialNumber>
    with no separators, e.g.:
        "AoFoam1.csv"   -> tester="Ao",   material="Foam",  trial="1"
        "AoFoam12.csv"  -> tester="Ao",   material="Foam",  trial="12"
        "SamRubber3.csv"-> tester="Sam",  material="Rubber",trial="3"

    Assumes:
      - Tester name is the FIRST capitalized word (letters only).
      - Trial number is the trailing run of digits.
      - Everything in between is the material name (can be one or more
        capitalized words, e.g. "SiliconeGel").

    Returns (tester, material_trial) where material_trial combines
    material + trial for the heat map's X-axis, e.g. "Foam_1".
    """
    stem = filename.replace(".csv", "")
    match = re.match(r"^([A-Z][a-z]*)(.+?)(\d+)$", stem)
    if not match:
        return "Unknown", stem

    tester, material, trial = match.groups()
    material_trial = f"{material}{trial}"
    return tester, material_trial


def parse_filename_by_uppercase(filename):
    """
    Alternative parser for filenames with NO separators, where each
    logical chunk starts with an uppercase letter, e.g.:
        "AliceFoam1Trial2.csv" -> tokens ["Alice", "Foam1", "Trial2"]
        tester = "Alice", material_trial = "Foam1_Trial2"

    Assumes the FIRST capitalized chunk is the tester name and everything
    after it is material + trial. Adjust the index below if your tester
    name is actually the last chunk instead of the first.
    """
    stem = filename.replace(".csv", "")
    # Split into chunks starting at each uppercase letter. This version
    # keeps runs of capitals together (so "EVA" doesn't get split into
    # "E", "V", "A") by treating an all-caps run followed by a
    # lowercase/digit tail as one token, e.g. "EVAFoam3" -> ["EVA", "Foam3"].
    tokens = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z][a-z0-9]*|[A-Z]+$", stem)

    if not tokens:
        return "Unknown", stem

    tester = tokens[0]
    material_trial = "_".join(tokens[1:]) if len(tokens) > 1 else stem
    return tester, material_trial


def _match_order(existing_labels, desired_order):
    """
    Given a list of existing labels and a desired order (list of strings),
    return existing_labels reordered to match desired_order as closely as
    possible, matching case-insensitively. Labels not mentioned in
    desired_order are appended at the end (never silently dropped).
    """
    if desired_order is None:
        return list(existing_labels)

    lower_to_actual = {str(l).lower(): l for l in existing_labels}
    ordered_actual = [
        lower_to_actual[d.lower()] for d in desired_order if d.lower() in lower_to_actual
    ]
    missing = [l for l in existing_labels if l not in ordered_actual]

    if missing:
        print(f"Note: labels not in the provided order were appended at the end: {missing}")

    return ordered_actual + missing


def _reorder_columns(pivot, column_order):
    """Reorder a pivot table's COLUMNS to match column_order (see _match_order)."""
    return pivot[_match_order(pivot.columns, column_order)]


def _reorder_index(pivot, row_order):
    """Reorder a pivot table's ROWS/index to match row_order (see _match_order)."""
    return pivot.loc[_match_order(pivot.index, row_order)]


def _collect_normalized_records(
    All_Data,
    force_columns,
    segment_key,
    parse_filename,
    normalize,
    max_force,
    agg,
):
    """
    Shared data-collection step used by both heat-map builders below.
    Walks All_Data, computes a per-(file, contact surface) aggregated
    force value, then normalizes it according to `normalize`.

    Returns a long-format DataFrame with columns:
        filename, tester, material_trial, column, value,
        max_force, normalized_value
    """
    records = []
    observed_max = {c: 0.0 for c in force_columns}

    # ---- resolve fixed max-force dict if needed ----
    fixed_max = None
    if normalize == "fixed":
        if max_force is None:
            raise ValueError("normalize='fixed' requires you to pass `max_force`.")
        if isinstance(max_force, dict):
            fixed_max = max_force
        else:
            if len(max_force) != len(force_columns):
                raise ValueError(
                    "`max_force` list must be the same length and order as `force_columns`."
                )
            fixed_max = dict(zip(force_columns, max_force))

    # ---- collect a value per (file, contact surface) ----
    for filename, data in All_Data.items():
        segments = data.get(segment_key, [])
        if not segments:
            continue

        tester, material_trial = parse_filename(filename)

        for col in force_columns:
            seg_values = []
            for seg in segments:
                if col not in seg.columns or seg.empty:
                    continue
                v = seg[col].mean() if agg == "mean" else seg[col].max()
                seg_values.append(v)
                observed_max[col] = max(observed_max[col], seg[col].max())

            if not seg_values:
                continue

            # average across all touch segments detected in this file
            records.append({
                "filename": filename,
                "tester": tester,
                "material_trial": material_trial,
                "column": col,
                "value": float(np.mean(seg_values)),
            })

    if not records:
        raise ValueError(
            "No data collected. Check that force_columns match your "
            "DataFrame columns, segment_key is correct, and All_Data is populated."
        )

    df_records = pd.DataFrame(records)

    # ---- normalize ----
    if normalize == "fixed":
        df_records["max_force"] = df_records["column"].map(fixed_max)
    elif normalize == "global":
        df_records["max_force"] = df_records["column"].map(observed_max)
    elif normalize == "per_file":
        file_col_max = (
            df_records.groupby(["filename", "column"])["value"]
            .transform("max")
        )
        df_records["max_force"] = file_col_max
    else:
        raise ValueError("normalize must be 'fixed', 'global', or 'per_file'")

    df_records["normalized_value"] = (
        df_records["value"] / df_records["max_force"].replace(0, np.nan)
    )

    return df_records


def default_surface_label(column_name):
    """
    Default mapping from a raw force-column name to a short surface label
    for the Y-axis, e.g. "V_ThumbPalm[N]" -> "ThumbPalm".
    Just strips the "V_" prefix and "[N]" suffix.
    """
    return column_name.replace("V_", "").replace("[N]", "")


def build_contact_force_heatmaps(
    All_Data,
    force_columns,
    segment_key="ForHeatMap",
    parse_filename=default_parse_filename,
    normalize="fixed",     # "fixed":    divide by a fixed, known max force per surface
                           #             (pass it via `max_force`, e.g. sensor rated capacity)
                           # "global":   divide by max ever seen on that surface across
                           #             the whole dataset
                           # "per_file": divide by the max seen within that file only
    max_force=None,        # required when normalize="fixed". Either:
                           #   - list/tuple aligned with force_columns, e.g. [80,80,80,20,20,80]
                           #   - dict {column_name: max_force}
    agg="mean",            # how to summarize force within a single touch segment
    column_order=None,     # optional list controlling the X-axis order, e.g.
                           #   ["Pillow1","Pillow2","Foam1","Foam2","Wood1","Wood2"]
                           # matched case-insensitively; any material/trial
                           # combos not listed are appended at the end.
    figsize_per_plot=(7, 5),
    cmap="viridis",
    save_path=None,        # e.g. "outputs/heatmap" -> saves "outputs/heatmap_V_Thumb.png" etc.
):
    """
    Returns
    -------
    dict[str, pd.DataFrame]
        One pivoted (tester x material_trial) table of normalized values
        per force column. Also displays/saves one heat map per column.
    """
    df_records = _collect_normalized_records(
        All_Data, force_columns, segment_key, parse_filename, normalize, max_force, agg
    )

    # ---- pivot + plot one annotated heat map per contact surface ----
    heatmaps = {}
    for col in force_columns:
        sub = df_records[df_records["column"] == col]
        if sub.empty:
            print(f"No data for column '{col}', skipping its heat map.")
            continue

        pivot = sub.pivot_table(
            index="tester",
            columns="material_trial",
            values="normalized_value",
            aggfunc="mean",
        )
        pivot = _reorder_columns(pivot, column_order)
        heatmaps[col] = pivot

        plt.figure(figsize=figsize_per_plot)
        sns.heatmap(
            pivot,
            annot=True,
            fmt=".2f",
            cmap=cmap,
            vmin=0,
            vmax=1,
            linewidths=0.5,
            cbar_kws={"label": "Normalized Mean Force (mean / max)"},
        )
        plt.title(f"Normalized Mean Force — {col}")
        plt.xlabel("Material + Trial")
        plt.ylabel("Tester")
        plt.tight_layout()

        if save_path:
            safe_col = col.replace("[N]", "").replace("/", "_").strip()
            plt.savefig(f"{save_path}_{safe_col}.png", dpi=200)

        plt.show()

    return heatmaps


def build_surface_vs_material_heatmap(
    All_Data,
    force_columns,
    segment_key="ForHeatMap",
    parse_filename=default_parse_filename,
    normalize="fixed",
    max_force=None,
    agg="mean",
    column_order=None,      # X-axis order, e.g. ["Pillow1","Pillow2","Foam1","Foam2","Wood1","Wood2"]
    row_order=None,         # Y-axis order, e.g. ["ThumbPalm","SidePalm","UpperPalm","Index","Middle","Thumb"]
    surface_label=default_surface_label,  # how to turn "V_ThumbPalm[N]" into "ThumbPalm"
    figsize=(9, 6),
    cmap="viridis",
    save_path=None,         # e.g. "outputs/surface_heatmap.png"
):
    """
    Build a SINGLE annotated heat map (averaged across all testers) with:
        rows    = Contact surface (e.g. ThumbPalm, SidePalm, ...)
        columns = Material + Trial number
        cell    = normalized mean force (mean force / max force), averaged
                  across every tester who touched that material/trial

    This answers "which contact surface sees the most relative force on
    which material?" — collapsing the tester dimension entirely. If you
    want per-tester breakdowns instead, use build_contact_force_heatmaps.

    Returns
    -------
    pd.DataFrame
        The pivoted (surface x material_trial) table of normalized values
        that was plotted.
    """
    df_records = _collect_normalized_records(
        All_Data, force_columns, segment_key, parse_filename, normalize, max_force, agg
    )

    pivot = df_records.pivot_table(
        index="column",
        columns="material_trial",
        values="normalized_value",
        aggfunc="mean",   # averages across testers (and across files) automatically
    )

    # Relabel the index from raw column names (e.g. "V_ThumbPalm[N]") to
    # short surface names (e.g. "ThumbPalm")
    pivot = pivot.rename(index=surface_label)

    pivot = _reorder_columns(pivot, column_order)
    pivot = _reorder_index(pivot, row_order)

    plt.figure(figsize=figsize)
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".2f",
        cmap=cmap,
        vmin=0,
        vmax=1,
        linewidths=0.5,
        cbar_kws={"label": "Normalized Mean Force (mean / max)"},
    )
    plt.title("Normalized Mean Force — Contact Surface vs Material/Trial")
    plt.xlabel("Material + Trial")
    plt.ylabel("Contact Surface")
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=200)

    plt.show()

    return pivot


# ---------------------------------------------------------------------
# Example usage:
#
# force_columns = [
#     "V_SidePalm[N]", "V_ThumbPalm[N]", "V_UpperPalm[N]",
#     "V_Middle[N]", "V_Index[N]", "V_Thumb[N]",
# ]
# max_force = [80, 80, 80, 20, 20, 80]  # sensor-rated capacity per surface, same order
# column_order = ["Pillow1", "Pillow2", "Foam1", "Foam2", "Wood1", "Wood2"]
#
# # One heat map per contact surface, rows = Tester
# heatmaps = build_contact_force_heatmaps(
#     All_Data,
#     force_columns,
#     segment_key="ForHeatMap",
#     parse_filename=parse_filename_tester_material_trial,  # matches "AoFoam1.csv"
#     normalize="fixed",
#     max_force=max_force,
#     column_order=column_order,
#     save_path="outputs/contact_heatmap",
# )
#
# # Single heat map, rows = Contact surface, averaged across testers
# surface_pivot = build_surface_vs_material_heatmap(
#     All_Data,
#     force_columns,
#     segment_key="ForHeatMap",
#     parse_filename=parse_filename_tester_material_trial,
#     normalize="fixed",
#     max_force=max_force,
#     column_order=column_order,
#     row_order=["ThumbPalm", "SidePalm", "UpperPalm", "Index", "Middle", "Thumb"],
#     save_path="outputs/surface_heatmap.png",
# )
# ---------------------------------------------------------------------