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
from scipy.stats import spearmanr, linregress


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
    sum_column="SumForce",
):
    """
    Shared data-collection step used by all heat-map builders below.
    Walks All_Data, computes a per-(file, contact surface) aggregated
    force value, then normalizes it according to `normalize`:

        "fixed":     value / fixed sensor-rated max force per surface
        "global":    value / max ever observed on that surface across the dataset
        "per_file":  value / max observed on that surface within that file
        "sum_force": value / mean total SumForce for that file, i.e. what
                     FRACTION of the total force that surface carried
                     (mean force of that surface / mean total force).
                     Uses `sum_column` if present in the segment, otherwise
                     falls back to summing all `force_columns` on the fly.

    Returns a long-format DataFrame with columns:
        filename, tester, material_trial, column, value,
        max_force, normalized_value
    """
    records = []
    observed_max = {c: 0.0 for c in force_columns}
    file_sum_force = {}  # filename -> mean total force across its touch segments

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

        # If needed, compute this file's mean total force once (shared by
        # every surface's normalization, not recomputed per column).
        if normalize == "sum_force":
            seg_sum_values = []
            for seg in segments:
                if seg.empty:
                    continue
                if sum_column in seg.columns:
                    seg_sum_values.append(seg[sum_column].mean())
                else:
                    present_cols = [c for c in force_columns if c in seg.columns]
                    if present_cols:
                        seg_sum_values.append(seg[present_cols].sum(axis=1).mean())
            if seg_sum_values:
                file_sum_force[filename] = float(np.mean(seg_sum_values))

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
    elif normalize == "sum_force":
        df_records["max_force"] = df_records["filename"].map(file_sum_force)
    else:
        raise ValueError("normalize must be 'fixed', 'global', 'per_file', or 'sum_force'")

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
    normalize="fixed",     # "fixed":     divide by a fixed, known max force per surface
                           #              (pass it via `max_force`, e.g. sensor rated capacity)
                           # "global":    divide by max ever seen on that surface across
                           #              the whole dataset
                           # "per_file":  divide by the max seen within that file only
                           # "sum_force": divide by that file's mean total force
                           #              (meanForce_surface / meanSumForce) -> the
                           #              FRACTION of total force that surface carried
    max_force=None,        # required when normalize="fixed". Either:
                           #   - list/tuple aligned with force_columns, e.g. [80,80,80,20,20,80]
                           #   - dict {column_name: max_force}
    agg="mean",            # how to summarize force within a single touch segment
    column_order=None,     # optional list controlling the X-axis order, e.g.
                           #   ["Pillow1","Pillow2","Foam1","Foam2","Wood1","Wood2"]
                           # matched case-insensitively; any material/trial
                           # combos not listed are appended at the end.
    sum_column="SumForce", # column holding total force, used when normalize="sum_force";
                           # if missing from a segment, falls back to summing force_columns
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
        All_Data, force_columns, segment_key, parse_filename, normalize, max_force, agg, sum_column
    )
    cbar_label = (
        "Mean Force / Mean Total Force" if normalize == "sum_force"
        else "Normalized Mean Force (mean / max)"
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
            cbar_kws={"label": cbar_label},
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
    sum_column="SumForce", # used when normalize="sum_force"; falls back to summing
                           # force_columns if this column isn't present in a segment
    figsize=(9, 6),
    cmap="viridis",
    save_path=None,         # e.g. "outputs/surface_heatmap.png"
):
    """
    Build a SINGLE annotated heat map (averaged across all testers) with:
        rows    = Contact surface (e.g. ThumbPalm, SidePalm, ...)
        columns = Material + Trial number
        cell    = normalized force value, averaged across every tester who
                  touched that material/trial. See `normalize` in
                  _collect_normalized_records for available modes,
                  including normalize="sum_force" for
                  meanForce_surface / meanSumForce (that surface's share
                  of total force).

    This answers "which contact surface sees the most relative force on
    which material?" — collapsing the tester dimension entirely. If you
    want per-tester breakdowns instead, use
    build_surface_vs_material_heatmap_per_tester.

    Returns
    -------
    pd.DataFrame
        The pivoted (surface x material_trial) table of normalized values
        that was plotted.
    """
    df_records = _collect_normalized_records(
        All_Data, force_columns, segment_key, parse_filename, normalize, max_force, agg, sum_column
    )
    cbar_label = (
        "Mean Force / Mean Total Force" if normalize == "sum_force"
        else "Normalized Mean Force (mean / max)"
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
        cbar_kws={"label": cbar_label},
    )
    plt.title("Normalized Mean Force — Contact Surface vs Material/Trial")
    plt.xlabel("Material + Trial")
    plt.ylabel("Contact Surface")
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=200)

    plt.show()

    return pivot


def build_surface_vs_material_heatmap_per_tester(
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
    testers=None,           # optional list to restrict/order which testers get plotted;
                           # None -> every tester found in the data, sorted alphabetically
    sum_column="SumForce", # used when normalize="sum_force"; falls back to summing
                           # force_columns if this column isn't present in a segment
    figsize=(9, 6),
    cmap="viridis",
    save_path=None,         # e.g. "outputs/surface_heatmap" -> saves "outputs/surface_heatmap_Ao.png" etc.
):
    """
    Same as build_surface_vs_material_heatmap, but produces ONE heat map
    PER TESTER instead of averaging everyone together:
        rows    = Contact surface (e.g. ThumbPalm, SidePalm, ...)
        columns = Material + Trial number
        cell    = normalized force value for that tester only. See
                  `normalize` in _collect_normalized_records for available
                  modes, including normalize="sum_force" for
                  meanForce_surface / meanSumForce.

    Returns
    -------
    dict[str, pd.DataFrame]
        {tester_name: pivoted (surface x material_trial) DataFrame}
    """
    df_records = _collect_normalized_records(
        All_Data, force_columns, segment_key, parse_filename, normalize, max_force, agg, sum_column
    )
    cbar_label = (
        "Mean Force / Mean Total Force" if normalize == "sum_force"
        else "Normalized Mean Force (mean / max)"
    )

    all_testers = sorted(df_records["tester"].unique())
    tester_list = testers if testers is not None else all_testers

    pivots = {}
    for tester in tester_list:
        sub = df_records[df_records["tester"] == tester]
        if sub.empty:
            print(f"No data for tester '{tester}', skipping.")
            continue

        pivot = sub.pivot_table(
            index="column",
            columns="material_trial",
            values="normalized_value",
            aggfunc="mean",
        )
        pivot = pivot.rename(index=surface_label)
        pivot = _reorder_columns(pivot, column_order)
        pivot = _reorder_index(pivot, row_order)
        pivots[tester] = pivot

        plt.figure(figsize=figsize)
        sns.heatmap(
            pivot,
            annot=True,
            fmt=".2f",
            cmap=cmap,
            vmin=0,
            vmax=1,
            linewidths=0.5,
            cbar_kws={"label": cbar_label},
        )
        plt.title(f"Normalized Mean Force — {tester}")
        plt.xlabel("Material + Trial")
        plt.ylabel("Contact Surface")
        plt.tight_layout()

        if save_path:
            plt.savefig(f"{save_path}_{tester}.png", dpi=200)

        plt.show()

    return pivots


def material_from_material_trial(material_trial):
    """Strip the trailing trial-number digits off a material_trial string,
    e.g. "Foam1" -> "Foam", "Wood12" -> "Wood"."""
    return re.sub(r"\d+$", "", str(material_trial))


def _resolve_hardness_map(hardness_order):
    """
    Accepts either:
      - an ordered list of material names from softest to hardest,
        e.g. ["Pillow", "Foam", "Wood"] -> ranks 1, 2, 3
      - a dict of {material_name: hardness_value} for a real hardness
        scale (e.g. Shore durometer values), used as-is

    Returns a dict {material_name_lowercase: hardness_value}.
    """
    if isinstance(hardness_order, dict):
        return {str(k).lower(): v for k, v in hardness_order.items()}
    return {str(m).lower(): i + 1 for i, m in enumerate(hardness_order)}


def _prepare_hardness_df(
    All_Data, force_columns, hardness_order, segment_key, parse_filename,
    normalize, max_force, agg, sum_column, surface_label,
):
    """Shared prep: collect records, map material -> hardness, relabel surfaces.
    Returns (df_records, value_col, y_label)."""
    df_records = _collect_normalized_records(
        All_Data, force_columns, segment_key, parse_filename, normalize, max_force, agg, sum_column
    )

    hardness_map = _resolve_hardness_map(hardness_order)

    df_records = df_records.copy()
    df_records["material"] = df_records["material_trial"].apply(material_from_material_trial)
    df_records["hardness"] = df_records["material"].str.lower().map(hardness_map)

    dropped = df_records[df_records["hardness"].isna()]["material"].unique()
    if len(dropped) > 0:
        print(f"Note: materials with no hardness value were dropped: {list(dropped)}")

    df_records = df_records.dropna(subset=["hardness"])
    if df_records.empty:
        raise ValueError(
            "No data left after mapping hardness — check that hardness_order's "
            "material names match the ones your parse_filename produces."
        )

    df_records["surface"] = df_records["column"].apply(surface_label)

    value_col = "normalized_value"
    y_label = (
        "Mean Force / Mean Total Force (usage share)" if normalize == "sum_force"
        else "Normalized Mean Force (mean / max)"
    )
    return df_records, value_col, y_label


def _compute_trend_stats(df_records, surfaces, value_col, min_points=3):
    """Per-surface Spearman correlation + linear regression of value vs hardness."""
    stats_rows = []
    for surf in surfaces:
        sub = df_records[df_records["surface"] == surf]
        if len(sub) < min_points:
            print(f"Skipping stats for '{surf}': fewer than {min_points} data points.")
            continue
        rho, p = spearmanr(sub["hardness"], sub[value_col])
        lin = linregress(sub["hardness"], sub[value_col])
        stats_rows.append({
            "surface": surf,
            "spearman_r": rho,
            "spearman_p": p,
            "slope": lin.slope,
            "intercept": lin.intercept,
            "n_points": len(sub),
        })
    return pd.DataFrame(stats_rows).set_index("surface")


def _plot_trend_lines(df_records, surfaces, value_col, y_label, title, figsize, save_path):
    """One errorbar line per surface: mean +/- std of value_col vs hardness."""
    agg_df = (
        df_records.groupby(["surface", "hardness"])[value_col]
        .agg(["mean", "std"])
        .reset_index()
    )

    plt.figure(figsize=figsize)
    for surf in surfaces:
        sub = agg_df[agg_df["surface"] == surf].sort_values("hardness")
        if sub.empty:
            continue
        plt.errorbar(
            sub["hardness"], sub["mean"], yerr=sub["std"].fillna(0),
            marker="o", capsize=3, label=surf,
        )

    plt.xlabel("Material Hardness")
    plt.ylabel(y_label)
    plt.title(title)
    plt.legend(title="Contact Surface", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.grid(alpha=0.3)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=200, bbox_inches="tight")

    plt.show()


def analyze_surface_hardness_trend(
    All_Data,
    force_columns,
    hardness_order,        # list ["Pillow","Foam","Wood"] (soft->hard) OR
                           # dict {"Pillow":10, "Foam":40, "Wood":90} (real hardness units)
    segment_key="ForHeatMap",
    parse_filename=default_parse_filename,
    normalize="sum_force",  # "sum_force" (share of total force) is recommended for
                            # analyzing WHICH surface is used, independent of grip strength
    max_force=None,         # only needed if normalize="fixed"
    agg="mean",
    sum_column="SumForce",
    surface_label=default_surface_label,
    surface_order=None,     # optional list controlling legend/table order, e.g.
                           #   ["ThumbPalm","SidePalm","UpperPalm","Index","Middle","Thumb"]
    figsize=(9, 6),
    save_path=None,         # e.g. "outputs/hardness_trend.png"
):
    """
    Analyze and plot how each contact surface's normalized force changes
    as material hardness increases — pooling ALL testers together. One
    line per surface, x-axis = hardness (rank or real value), y-axis =
    normalized force (mean +/- std across testers/trials at that hardness
    level).

    Also computes, per surface:
      - Spearman correlation between hardness and normalized value
        (captures monotonic trend strength, robust to non-linearity)
      - Linear regression slope (captures rate/direction of change)

    Only materials present in `hardness_order` are included; any material
    name your parser produces that isn't listed there is dropped (with a
    printed note), since there's no hardness value to plot it against.

    If you want each tester's own trend instead of one pooled trend, use
    analyze_surface_hardness_trend_per_tester.

    Returns
    -------
    trend_stats : pd.DataFrame
        One row per surface: spearman_r, spearman_p, slope, intercept, n_points
    plotted_data : pd.DataFrame
        Long-format data actually used for the plot/stats (surface,
        material, hardness, normalized_value, tester, filename)
    """
    df_records, value_col, y_label = _prepare_hardness_df(
        All_Data, force_columns, hardness_order, segment_key, parse_filename,
        normalize, max_force, agg, sum_column, surface_label,
    )

    surfaces = surface_order if surface_order is not None else sorted(df_records["surface"].unique())
    trend_stats = _compute_trend_stats(df_records, surfaces, value_col)
    _plot_trend_lines(
        df_records, surfaces, value_col, y_label,
        title="Contact Surface Trend vs. Material Hardness (all testers)",
        figsize=figsize, save_path=save_path,
    )

    return trend_stats, df_records


def analyze_surface_hardness_trend_per_tester(
    All_Data,
    force_columns,
    hardness_order,
    segment_key="ForHeatMap",
    parse_filename=default_parse_filename,
    normalize="sum_force",
    max_force=None,
    agg="mean",
    sum_column="SumForce",
    surface_label=default_surface_label,
    surface_order=None,
    testers=None,           # optional list to restrict/order which testers get analyzed;
                           # None -> every tester found in the data, sorted alphabetically
    figsize=(9, 6),
    save_path=None,         # e.g. "outputs/hardness_trend" -> saves "outputs/hardness_trend_Ao.png" etc.
):
    """
    Same as analyze_surface_hardness_trend, but computed and plotted
    SEPARATELY for each tester instead of pooling everyone together —
    useful for spotting individual differences (e.g. one tester
    consistently favors their thumb regardless of material, while
    another's grip shifts a lot with hardness).

    Returns
    -------
    dict[str, tuple[pd.DataFrame, pd.DataFrame]]
        {tester_name: (trend_stats, plotted_data)} — same shape as the
        return value of analyze_surface_hardness_trend, one per tester.
    """
    df_records, value_col, y_label = _prepare_hardness_df(
        All_Data, force_columns, hardness_order, segment_key, parse_filename,
        normalize, max_force, agg, sum_column, surface_label,
    )

    surfaces = surface_order if surface_order is not None else sorted(df_records["surface"].unique())
    all_testers = sorted(df_records["tester"].unique())
    tester_list = testers if testers is not None else all_testers

    results = {}
    for tester in tester_list:
        sub = df_records[df_records["tester"] == tester]
        if sub.empty:
            print(f"No data for tester '{tester}', skipping.")
            continue

        trend_stats = _compute_trend_stats(sub, surfaces, value_col)
        tester_save_path = f"{save_path}_{tester}.png" if save_path else None
        _plot_trend_lines(
            sub, surfaces, value_col, y_label,
            title=f"Contact Surface Trend vs. Material Hardness — {tester}",
            figsize=figsize, save_path=tester_save_path,
        )

        results[tester] = (trend_stats, sub)

    return results


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
#
# # One heat map PER TESTER, rows = Contact surface
# per_tester_pivots = build_surface_vs_material_heatmap_per_tester(
#     All_Data,
#     force_columns,
#     segment_key="ForHeatMap",
#     parse_filename=parse_filename_tester_material_trial,
#     normalize="fixed",
#     max_force=max_force,
#     column_order=column_order,
#     row_order=["ThumbPalm", "SidePalm", "UpperPalm", "Index", "Middle", "Thumb"],
#     save_path="outputs/surface_heatmap",  # -> outputs/surface_heatmap_Ao.png, etc.
# )
#
# # Same as above three, but cells = share of total force
# # (meanForce_surface / meanSumForce) instead of fraction of sensor capacity:
# per_tester_share = build_surface_vs_material_heatmap_per_tester(
#     All_Data,
#     force_columns,
#     segment_key="ForHeatMap",
#     parse_filename=parse_filename_tester_material_trial,
#     normalize="sum_force",       # <-- new mode, no max_force needed
#     sum_column="SumForce",       # column in your CSVs holding total force
#     column_order=column_order,
#     row_order=["ThumbPalm", "SidePalm", "UpperPalm", "Index", "Middle", "Thumb"],
#     save_path="outputs/surface_share_heatmap",
# )
#
# # Trend analysis: does each surface's usage share change as material gets harder?
# # Option A: just give ranked order, soft -> hard (ranks 1,2,3 used as hardness)
# hardness_order = ["Pillow", "Foam", "Wood"]
# # Option B: give real hardness values (e.g. Shore durometer) for a continuous x-axis
# # hardness_order = {"Pillow": 10, "Foam": 40, "Wood": 90}
#
# trend_stats, plotted_data = analyze_surface_hardness_trend(
#     All_Data,
#     force_columns,
#     hardness_order=hardness_order,
#     parse_filename=parse_filename_tester_material_trial,
#     normalize="sum_force",
#     surface_order=["ThumbPalm", "SidePalm", "UpperPalm", "Index", "Middle", "Thumb"],
#     save_path="outputs/hardness_trend.png",
# )
# print(trend_stats)  # spearman_r close to +/-1 with low spearman_p = strong, significant trend
#
# # Same trend analysis, but SEPARATELY for each tester
# per_tester_trends = analyze_surface_hardness_trend_per_tester(
#     All_Data,
#     force_columns,
#     hardness_order=hardness_order,
#     parse_filename=parse_filename_tester_material_trial,
#     normalize="sum_force",
#     surface_order=["ThumbPalm", "SidePalm", "UpperPalm", "Index", "Middle", "Thumb"],
#     save_path="outputs/hardness_trend",  # -> outputs/hardness_trend_Ao.png, etc.
# )
# for tester, (stats, data) in per_tester_trends.items():
#     print(f"--- {tester} ---")
#     print(stats)
# ---------------------------------------------------------------------