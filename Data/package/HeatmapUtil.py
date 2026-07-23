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


def _hardness_tick_labels(df):
    """
    Given a DataFrame with 'hardness' and 'material' columns (added by
    _prepare_hardness_df / the various plot_*_trend functions), return
    (positions, labels) so the x-axis can show material names ("Pillow",
    "Foam", "Wood") instead of raw hardness numbers (1, 2, 3).

    Used by every hardness/stiffness trend chart so ticks are readable
    regardless of whether hardness_order was a ranked list or a dict of
    real hardness values.
    """
    pairs = (
        df[["hardness", "material"]]
        .drop_duplicates()
        .sort_values("hardness")
    )
    return pairs["hardness"].tolist(), pairs["material"].tolist()


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
    tick_pos, tick_labels = _hardness_tick_labels(df_records)
    plt.xticks(tick_pos, tick_labels)
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


# NOTE: extract_rising_slope() now lives in its own file, rising_slope.py,
# since it doesn't depend on any of the pivot/heatmap machinery above.
# Import it with:
#     from rising_slope import extract_rising_slope


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
#
# # Rising slope of each trial (touch onset -> peak force)
# # extract_rising_slope now lives in its own file: rising_slope.py
# from rising_slope import extract_rising_slope
#
# rising_df = extract_rising_slope(
#     All_Data,
#     force_column="SumForce",
#     segment_key="ForForceTime",
#     parse_filename=parse_filename_tester_material_trial,
#     peak_frac=1.0,     # use e.g. 0.9 if the exact peak sample is noisy
# )
# print(rising_df)
# # Average rising slope per material, across all trials/testers:
# print(rising_df.groupby("material_trial")["rising_slope"].mean())
# ---------------------------------------------------------------------


# ============================================================================
# SECTION: rising_slope.py -- rising slope of force at start of each trial
# ============================================================================
"""
Extract the rising slope of force at the start of each trial, from the
All_Data["<filename>"]["ForForceTime"] segments produced by your
segmentation pipeline.

Requires contact_heatmap.py to be in the same folder (or on your
PYTHONPATH), since it reuses the same filename parsers so tester/material/
trial naming stays consistent across your whole analysis.
"""




def extract_rising_slope(
    All_Data,
    force_column="SumForce",
    segment_key="ForForceTime",
    parse_filename=default_parse_filename,
    time_col="time",
    peak_frac=1.0,          # find the rising phase up to the first point where
                           # force reaches peak_frac * that segment's max force
                           # (1.0 = exact peak; use e.g. 0.9 if the very peak
                           # sample is noisy/spiky)
    min_points=3,           # need at least this many samples in the rising
                           # phase to fit a slope
):
    """
    For each touch segment in All_Data[filename][segment_key] (i.e. each
    trial, cut so it starts at the touching point), compute the RISING
    SLOPE of `force_column` from the first sample (touch onset, t=0) up to
    the point where force reaches its peak.

    For each segment:
      1. Zero the time axis: t = time - time[0], so every trial starts at
         t=0 regardless of when it was recorded absolutely.
      2. Find the rising phase: from t=0 up to the first sample where
         force >= peak_frac * max(force in this segment).
      3. Fit a line (linear regression) through (t, force) over that
         rising phase -> slope = rate of force increase (force units / s).
         Also reports r_squared so you can sanity-check how linear/clean
         the rise actually was (low r_squared = noisy or non-monotonic rise).

    Parameters
    ----------
    All_Data : dict
        {filename: {segment_key: [DataFrame, DataFrame, ...], ...}, ...}
    force_column : str
        Which column to measure the rise of (e.g. "SumForce", or a single
        surface like "V_Thumb[N]").
    segment_key : str
        Which list of cut segments to use (default "ForForceTime").
    parse_filename : callable
        filename -> (tester, material_trial), same as used elsewhere.
    time_col : str
        Name of the time column in each segment.
    peak_frac : float
        Fraction of peak force that defines the end of the "rising phase".
    min_points : int
        Minimum samples required in the rising phase to attempt a fit.

    Returns
    -------
    pd.DataFrame
        One row per touch segment, columns:
            filename, tester, material_trial, segment_index,
            rising_time, rising_slope, intercept, rising_slope_simple,
            peak_force, r_squared, n_points
        `rising_slope` is the regression-fit slope (recommended, more
        robust to noise). `intercept` is the fit's y-intercept (useful for
        reconstructing/plotting the exact fitted line: force = intercept +
        rising_slope * t). `rising_slope_simple` is just
        (peak_force - force[0]) / rising_time, included for reference/
        sanity-checking against the fitted value.
    """
    rows = []

    for filename, data in All_Data.items():
        segments = data.get(segment_key, [])
        if not segments:
            continue

        tester, material_trial = parse_filename(filename)

        for seg_idx, seg in enumerate(segments):
            if seg.empty or force_column not in seg.columns or time_col not in seg.columns:
                continue

            t = seg[time_col].to_numpy(dtype=float)
            force = seg[force_column].to_numpy(dtype=float)

            # Zero time at the first sample -> each trial starts at t=0
            # (this IS the touching point, since ForForceTime segments are
            # already cut to start there).
            t0 = t - t[0]

            peak_force = force.max()
            threshold = peak_frac * peak_force

            # First index where force reaches the threshold
            reach_idx = np.argmax(force >= threshold)  # first True, or 0 if none

            if reach_idx < min_points - 1:
                # Not enough points before the threshold is reached to fit
                # a meaningful slope (e.g. peak happens almost immediately)
                if reach_idx == 0 and force[0] < threshold:
                    print(
                        f"Skipping {filename} segment {seg_idx}: force never "
                        f"reached {peak_frac:.0%} of its peak."
                    )
                    continue
                print(
                    f"Skipping {filename} segment {seg_idx}: only {reach_idx + 1} "
                    f"point(s) in the rising phase (< {min_points} required)."
                )
                continue

            rise_t = t0[: reach_idx + 1]
            rise_force = force[: reach_idx + 1]

            lin = linregress(rise_t, rise_force)
            rising_time = rise_t[-1]  # time (from touch onset) to reach peak
            simple_slope = (
                (rise_force[-1] - rise_force[0]) / rising_time
                if rising_time > 0 else np.nan
            )

            rows.append({
                "filename": filename,
                "tester": tester,
                "material_trial": material_trial,
                "segment_index": seg_idx,
                "rising_time": rising_time,
                "rising_slope": lin.slope,
                "intercept": lin.intercept,
                "rising_slope_simple": simple_slope,
                "peak_force": rise_force[-1],
                "r_squared": lin.rvalue ** 2,
                "n_points": len(rise_t),
            })

    if not rows:
        raise ValueError(
            "No rising slopes could be computed. Check force_column/time_col "
            f"names and that All_Data[...][{segment_key!r}] has data."
        )

    return pd.DataFrame(rows)


def plot_rising_slope_summary(
    rising_df,
    group_by="material_trial",
    value_col="rising_slope",
    hue_col=None,           # e.g. "tester" to show grouped bars per tester
    order=None,             # e.g. ["Pillow1","Pillow2","Foam1","Foam2","Wood1","Wood2"]
    estimator="mean",       # "mean" (with std error bars) or "sum" (total per group,
                           # no error bars since a sum's spread isn't meaningful the
                           # same way)
    title_suffix=None,      # e.g. a tester's name, appended to the title as " — {suffix}"
    figsize=(9, 6),
    palette="viridis",
    save_path=None,
):
    """
    Bar chart summarizing `value_col` (default "rising_slope") across
    groups (default "material_trial").

    Parameters
    ----------
    rising_df : pd.DataFrame
        Output of extract_rising_slope().
    group_by : str
        Column to put on the X-axis (e.g. "material_trial" or "tester").
    value_col : str
        Column to summarize (e.g. "rising_slope", "rising_time", "r_squared").
    hue_col : str or None
        Optional column to split bars by color (e.g. "tester") for a
        grouped bar chart instead of one bar per group_by value.
    order : list or None
        Explicit X-axis order, matched case-insensitively; unlisted values
        are appended at the end (see contact_heatmap._match_order).
    estimator : "mean" or "sum"
        "mean" shows the average value_col per group with std error bars
        (good for comparing typical rising slope across materials/testers).
        "sum" shows the total value_col per group with no error bars (good
        for e.g. "total rising slope accumulated per tester" as a rough
        measure of overall exertion/activity).
    title_suffix : str or None
        Optional text appended to the chart title, e.g. a tester's name
        when calling this once per tester.
    """
    existing = sorted(rising_df[group_by].astype(str).unique())
    ordered = _match_order(existing, order) if order is not None else existing

    if estimator == "sum":
        agg_func = "sum"
        errorbar = None
    elif estimator == "mean":
        agg_func = "mean"
        errorbar = "sd"
    else:
        raise ValueError("estimator must be 'mean' or 'sum'")

    plt.figure(figsize=figsize)
    if hue_col is None:
        # Newer seaborn requires hue to be set to use a palette; assign the
        # x variable as hue and hide the redundant legend it would create.
        sns.barplot(
            data=rising_df, x=group_by, y=value_col,
            hue=group_by, order=ordered, hue_order=ordered,
            estimator=agg_func, errorbar=errorbar,
            palette=palette, capsize=0.1 if errorbar else 0, legend=False,
        )
    else:
        sns.barplot(
            data=rising_df, x=group_by, y=value_col, hue=hue_col,
            order=ordered, estimator=agg_func, errorbar=errorbar,
            palette=palette, capsize=0.1 if errorbar else 0,
        )
    plt.xlabel(group_by.replace("_", " ").title())
    plt.ylabel(value_col.replace("_", " ").title())
    title = (
        f"{estimator.title()} {value_col.replace('_', ' ').title()} "
        f"by {group_by.replace('_', ' ').title()}"
    )
    if title_suffix:
        title += f" — {title_suffix}"
    plt.title(title)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=200, bbox_inches="tight")

    plt.show()


def plot_rising_slope_summary_per_tester(
    rising_df,
    group_by="material_trial",
    value_col="rising_slope",
    order=None,
    estimator="mean",
    testers=None,           # optional list to restrict/order which testers get plotted;
                           # None -> every tester found in rising_df, sorted alphabetically
    figsize=(9, 6),
    palette="viridis",
    save_path=None,         # e.g. "outputs/rising_summary" -> saves "outputs/rising_summary_Ao.png" etc.
):
    """
    Same as plot_rising_slope_summary, but produces ONE summary bar chart
    PER TESTER instead of one chart pooling everyone together — useful for
    comparing each person's own material/trial pattern side by side.

    Parameters
    ----------
    testers : list or None
        Which testers to plot, and in what order. None -> every tester
        found in rising_df, sorted alphabetically.
    (all other parameters are passed straight through to
    plot_rising_slope_summary for each tester's subset of the data)
    """
    all_testers = sorted(rising_df["tester"].unique())
    tester_list = testers if testers is not None else all_testers

    for tester in tester_list:
        sub = rising_df[rising_df["tester"] == tester]
        if sub.empty:
            print(f"No data for tester '{tester}', skipping.")
            continue

        tester_save_path = f"{save_path}_{tester}.png" if save_path else None
        plot_rising_slope_summary(
            sub,
            group_by=group_by,
            value_col=value_col,
            order=order,
            estimator=estimator,
            title_suffix=tester,
            figsize=figsize,
            palette=palette,
            save_path=tester_save_path,
        )


def plot_rising_curve_examples(
    All_Data,
    rising_df,
    force_column="SumForce",
    segment_key="ForForceTime",
    time_col="time",
    n_examples=6,
    random_state=0,
    ncols=3,
    figsize=(13, 8),
    save_path=None,
):
    """
    Diagnostic plot: pick a handful of trials from rising_df and plot each
    one's raw force-vs-time curve (time zeroed at touch onset) with the
    fitted rising-slope line overlaid, so you can visually confirm the
    fits look reasonable (or spot ones that don't -> check r_squared for
    those, or lower peak_frac if the peak sample looks like a noise spike).

    Parameters
    ----------
    All_Data : dict
        The same All_Data used to produce rising_df.
    rising_df : pd.DataFrame
        Output of extract_rising_slope().
    n_examples : int
        How many trials to sample and plot (a grid of subplots).
    random_state : int
        Seed for reproducible sampling of which trials get shown.
    """
    sample = rising_df.sample(min(n_examples, len(rising_df)), random_state=random_state)

    n = len(sample)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)
    axes = axes.reshape(-1)

    for ax, (_, row) in zip(axes, sample.iterrows()):
        seg = All_Data[row["filename"]][segment_key][row["segment_index"]]
        t = seg[time_col].to_numpy(dtype=float)
        force = seg[force_column].to_numpy(dtype=float)
        t0 = t - t[0]

        ax.plot(t0, force, color="steelblue", alpha=0.7, label="raw force")

        fit_t = np.array([0, row["rising_time"]])
        fit_force = row["intercept"] + row["rising_slope"] * fit_t
        ax.plot(fit_t, fit_force, color="crimson", linewidth=2, label="fitted rise")

        ax.axvline(row["rising_time"], color="gray", linestyle="--", alpha=0.5)
        ax.scatter([row["rising_time"]], [row["peak_force"]], color="crimson", zorder=5)

        ax.set_title(
            f"{row['filename']} [{row['segment_index']}]\n"
            f"slope={row['rising_slope']:.2f}, R²={row['r_squared']:.2f}",
            fontsize=9,
        )
        ax.set_xlabel("Time from touch onset (s)")
        ax.set_ylabel(force_column)
        ax.legend(fontsize=7)

    # hide any unused subplot axes
    for ax in axes[n:]:
        ax.axis("off")

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=200, bbox_inches="tight")

    plt.show()


# ---------------------------------------------------------------------
# Example usage:
#
# from rising_slope import extract_rising_slope
# from contact_heatmap import parse_filename_tester_material_trial
#
# rising_df = extract_rising_slope(
#     All_Data,
#     force_column="SumForce",
#     segment_key="ForForceTime",
#     parse_filename=parse_filename_tester_material_trial,
#     peak_frac=1.0,     # use e.g. 0.9 if the exact peak sample is noisy
# )
# print(rising_df)
# # Average rising slope per material, across all trials/testers:
# print(rising_df.groupby("material_trial")["rising_slope"].mean())
#
# # Bar chart: rising slope by material/trial
# plot_rising_slope_summary(
#     rising_df,
#     group_by="material_trial",
#     value_col="rising_slope",
#     order=["Pillow1","Pillow2","Foam1","Foam2","Wood1","Wood2"],
#     save_path="outputs/rising_slope_summary.png",
# )
#
# # Same, but split by tester (grouped bars)
# plot_rising_slope_summary(
#     rising_df,
#     group_by="material_trial",
#     value_col="rising_slope",
#     hue_col="tester",
#     order=["Pillow1","Pillow2","Foam1","Foam2","Wood1","Wood2"],
# )
#
# # Total rising slope SUMMED per tester (no error bars, since sums don't
# # have a meaningful std the same way means do)
# plot_rising_slope_summary(
#     rising_df,
#     group_by="tester",
#     value_col="rising_slope",
#     estimator="sum",
#     save_path="outputs/rising_slope_sum_per_tester.png",
# )
#
# # One summary bar chart PER TESTER (material/trial on X-axis for each person)
# plot_rising_slope_summary_per_tester(
#     rising_df,
#     group_by="material_trial",
#     value_col="rising_slope",
#     order=["Pillow1","Pillow2","Foam1","Foam2","Wood1","Wood2"],
#     save_path="outputs/rising_summary",  # -> outputs/rising_summary_Ao.png, etc.
# )
#
# # Diagnostic: look at a handful of actual curves + their fitted lines
# plot_rising_curve_examples(
#     All_Data,
#     rising_df,
#     n_examples=6,
#     save_path="outputs/rising_slope_examples.png",
# )
# ---------------------------------------------------------------------


# ============================================================================
# SECTION: movement_trend.py -- overall hand position/orientation movement trend
# ============================================================================
"""
Extract position/orientation MOVEMENT (not force) from each trial in
All_Data, and visualize it as a trend LINE GRAPH (one line per axis)
against material hardness — the movement equivalent of
analyze_surface_hardness_trend() in contact_heatmap.py, but for how much
the hand/tool physically moved instead of how much force it applied.

Requires contact_heatmap.py to be in the same folder (reuses its filename
parsers and hardness-mapping helpers).

IMPORTANT: the default column names below (pos_x[mm], pos_y[mm],
pos_z[mm], roll[deg], pitch[deg], yaw[deg]) are guesses at your naming
convention. Pass your own `position_columns` / `orientation_columns`
lists if your CSVs use different header names.
"""



DEFAULT_POSITION_COLUMNS = ["pos_x[mm]", "pos_y[mm]", "pos_z[mm]"]
DEFAULT_ORIENTATION_COLUMNS = ["roll[deg]", "pitch[deg]", "yaw[deg]"]


def extract_movement_metrics(
    All_Data,
    position_columns=None,      # defaults to DEFAULT_POSITION_COLUMNS if None
    orientation_columns=None,   # defaults to DEFAULT_ORIENTATION_COLUMNS if None
    segment_key="ForForceTime",
    parse_filename=default_parse_filename,
    metric="range",             # "range" (max-min), "std", or "abs_max_deviation"
                                # (max absolute deviation from the first sample,
                                # i.e. from the touch-onset position/orientation)
):
    """
    For each trial segment, compute a single summary number per axis
    describing how much that axis moved during the trial.

    Parameters
    ----------
    position_columns, orientation_columns : list[str] or None
        Column names to extract. Adjust these to match your actual CSV
        headers if they differ from the defaults.
    segment_key : str
        Which list of cut segments to use (default "ForForceTime", since
        that's the touch-duration window; use "ForHeatMap" if you'd
        rather measure movement over that window instead).
    metric : "range", "std", or "abs_max_deviation"
        "range": max(axis) - min(axis) over the trial -> total excursion
        "std": standard deviation over the trial -> general variability
        "abs_max_deviation": max(|axis - axis[0]|) -> largest departure
            from the starting position/orientation at touch onset

    Returns
    -------
    pd.DataFrame
        One row per (trial segment, axis):
            filename, tester, material_trial, segment_index,
            axis, axis_type ("position" or "orientation"), value
    """
    position_columns = position_columns if position_columns is not None else DEFAULT_POSITION_COLUMNS
    orientation_columns = orientation_columns if orientation_columns is not None else DEFAULT_ORIENTATION_COLUMNS
    all_axis_columns = list(position_columns) + list(orientation_columns)

    if metric not in ("range", "std", "abs_max_deviation"):
        raise ValueError("metric must be 'range', 'std', or 'abs_max_deviation'")

    rows = []
    missing_cols_seen = set()

    for filename, data in All_Data.items():
        segments = data.get(segment_key, [])
        if not segments:
            continue

        tester, material_trial = parse_filename(filename)

        for seg_idx, seg in enumerate(segments):
            if seg.empty:
                continue

            for col in all_axis_columns:
                if col not in seg.columns:
                    missing_cols_seen.add(col)
                    continue

                series = seg[col].to_numpy(dtype=float)
                if len(series) == 0:
                    continue

                if metric == "range":
                    value = float(series.max() - series.min())
                elif metric == "std":
                    value = float(series.std())
                else:  # abs_max_deviation
                    value = float(np.max(np.abs(series - series[0])))

                axis_type = "position" if col in position_columns else "orientation"
                rows.append({
                    "filename": filename,
                    "tester": tester,
                    "material_trial": material_trial,
                    "segment_index": seg_idx,
                    "axis": col,
                    "axis_type": axis_type,
                    "value": value,
                })

    if missing_cols_seen:
        print(f"Note: these columns were not found in any segment and were skipped: {sorted(missing_cols_seen)}")

    if not rows:
        raise ValueError(
            "No movement data collected. Check that position_columns/"
            "orientation_columns match your actual CSV headers, and that "
            f"All_Data[...][{segment_key!r}] has data."
        )

    return pd.DataFrame(rows)


def plot_movement_trend(
    movement_df,
    hardness_order,        # list ["Pillow","Foam","Wood"] (soft->hard) OR
                           # dict {"Pillow":10,"Foam":40,"Wood":90} (real hardness units)
    axis_order=None,       # optional list controlling line order/legend, e.g.
                           #   ["pos_x[mm]","pos_y[mm]","pos_z[mm]","roll[deg]","pitch[deg]","yaw[deg]"]
    metric_name="range",   # just used for axis label / title text
    title_suffix=None,     # e.g. a tester's name, appended to the title as " — {suffix}"
    figsize=(9, 6),
    save_path=None,
):
    """
    Plot one line per axis: x = material hardness, y = mean movement
    value (+/- std across testers/trials at that hardness level).

    Returns
    -------
    pd.DataFrame
        movement_df with `material` and `hardness` columns added, filtered
        to only the rows whose material had a hardness value (this is
        what was actually plotted).
    """
    df = movement_df.copy()
    df["material"] = df["material_trial"].apply(material_from_material_trial)

    hardness_map = _resolve_hardness_map(hardness_order)
    df["hardness"] = df["material"].str.lower().map(hardness_map)

    dropped = df[df["hardness"].isna()]["material"].unique()
    if len(dropped) > 0:
        print(f"Note: materials with no hardness value were dropped: {list(dropped)}")

    df = df.dropna(subset=["hardness"])
    if df.empty:
        raise ValueError(
            "No data left after mapping hardness — check that hardness_order's "
            "material names match the ones your parse_filename produces."
        )

    axes = axis_order if axis_order is not None else sorted(df["axis"].unique())

    agg_df = (
        df.groupby(["axis", "hardness"])["value"]
        .agg(["mean", "std"])
        .reset_index()
    )

    plt.figure(figsize=figsize)
    for axis_name in axes:
        sub = agg_df[agg_df["axis"] == axis_name].sort_values("hardness")
        if sub.empty:
            continue
        plt.errorbar(
            sub["hardness"], sub["mean"], yerr=sub["std"].fillna(0),
            marker="o", capsize=3, label=axis_name,
        )

    plt.xlabel("Material Hardness")
    plt.ylabel(f"Movement {metric_name.title()}")
    title = f"Movement {metric_name.title()} vs. Material Hardness"
    if title_suffix:
        title += f" — {title_suffix}"
    plt.title(title)
    tick_pos, tick_labels = _hardness_tick_labels(df)
    plt.xticks(tick_pos, tick_labels)
    plt.legend(title="Axis", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.grid(alpha=0.3)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=200, bbox_inches="tight")

    plt.show()

    return df


def plot_movement_trend_per_tester(
    movement_df,
    hardness_order,
    axis_order=None,
    metric_name="range",
    testers=None,           # optional list to restrict/order which testers get plotted;
                           # None -> every tester found in movement_df, sorted alphabetically
    figsize=(9, 6),
    save_path=None,         # e.g. "outputs/movement_trend" -> saves "outputs/movement_trend_Ao.png" etc.
):
    """
    Same as plot_movement_trend, but produces ONE trend chart PER TESTER
    instead of pooling everyone together — useful for spotting individual
    differences in how each person's movement changes with hardness (e.g.
    one tester keeps their wrist steadier regardless of material, while
    another's motion range grows a lot on harder surfaces).

    Returns
    -------
    dict[str, pd.DataFrame]
        {tester_name: plotted_df} — plotted_df is movement_df filtered to
        that tester, with `material`/`hardness` columns added (same shape
        returned by plot_movement_trend).
    """
    all_testers = sorted(movement_df["tester"].unique())
    tester_list = testers if testers is not None else all_testers

    results = {}
    for tester in tester_list:
        sub = movement_df[movement_df["tester"] == tester]
        if sub.empty:
            print(f"No data for tester '{tester}', skipping.")
            continue

        tester_save_path = f"{save_path}_{tester}.png" if save_path else None
        plotted = plot_movement_trend(
            sub,
            hardness_order=hardness_order,
            axis_order=axis_order,
            metric_name=metric_name,
            title_suffix=tester,
            figsize=figsize,
            save_path=tester_save_path,
        )
        results[tester] = plotted

    return results


def plot_movement_trend_all_testers(
    movement_df,
    hardness_order,
    axis_type="position",   # "position" or "orientation" -- which set of axes to plot
    axis_order=None,        # optional list controlling which axes (within axis_type) get
                           # plotted and in what order, e.g. ["pos_x[mm]","pos_y[mm]","pos_z[mm]"]
    ncols=3,
    figsize=(14, 8),
    save_path=None,         # e.g. "outputs/position_trend_all_testers.png"
):
    """
    For ONE axis_type ("position" or "orientation"), plot one subplot per
    axis (e.g. pos_x, pos_y, pos_z), each showing:
      - one solid line per tester (mean value vs hardness)
      - one black dashed line: the AVERAGE across testers at each
        hardness level

    This lets you see individual differences (spread of the solid lines)
    alongside the overall trend (the dashed average) in a single view.

    Parameters
    ----------
    movement_df : pd.DataFrame
        Output of extract_movement_metrics().
    hardness_order : list or dict
        Same as in plot_movement_trend — soft->hard ordered list, or a
        dict of real hardness values.
    axis_type : "position" or "orientation"
        Which set of axes to plot (position: pos_x/y/z, orientation:
        roll/pitch/yaw, based on how extract_movement_metrics tagged them).
    axis_order : list or None
        Which specific axes (within axis_type) to include, and in what
        order. None -> every axis of that type found in the data.

    Returns
    -------
    pd.DataFrame
        movement_df filtered to axis_type, with `material`/`hardness`
        columns added (i.e. what was actually plotted).
    """
    if axis_type not in ("position", "orientation"):
        raise ValueError("axis_type must be 'position' or 'orientation'")

    df = movement_df[movement_df["axis_type"] == axis_type].copy()
    if df.empty:
        raise ValueError(f"No rows with axis_type='{axis_type}' found in movement_df.")

    df["material"] = df["material_trial"].apply(material_from_material_trial)
    hardness_map = _resolve_hardness_map(hardness_order)
    df["hardness"] = df["material"].str.lower().map(hardness_map)

    dropped = df[df["hardness"].isna()]["material"].unique()
    if len(dropped) > 0:
        print(f"Note: materials with no hardness value were dropped: {list(dropped)}")

    df = df.dropna(subset=["hardness"])
    if df.empty:
        raise ValueError(
            "No data left after mapping hardness — check that hardness_order's "
            "material names match the ones your parse_filename produces."
        )

    axes_list = axis_order if axis_order is not None else sorted(df["axis"].unique())
    testers = sorted(df["tester"].unique())

    n = len(axes_list)
    nrows = int(np.ceil(n / ncols))
    fig, subplot_axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)
    subplot_axes = subplot_axes.reshape(-1)

    for ax, axis_name in zip(subplot_axes, axes_list):
        sub = df[df["axis"] == axis_name]
        if sub.empty:
            ax.axis("off")
            continue

        tester_means = {}
        for tester in testers:
            tsub = sub[sub["tester"] == tester].groupby("hardness")["value"].mean()
            if tsub.empty:
                continue
            tester_means[tester] = tsub
            ax.plot(tsub.index, tsub.values, marker="o", label=tester)

        if tester_means:
            # Average of the tester-level curves (equal weight per tester),
            # so the dashed line matches the visual mean of the solid lines.
            combined = pd.concat(tester_means.values(), axis=1)
            avg = combined.mean(axis=1, skipna=True).sort_index()
            ax.plot(
                avg.index, avg.values,
                linestyle="--", color="black", linewidth=2, marker="s",
                label="Average",
            )

        ax.set_title(axis_name, fontsize=10)
        ax.set_xlabel("Material Hardness")
        ax.set_ylabel("Value")
        tick_pos, tick_labels = _hardness_tick_labels(sub)
        ax.set_xticks(tick_pos)
        ax.set_xticklabels(tick_labels)
        ax.legend(fontsize=7)
        ax.grid(alpha=0.3)

    for ax in subplot_axes[n:]:
        ax.axis("off")

    fig.suptitle(f"{axis_type.title()} Movement vs. Material Hardness (per tester + average)")
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=200, bbox_inches="tight")

    plt.show()

    return df


# ---------------------------------------------------------------------
# Example usage:
#
# from movement_trend import extract_movement_metrics, plot_movement_trend
# from contact_heatmap import parse_filename_tester_material_trial
#
# movement_df = extract_movement_metrics(
#     All_Data,
#     position_columns=["pos_x[mm]", "pos_y[mm]", "pos_z[mm]"],       # adjust to your headers
#     orientation_columns=["roll[deg]", "pitch[deg]", "yaw[deg]"],    # adjust to your headers
#     segment_key="ForForceTime",
#     parse_filename=parse_filename_tester_material_trial,
#     metric="range",   # or "std" / "abs_max_deviation"
# )
#
# plotted_df = plot_movement_trend(
#     movement_df,
#     hardness_order=["Pillow", "Foam", "Wood"],   # or a dict of real hardness values
#     axis_order=["pos_x[mm]", "pos_y[mm]", "pos_z[mm]", "roll[deg]", "pitch[deg]", "yaw[deg]"],
#     metric_name="range",
#     save_path="outputs/movement_trend.png",
# )
#
# # Same, but one trend chart PER TESTER
# per_tester_movement = plot_movement_trend_per_tester(
#     movement_df,
#     hardness_order=["Pillow", "Foam", "Wood"],
#     axis_order=["pos_x[mm]", "pos_y[mm]", "pos_z[mm]", "roll[deg]", "pitch[deg]", "yaw[deg]"],
#     metric_name="range",
#     save_path="outputs/movement_trend",  # -> outputs/movement_trend_Ao.png, etc.
# )
#
# # Position axes, one subplot each, all testers overlaid + dashed average line
# plot_movement_trend_all_testers(
#     movement_df,
#     hardness_order=["Pillow", "Foam", "Wood"],
#     axis_type="position",
#     axis_order=["pos_x[mm]", "pos_y[mm]", "pos_z[mm]"],
#     save_path="outputs/position_trend_all_testers.png",
# )
#
# # Same for orientation axes
# plot_movement_trend_all_testers(
#     movement_df,
#     hardness_order=["Pillow", "Foam", "Wood"],
#     axis_type="orientation",
#     axis_order=["roll[deg]", "pitch[deg]", "yaw[deg]"],
#     save_path="outputs/orientation_trend_all_testers.png",
# )
# ---------------------------------------------------------------------


# ============================================================================
# SECTION: surface_position_trend.py -- per-surface position trend
# ============================================================================
"""
Extract POSITION (x, y, z) for each individual contact surface (Thumb,
Index, UpperPalm, ThumbPalm, SidePalm) from All_Data, and visualize it as
a trend line graph — one line per surface, per axis, against material
hardness.

This is different from movement_trend.py, which tracks the overall
probe/hand's position. Here, each contact surface has its OWN position
sensor (e.g. where that finger/palm region physically was).

Requires contact_heatmap.py to be in the same folder (reuses its filename
parsers and hardness-mapping helpers).

IMPORTANT: DEFAULT_SURFACE_POSITION_COLUMNS below matches header naming
like "thumbPos_x[mm]", "indexPos_y[mm]", etc. If your CSVs use different
names, pass your own `surface_columns` dict -- the function will print a
note listing any column it couldn't find, so you'll know right away if
something's misnamed.
"""



# Best-guess column naming: {surface: {"x": col, "y": col, "z": col}}
# Matches header naming like "thumbPos_x[mm]", "indexPos_y[mm]", etc.
# Note: there is no position sensor for "Middle" (unlike the force columns,
# which do include V_Middle[N]) -- only these 5 contact surfaces have
# position data, plus "Hand" for the overall hand/probe position.
# "Hand" column names are a GUESS following the same naming convention
# ("handPos_x[mm]") -- adjust surface_columns if your real header differs.
DEFAULT_SURFACE_POSITION_COLUMNS = {
    "Thumb": {
        "x": "thumbPos_x[mm]", "y": "thumbPos_y[mm]", "z": "thumbPos_z[mm]",
    },
    "Index": {
        "x": "indexPos_x[mm]", "y": "indexPos_y[mm]", "z": "indexPos_z[mm]",
    },
    "UpperPalm": {
        "x": "upperPalmPos_x[mm]", "y": "upperPalmPos_y[mm]", "z": "upperPalmPos_z[mm]",
    },
    "SidePalm": {
        "x": "sidePalmPos_x[mm]", "y": "sidePalmPos_y[mm]", "z": "sidePalmPos_z[mm]",
    },
    "ThumbPalm": {
        "x": "thumbPalmPos_x[mm]", "y": "thumbPalmPos_y[mm]", "z": "thumbPalmPos_z[mm]",
    },
    "Hand": {
        "x": "pos_x[mm]", "y": "pos_y[mm]", "z": "pos_z[mm]",
    },
}


def extract_surface_positions(
    All_Data,
    surface_columns=None,   # dict {surface: {"x": col, "y": col, "z": col}};
                           # defaults to DEFAULT_SURFACE_POSITION_COLUMNS if None
    segment_key="ForForceTime",
    parse_filename=default_parse_filename,
    metric="mean",           # "mean" (average position during the trial),
                           # "range" (max-min), or "std"
):
    """
    For each trial segment, compute a single summary position value per
    (contact surface, axis).

    Parameters
    ----------
    surface_columns : dict or None
        {surface_name: {"x": col_name, "y": col_name, "z": col_name}}.
        Any axis you don't have data for can just be omitted from the
        inner dict. Defaults to DEFAULT_SURFACE_POSITION_COLUMNS -- ADJUST
        THIS to your real column names.
    segment_key : str
        Which list of cut segments to use (default "ForForceTime").
    parse_filename : callable
        filename -> (tester, material_trial), same as used elsewhere.
    metric : "mean", "range", or "std"
        "mean": average position during the trial -> WHERE that surface
            typically was (recommended default for "position of surface X")
        "range": max(axis) - min(axis) -> how much that surface moved
        "std": standard deviation -> general positional variability

    Returns
    -------
    pd.DataFrame
        One row per (trial segment, surface, axis):
            filename, tester, material_trial, segment_index,
            surface, axis, value
    """
    surface_columns = surface_columns if surface_columns is not None else DEFAULT_SURFACE_POSITION_COLUMNS

    if metric not in ("mean", "range", "std"):
        raise ValueError("metric must be 'mean', 'range', or 'std'")

    rows = []
    missing_cols_seen = set()

    for filename, data in All_Data.items():
        segments = data.get(segment_key, [])
        if not segments:
            continue

        tester, material_trial = parse_filename(filename)

        for seg_idx, seg in enumerate(segments):
            if seg.empty:
                continue

            for surface, axis_cols in surface_columns.items():
                for axis, col in axis_cols.items():
                    if col not in seg.columns:
                        missing_cols_seen.add(col)
                        continue

                    series = seg[col].to_numpy(dtype=float)
                    if len(series) == 0:
                        continue

                    if metric == "mean":
                        value = float(series.mean())
                    elif metric == "range":
                        value = float(series.max() - series.min())
                    else:  # std
                        value = float(series.std())

                    rows.append({
                        "filename": filename,
                        "tester": tester,
                        "material_trial": material_trial,
                        "segment_index": seg_idx,
                        "surface": surface,
                        "axis": axis,
                        "value": value,
                    })

    if missing_cols_seen:
        print(f"Note: these columns were not found in any segment and were skipped: {sorted(missing_cols_seen)}")

    if not rows:
        raise ValueError(
            "No surface position data collected. Check that surface_columns "
            f"match your actual CSV headers, and that All_Data[...][{segment_key!r}] has data."
        )

    return pd.DataFrame(rows)


def plot_surface_position_trend(
    surface_pos_df,
    hardness_order,        # list ["Pillow","Foam","Wood"] (soft->hard) OR
                           # dict {"Pillow":10,"Foam":40,"Wood":90} (real hardness units)
    axis_order=("x", "y", "z"),  # which axes to plot, one subplot each
    surface_order=None,    # optional list controlling line order/legend, e.g.
                           #   ["Thumb","Index","UpperPalm","ThumbPalm","SidePalm"]
    metric_name="mean",    # just used for axis label / title text
    title_suffix=None,     # e.g. a tester's name, appended to the title as " — {suffix}"
    ncols=3,
    figsize=(14, 5),
    save_path=None,        # e.g. "outputs/surface_position_trend.png"
):
    """
    Plot one subplot per axis (x, y, z); within each subplot, one line per
    contact surface: x-axis = material hardness, y-axis = mean position
    value (+/- std across testers/trials at that hardness level).

    Returns
    -------
    pd.DataFrame
        surface_pos_df with `material` and `hardness` columns added,
        filtered to only rows whose material had a hardness value.
    """
    df = surface_pos_df.copy()
    df["material"] = df["material_trial"].apply(material_from_material_trial)

    hardness_map = _resolve_hardness_map(hardness_order)
    df["hardness"] = df["material"].str.lower().map(hardness_map)

    dropped = df[df["hardness"].isna()]["material"].unique()
    if len(dropped) > 0:
        print(f"Note: materials with no hardness value were dropped: {list(dropped)}")

    df = df.dropna(subset=["hardness"])
    if df.empty:
        raise ValueError(
            "No data left after mapping hardness — check that hardness_order's "
            "material names match the ones your parse_filename produces."
        )

    surfaces = surface_order if surface_order is not None else sorted(df["surface"].unique())
    axes_list = [a for a in axis_order if a in df["axis"].unique()]

    n = len(axes_list)
    nrows = int(np.ceil(n / ncols))
    fig, subplot_axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)
    subplot_axes = subplot_axes.reshape(-1)

    for ax, axis_name in zip(subplot_axes, axes_list):
        sub = df[df["axis"] == axis_name]

        agg_df = (
            sub.groupby(["surface", "hardness"])["value"]
            .agg(["mean", "std"])
            .reset_index()
        )

        for surface in surfaces:
            surf_sub = agg_df[agg_df["surface"] == surface].sort_values("hardness")
            if surf_sub.empty:
                continue
            ax.errorbar(
                surf_sub["hardness"], surf_sub["mean"], yerr=surf_sub["std"].fillna(0),
                marker="o", capsize=3, label=surface,
            )

        ax.set_title(f"Axis: {axis_name}", fontsize=10)
        ax.set_xlabel("Material Hardness")
        ax.set_ylabel(f"{metric_name.title()} Position")
        tick_pos, tick_labels = _hardness_tick_labels(sub)
        ax.set_xticks(tick_pos)
        ax.set_xticklabels(tick_labels)
        ax.legend(title="Surface", fontsize=7)
        ax.grid(alpha=0.3)

    for ax in subplot_axes[n:]:
        ax.axis("off")

    title = "Contact Surface Position vs. Material Hardness"
    if title_suffix:
        title += f" — {title_suffix}"
    fig.suptitle(title)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=200, bbox_inches="tight")

    plt.show()

    return df


def plot_surface_position_trend_per_tester(
    surface_pos_df,
    hardness_order,
    axis_order=("x", "y", "z"),
    surface_order=None,
    metric_name="mean",
    testers=None,           # optional list to restrict/order which testers get plotted;
                           # None -> every tester found in surface_pos_df, sorted alphabetically
    ncols=3,
    figsize=(14, 5),
    save_path=None,         # e.g. "outputs/surface_position_trend" -> saves
                           # "outputs/surface_position_trend_Ao.png" etc.
):
    """
    Same as plot_surface_position_trend, but produces ONE set of subplots
    PER TESTER instead of pooling everyone together — useful for spotting
    individual differences in how each person's contact-surface positions
    shift with material hardness.

    Returns
    -------
    dict[str, pd.DataFrame]
        {tester_name: plotted_df} — plotted_df is surface_pos_df filtered
        to that tester, with `material`/`hardness` columns added (same
        shape returned by plot_surface_position_trend).
    """
    all_testers = sorted(surface_pos_df["tester"].unique())
    tester_list = testers if testers is not None else all_testers

    results = {}
    for tester in tester_list:
        sub = surface_pos_df[surface_pos_df["tester"] == tester]
        if sub.empty:
            print(f"No data for tester '{tester}', skipping.")
            continue

        tester_save_path = f"{save_path}_{tester}.png" if save_path else None
        plotted = plot_surface_position_trend(
            sub,
            hardness_order=hardness_order,
            axis_order=axis_order,
            surface_order=surface_order,
            metric_name=metric_name,
            title_suffix=tester,
            ncols=ncols,
            figsize=figsize,
            save_path=tester_save_path,
        )
        results[tester] = plotted

    return results


def extract_surface_relative_position(
    All_Data,
    surface_columns=None,   # dict of surfaces to include (excluding "Hand");
                           # defaults to all surfaces in DEFAULT_SURFACE_POSITION_COLUMNS
                           # except "Hand" itself
    hand_columns=None,      # dict {"x": col, "y": col, "z": col} for the hand's own
                           # position; defaults to DEFAULT_SURFACE_POSITION_COLUMNS["Hand"]
    segment_key="ForForceTime",
    parse_filename=default_parse_filename,
    metric="mean",           # "mean" (average offset during the trial),
                           # "range" (max-min of the offset), or "std"
):
    """
    For each trial segment, compute each contact surface's position
    RELATIVE TO THE HAND: (surface_axis - hand_axis), sample-by-sample,
    then summarized with `metric` -- i.e. how far and in which direction
    that surface sits from the hand's own reference position, and whether
    that offset shifts (e.g. with material hardness).

    A roughly constant offset across materials means that surface stays
    in a fixed position relative to the hand (e.g. rigid anatomy); a
    changing offset means the surface moves relative to the hand itself
    (e.g. the thumb splays out more on harder materials).

    Parameters
    ----------
    surface_columns : dict or None
        {surface_name: {"x": col, "y": col, "z": col}}. Defaults to every
        surface in DEFAULT_SURFACE_POSITION_COLUMNS except "Hand".
    hand_columns : dict or None
        {"x": col, "y": col, "z": col} for the hand's own position.
        Defaults to DEFAULT_SURFACE_POSITION_COLUMNS["Hand"].
    metric : "mean", "range", or "std"
        Applied to the per-sample (surface - hand) offset within each trial.

    Returns
    -------
    pd.DataFrame
        One row per (trial segment, surface, axis):
            filename, tester, material_trial, segment_index,
            surface, axis, value
        `value` is in the same units as your position columns (e.g. mm),
        representing surface position relative to the hand.
    """
    if surface_columns is None:
        surface_columns = {
            k: v for k, v in DEFAULT_SURFACE_POSITION_COLUMNS.items() if k != "Hand"
        }
    if hand_columns is None:
        hand_columns = DEFAULT_SURFACE_POSITION_COLUMNS["Hand"]

    if metric not in ("mean", "range", "std"):
        raise ValueError("metric must be 'mean', 'range', or 'std'")

    rows = []
    missing_cols_seen = set()

    for filename, data in All_Data.items():
        segments = data.get(segment_key, [])
        if not segments:
            continue

        tester, material_trial = parse_filename(filename)

        for seg_idx, seg in enumerate(segments):
            if seg.empty:
                continue

            for surface, axis_cols in surface_columns.items():
                for axis, col in axis_cols.items():
                    hand_col = hand_columns.get(axis)

                    if col not in seg.columns:
                        missing_cols_seen.add(col)
                        continue
                    if hand_col is None or hand_col not in seg.columns:
                        if hand_col is not None:
                            missing_cols_seen.add(hand_col)
                        continue

                    surf_series = seg[col].to_numpy(dtype=float)
                    hand_series = seg[hand_col].to_numpy(dtype=float)
                    if len(surf_series) == 0 or len(hand_series) == 0:
                        continue

                    offset = surf_series - hand_series

                    if metric == "mean":
                        value = float(offset.mean())
                    elif metric == "range":
                        value = float(offset.max() - offset.min())
                    else:  # std
                        value = float(offset.std())

                    rows.append({
                        "filename": filename,
                        "tester": tester,
                        "material_trial": material_trial,
                        "segment_index": seg_idx,
                        "surface": surface,
                        "axis": axis,
                        "value": value,
                    })

    if missing_cols_seen:
        print(f"Note: these columns were not found in any segment and were skipped: {sorted(missing_cols_seen)}")

    if not rows:
        raise ValueError(
            "No relative position data collected. Check that surface_columns/"
            f"hand_columns match your actual CSV headers, and that All_Data[...][{segment_key!r}] has data."
        )

    return pd.DataFrame(rows)


def plot_surface_relative_position_trend(
    relative_pos_df,
    hardness_order,
    axis_order=("x", "y", "z"),
    surface_order=None,
    metric_name="mean",
    ncols=3,
    figsize=(14, 5),
    save_path=None,        # e.g. "outputs/surface_relative_position_trend.png"
):
    """
    Same visual style as plot_surface_position_trend, but for RELATIVE
    position (surface - hand) instead of absolute position. One subplot
    per axis (x, y, z); within each, one line per surface: x-axis =
    material hardness, y-axis = mean offset from the hand (+/- std).

    A flat line near a surface's typical offset means that surface's
    position relative to the hand doesn't change with hardness; a
    sloped line means it does (e.g. fingers splaying more on hard
    surfaces).

    Returns
    -------
    pd.DataFrame
        relative_pos_df with `material`/`hardness` columns added, filtered
        to rows whose material had a hardness value.
    """
    df = relative_pos_df.copy()
    df["material"] = df["material_trial"].apply(material_from_material_trial)

    hardness_map = _resolve_hardness_map(hardness_order)
    df["hardness"] = df["material"].str.lower().map(hardness_map)

    dropped = df[df["hardness"].isna()]["material"].unique()
    if len(dropped) > 0:
        print(f"Note: materials with no hardness value were dropped: {list(dropped)}")

    df = df.dropna(subset=["hardness"])
    if df.empty:
        raise ValueError(
            "No data left after mapping hardness — check that hardness_order's "
            "material names match the ones your parse_filename produces."
        )

    surfaces = surface_order if surface_order is not None else sorted(df["surface"].unique())
    axes_list = [a for a in axis_order if a in df["axis"].unique()]

    n = len(axes_list)
    nrows = int(np.ceil(n / ncols))
    fig, subplot_axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)
    subplot_axes = subplot_axes.reshape(-1)

    for ax, axis_name in zip(subplot_axes, axes_list):
        sub = df[df["axis"] == axis_name]

        agg_df = (
            sub.groupby(["surface", "hardness"])["value"]
            .agg(["mean", "std"])
            .reset_index()
        )

        for surface in surfaces:
            surf_sub = agg_df[agg_df["surface"] == surface].sort_values("hardness")
            if surf_sub.empty:
                continue
            ax.errorbar(
                surf_sub["hardness"], surf_sub["mean"], yerr=surf_sub["std"].fillna(0),
                marker="o", capsize=3, label=surface,
            )

        ax.axhline(0, color="gray", linestyle=":", linewidth=1)
        ax.set_title(f"Axis: {axis_name}", fontsize=10)
        ax.set_xlabel("Material Hardness")
        ax.set_ylabel(f"{metric_name.title()} Offset from Hand")
        tick_pos, tick_labels = _hardness_tick_labels(sub)
        ax.set_xticks(tick_pos)
        ax.set_xticklabels(tick_labels)
        ax.legend(title="Surface", fontsize=7)
        ax.grid(alpha=0.3)

    for ax in subplot_axes[n:]:
        ax.axis("off")

    fig.suptitle("Contact Surface Position RELATIVE TO HAND vs. Material Hardness")
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=200, bbox_inches="tight")

    plt.show()

    return df


# ---------------------------------------------------------------------
# Example usage:
#
# from surface_position_trend import extract_surface_positions, plot_surface_position_trend
# from contact_heatmap import parse_filename_tester_material_trial
#
# # ADJUST surface_columns to your real CSV headers if they differ from
# # the DEFAULT_SURFACE_POSITION_COLUMNS guess in this file!
# surface_pos_df = extract_surface_positions(
#     All_Data,
#     segment_key="ForForceTime",
#     parse_filename=parse_filename_tester_material_trial,
#     metric="mean",   # or "range" / "std"
# )
#
# plotted_df = plot_surface_position_trend(
#     surface_pos_df,
#     hardness_order=["Pillow", "Foam", "Wood"],
#     surface_order=["Thumb", "Index", "UpperPalm", "ThumbPalm", "SidePalm", "Hand"],
#     metric_name="mean",
#     save_path="outputs/surface_position_trend.png",
# )
#
# # Same, but one set of subplots PER TESTER
# per_tester_surface_pos = plot_surface_position_trend_per_tester(
#     surface_pos_df,
#     hardness_order=["Pillow", "Foam", "Wood"],
#     surface_order=["Thumb", "Index", "UpperPalm", "ThumbPalm", "SidePalm", "Hand"],
#     metric_name="mean",
#     save_path="outputs/surface_position_trend",  # -> outputs/surface_position_trend_Ao.png, etc.
# )
#
# # Position of each surface RELATIVE TO THE HAND (surface - hand offset)
# relative_pos_df = extract_surface_relative_position(
#     All_Data,
#     segment_key="ForForceTime",
#     parse_filename=parse_filename_tester_material_trial,
#     metric="mean",
# )
#
# plot_surface_relative_position_trend(
#     relative_pos_df,
#     hardness_order=["Pillow", "Foam", "Wood"],
#     surface_order=["Thumb", "Index", "UpperPalm", "ThumbPalm", "SidePalm"],
#     metric_name="mean",
#     save_path="outputs/surface_relative_position_trend.png",
# )
# ---------------------------------------------------------------------


# ============================================================================
# SECTION: position_timeseries.py -- position over time during force application
# ============================================================================
"""
Extract how POSITION changes OVER TIME during force application (i.e.
within each touch segment), for the hand and every contact surface --
unlike surface_position_trend.py, which summarizes each trial down to a
single number (mean/range/std), this keeps the full time-series so you
can see the actual movement trace during contact.

Requires contact_heatmap.py and surface_position_trend.py to be in the
same folder (reuses filename parsers and the default column-name mapping).
"""




def extract_position_timeseries(
    All_Data,
    surface_columns=None,   # dict of surfaces to include (excluding "Hand");
                           # defaults to all surfaces in DEFAULT_SURFACE_POSITION_COLUMNS
                           # except "Hand" itself
    hand_columns=None,      # dict {"x": col, "y": col, "z": col} for the hand's own
                           # position; defaults to DEFAULT_SURFACE_POSITION_COLUMNS["Hand"]
    segment_key="ForForceTime",
    parse_filename=default_parse_filename,
    time_col="time",
    filenames=None,          # optional list to restrict extraction to specific files
                           # (recommended for large datasets -- see note below)
):
    """
    For each touch segment, zero the time axis at the first sample (touch
    onset, t=0) and record the position of the hand and every contact
    surface at every timestamp during that touch.

    NOTE ON SIZE: this returns one row per (sample x surface x axis), so
    it can get large fast (e.g. 200 samples x 6 surfaces x 3 axes = 3600
    rows PER TRIAL). For big datasets, pass `filenames` to restrict this
    to a handful of trials you actually want to inspect, rather than
    extracting your entire dataset at once.

    Parameters
    ----------
    surface_columns, hand_columns : dict or None
        Same shape as in surface_position_trend.py. Defaults to
        DEFAULT_SURFACE_POSITION_COLUMNS.
    filenames : list[str] or None
        If given, only these files are processed (useful to keep the
        output small when you just want a few example trials).

    Returns
    -------
    pd.DataFrame
        One row per (trial segment, timestamp, surface, axis):
            filename, tester, material_trial, segment_index,
            time, surface, axis, value
        `time` is zeroed at touch onset (t=0 is the first sample).
    """
    if surface_columns is None:
        surface_columns = {
            k: v for k, v in DEFAULT_SURFACE_POSITION_COLUMNS.items() if k != "Hand"
        }
    if hand_columns is None:
        hand_columns = DEFAULT_SURFACE_POSITION_COLUMNS["Hand"]

    all_entities = dict(surface_columns)
    all_entities["Hand"] = hand_columns

    rows = []
    missing_cols_seen = set()

    items = All_Data.items() if filenames is None else (
        (f, All_Data[f]) for f in filenames if f in All_Data
    )

    for filename, data in items:
        segments = data.get(segment_key, [])
        if not segments:
            continue

        tester, material_trial = parse_filename(filename)

        for seg_idx, seg in enumerate(segments):
            if seg.empty or time_col not in seg.columns:
                continue

            t = seg[time_col].to_numpy(dtype=float)
            t0 = t - t[0]  # zero at touch onset

            for surface, axis_cols in all_entities.items():
                for axis, col in axis_cols.items():
                    if col not in seg.columns:
                        missing_cols_seen.add(col)
                        continue

                    values = seg[col].to_numpy(dtype=float)
                    for time_val, v in zip(t0, values):
                        rows.append({
                            "filename": filename,
                            "tester": tester,
                            "material_trial": material_trial,
                            "segment_index": seg_idx,
                            "time": time_val,
                            "surface": surface,
                            "axis": axis,
                            "value": v,
                        })

    if missing_cols_seen:
        print(f"Note: these columns were not found in any segment and were skipped: {sorted(missing_cols_seen)}")

    if not rows:
        raise ValueError(
            "No position time-series data collected. Check that surface_columns/"
            f"hand_columns match your actual CSV headers, and that All_Data[...][{segment_key!r}] has data."
        )

    return pd.DataFrame(rows)


def plot_position_timeseries(
    timeseries_df,
    filename,
    segment_index=0,
    axis_order=("x", "y", "z"),
    surface_order=None,     # e.g. ["Hand","Thumb","Index","UpperPalm","ThumbPalm","SidePalm"]
    ncols=3,
    figsize=(14, 5),
    save_path=None,
):
    """
    Plot ONE specific trial's position-over-time trace: one subplot per
    axis (x, y, z), each showing the hand's line plus every contact
    surface's line over time (zeroed at touch onset).

    Parameters
    ----------
    timeseries_df : pd.DataFrame
        Output of extract_position_timeseries().
    filename, segment_index : str, int
        Which trial (and which touch segment within that trial's file)
        to plot.

    Returns
    -------
    pd.DataFrame
        The subset of timeseries_df actually plotted.
    """
    sub_trial = timeseries_df[
        (timeseries_df["filename"] == filename)
        & (timeseries_df["segment_index"] == segment_index)
    ]
    if sub_trial.empty:
        raise ValueError(f"No data found for filename={filename!r}, segment_index={segment_index}.")

    surfaces = surface_order if surface_order is not None else sorted(sub_trial["surface"].unique())
    axes_list = [a for a in axis_order if a in sub_trial["axis"].unique()]

    n = len(axes_list)
    nrows = int(np.ceil(n / ncols))
    fig, subplot_axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)
    subplot_axes = subplot_axes.reshape(-1)

    for ax, axis_name in zip(subplot_axes, axes_list):
        axis_sub = sub_trial[sub_trial["axis"] == axis_name]
        for surface in surfaces:
            surf_sub = axis_sub[axis_sub["surface"] == surface].sort_values("time")
            if surf_sub.empty:
                continue
            style = dict(linewidth=2.5, linestyle="--") if surface == "Hand" else dict(linewidth=1.3)
            ax.plot(surf_sub["time"], surf_sub["value"], label=surface, **style)

        ax.set_title(f"Axis: {axis_name}", fontsize=10)
        ax.set_xlabel("Time from touch onset (s)")
        ax.set_ylabel("Position (mm)")
        ax.legend(fontsize=7)
        ax.grid(alpha=0.3)

    for ax in subplot_axes[n:]:
        ax.axis("off")

    tester = sub_trial["tester"].iloc[0]
    material_trial = sub_trial["material_trial"].iloc[0]
    fig.suptitle(f"Position over Time — {tester} / {material_trial} (seg {segment_index})")
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=200, bbox_inches="tight")

    plt.show()

    return sub_trial


def plot_position_timeseries_examples(
    timeseries_df,
    n_examples=4,
    axis="x",
    surface_order=None,
    random_state=0,
    ncols=2,
    figsize=(13, 8),
    save_path=None,
):
    """
    Diagnostic grid: sample a handful of (filename, segment_index) trials
    from timeseries_df and plot each one's position-over-time trace for a
    SINGLE chosen axis, hand + every surface overlaid -- useful for
    quickly scanning several trials at once (e.g. to see whether contact
    surfaces consistently lag or lead the hand's own movement).

    Parameters
    ----------
    axis : str
        Which single axis to plot (e.g. "x", "y", or "z"). Use
        plot_position_timeseries for a specific trial's full x/y/z view.
    """
    trial_keys = (
        timeseries_df[["filename", "segment_index"]]
        .drop_duplicates()
        .sample(frac=1, random_state=random_state)
    )
    trial_keys = trial_keys.head(n_examples)

    n = len(trial_keys)
    nrows = int(np.ceil(n / ncols))
    fig, subplot_axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)
    subplot_axes = subplot_axes.reshape(-1)

    for ax, (_, row) in zip(subplot_axes, trial_keys.iterrows()):
        sub_trial = timeseries_df[
            (timeseries_df["filename"] == row["filename"])
            & (timeseries_df["segment_index"] == row["segment_index"])
            & (timeseries_df["axis"] == axis)
        ]
        if sub_trial.empty:
            ax.axis("off")
            continue

        surfaces = surface_order if surface_order is not None else sorted(sub_trial["surface"].unique())
        for surface in surfaces:
            surf_sub = sub_trial[sub_trial["surface"] == surface].sort_values("time")
            if surf_sub.empty:
                continue
            style = dict(linewidth=2.5, linestyle="--") if surface == "Hand" else dict(linewidth=1.3)
            ax.plot(surf_sub["time"], surf_sub["value"], label=surface, **style)

        tester = sub_trial["tester"].iloc[0]
        material_trial = sub_trial["material_trial"].iloc[0]
        ax.set_title(f"{tester} / {material_trial} (seg {row['segment_index']})", fontsize=9)
        ax.set_xlabel("Time from touch onset (s)")
        ax.set_ylabel(f"{axis} Position (mm)")
        ax.legend(fontsize=6)
        ax.grid(alpha=0.3)

    for ax in subplot_axes[n:]:
        ax.axis("off")

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=200, bbox_inches="tight")

    plt.show()


# ---------------------------------------------------------------------
# Example usage:
#
# from position_timeseries import (
#     extract_position_timeseries, plot_position_timeseries,
#     plot_position_timeseries_examples,
# )
# from contact_heatmap import parse_filename_tester_material_trial
#
# # Restrict to a few files first if your dataset is large!
# timeseries_df = extract_position_timeseries(
#     All_Data,
#     segment_key="ForForceTime",
#     parse_filename=parse_filename_tester_material_trial,
#     filenames=["AoFoam1.csv", "AoWood1.csv"],  # or None for everything
# )
#
# # Full x/y/z view of one specific trial
# plot_position_timeseries(
#     timeseries_df,
#     filename="AoFoam1.csv",
#     segment_index=0,
#     surface_order=["Hand","Thumb","Index","UpperPalm","ThumbPalm","SidePalm"],
#     save_path="outputs/position_timeseries_AoFoam1.png",
# )
#
# # Quick scan of several trials, one axis at a time
# plot_position_timeseries_examples(
#     timeseries_df,
#     n_examples=4,
#     axis="x",
#     surface_order=["Hand","Thumb","Index","UpperPalm","ThumbPalm","SidePalm"],
#     save_path="outputs/position_timeseries_examples.png",
# )
# ---------------------------------------------------------------------