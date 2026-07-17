#!/usr/bin/env python3
"""Regenerate the repository figures and verify headline data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mplconfig"))
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import matplotlib.patheffects as path_effects  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402


DATA = ROOT / "data"
FIGURES = ROOT / "figures"


def validate_checksums() -> None:
    manifest = DATA / "SHA256SUMS"
    for line in manifest.read_text().splitlines():
        expected, relative_path = line.split(maxsplit=1)
        payload = (ROOT / relative_path).read_bytes()
        actual = hashlib.sha256(payload).hexdigest()
        assert actual == expected, relative_path


def load_csv() -> list[dict[str, float | int | str]]:
    with (DATA / "dvlt_k_sweep.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {
            "K": int(row["K"]),
            "depth_absrel": float(row["depth_absrel"]),
            "depth_delta1": float(row["depth_delta1"]),
            "pose_auc30": float(row["pose_auc30"]),
            "range": row["range"],
        }
        for row in rows
    ]


def load_summary() -> dict:
    return json.loads((DATA / "t36_sequence_summary.json").read_text())


def load_set_filter_results() -> tuple[dict, dict, dict, dict]:
    geometry = json.loads((DATA / "set_relative_filter_geometry.json").read_text())
    cascade = json.loads((DATA / "iterative_filter_cascade.json").read_text())
    subset_law = json.loads((DATA / "distractor_subset_law.json").read_text())
    projectivity = json.loads((DATA / "shared_output_projectivity.json").read_text())
    return geometry, cascade, subset_law, projectivity


def load_qualitative_results() -> tuple[dict, dict[str, np.ndarray]]:
    metadata = json.loads((DATA / "qualitative_forest2.json").read_text())
    with np.load(DATA / "qualitative_forest2.npz", allow_pickle=False) as packet:
        arrays = {name: packet[name] for name in packet.files}
    return metadata, arrays


def validate(rows: list[dict], summary: dict) -> None:
    assert [row["K"] for row in rows] == [8, 12, 16, 20, 24, 32, 48, 64]
    by_k = {row["K"]: row for row in rows}
    assert math.isclose(by_k[16]["depth_absrel"], 0.018220653757452965)
    assert math.isclose(by_k[64]["depth_absrel"], 0.3126002848148346)
    assert math.isclose(by_k[64]["pose_auc30"], 0.02076348289847374)
    assert by_k[64]["depth_absrel"] / by_k[16]["depth_absrel"] > 17.0

    raw_path = DATA / "raw" / "dvlt_r1_r2_r3_summary.json"
    if raw_path.exists():
        raw = json.loads(raw_path.read_text())
        raw_k = raw["r3"]["flat_metrics_by_k"]
        for row in rows:
            source = raw_k[str(row["K"])]
            assert math.isclose(row["depth_absrel"], source["eth3d.depth.AbsRel"])
            assert math.isclose(row["depth_delta1"], source["eth3d.depth.Delta1"])
            assert math.isclose(row["pose_auc30"], source["eth3d.pose.Auc_30"])
        assert raw["r3"]["degradation_start_k_vs_explicit_K16"] == 32
        assert raw["r2"]["divergent_channel_count"] == 567

    ceiling = summary["oracle_action_ceiling"]["all"]
    assert ceiling["n"] == 24
    assert ceiling["positive"] == 24
    assert ceiling["best_action_counts"] == {"KEEP": 0, "REFINE": 3, "REPAIR": 21}
    assert summary["hard_refusal_attempt_level"] == {
        "a1_external_tracker": 0.575,
        "a2_vggt_track_head": 0.875,
    }


def validate_set_filter_results(
    geometry: dict, cascade: dict, subset_law: dict, projectivity: dict
) -> None:
    assert geometry["status"] == "complete"
    assert geometry["scene_count"] == 4
    assert geometry["aggregate"]["exact_extension_reversal_scene_count"] == 4
    assert geometry["aggregate"]["normalization_only_reversal_scene_count"] == 4
    assert geometry["aggregate"]["all_valid_geometry_harmed_scene_count"] == 4
    assert math.isclose(geometry["aggregate"]["mean_filtering_effect_differential"], 0.12626516878605087)
    assert cascade["status"] == "complete"
    assert cascade["chain_count"] == 8
    assert cascade["aggregate"]["non_idempotent_chain_count"] == 8
    assert cascade["aggregate"]["connector_eventually_rejected_chain_count"] == 8
    assert cascade["aggregate"]["final_survivor_count_range"] == [2, 3]
    assert subset_law["status"] == "complete"
    assert subset_law["design"]["total_forward_passes"] == 64
    assert subset_law["cross_scene"]["actual_rescue_condition_count"] == 44
    assert subset_law["cross_scene"]["calibration_anchor_rescue_condition_count"] == 44
    assert subset_law["cross_scene"]["valid_only_calibration_rescue_condition_count"] == 0
    assert subset_law["cross_scene"]["first_rescue_counts"] == {
        "gascola_P003": 1,
        "gascola_P005": 1,
        "hospital_P000": 1,
        "hospital_P003": 2,
    }
    assert math.isclose(
        subset_law["cross_scene"]["mean_count_explained_score_variance"],
        0.9295813233800554,
    )
    assert projectivity["status"] == "complete"
    assert projectivity["design"]["forward_count"] == 16
    projectivity_summary = projectivity["summary"]
    assert projectivity_summary["score_control_passed_scene_count"] == 4
    assert projectivity_summary["distractor_accuracy_worsened_scene_count"] == 4
    assert projectivity_summary["redundant_accuracy_worsened_scene_count"] == 1
    assert projectivity_summary["distractor_shift_exceeds_redundant_scene_count"] == 4
    assert projectivity_summary["distractor_extension_shift_exceeds_core_scene_count"] == 4
    assert math.isclose(
        projectivity_summary["median_distractor_minus_redundant_relative_error_effect"],
        0.34326083207841385,
    )


def validate_qualitative_results(metadata: dict, packet: dict[str, np.ndarray]) -> None:
    assert metadata["status"] == "complete"
    assert metadata["scene"] == "gascola_P005"
    assert metadata["score_threshold"] == 0.4
    assert packet["mixed_thumbnails"].shape == (12, 168, 224, 3)
    assert packet["same_scene_thumbnails"].shape == (12, 168, 224, 3)
    assert packet["remote_rgb"].shape[:2] == packet["distractor_shift_percent"].shape
    assert packet["remote_rgb"].shape[:2] == packet["redundant_shift_percent"].shape
    mixed = metadata["conditions"]["distractor_context"]
    same_scene = metadata["conditions"]["redundant_context"]
    assert sum(item["rejected"] for item in mixed[:8]) == 0
    assert sum(item["rejected"] for item in mixed[8:]) == 4
    assert [item["rejected"] for item in same_scene[6:8]] == [True, True]
    assert sum(item["rejected"] for item in same_scene) == 2
    for condition, array_name in (
        ("distractor_context", "distractor_shift_percent"),
        ("redundant_context", "redundant_shift_percent"),
    ):
        observed = float(np.nanmedian(packet[array_name]))
        expected = metadata["point_shift_percent_of_camera_diameter"][condition][
            "median_percent"
        ]
        assert math.isclose(observed, expected, rel_tol=1.0e-6)


def style() -> None:
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 140,
            "savefig.dpi": 220,
        }
    )


def japanese_style() -> None:
    available_fonts = {font.name for font in font_manager.fontManager.ttflist}
    font_family = next(
        (
            name
            for name in ("Hiragino Sans", "Noto Sans CJK JP", "DejaVu Sans")
            if name in available_fonts
        ),
        "DejaVu Sans",
    )
    plt.rcParams.update(
        {
            "font.family": font_family,
            "axes.unicode_minus": False,
        }
    )


def _box(ax, x: float, y: float, w: float, h: float, text: str, color: str, *, fontsize: float = 10) -> None:
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.015",
        linewidth=1.3,
        edgecolor="#3d3d3d",
        facecolor=color,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize)


def _arrow(ax, start: tuple[float, float], end: tuple[float, float]) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=1.4,
            color="#4a4a4a",
        )
    )


def _result_table(
    ax,
    row_labels: list[str],
    column_labels: list[str],
    texts: list[list[str]],
    colors: list[list[str]],
    title: str,
) -> None:
    row_count = len(row_labels)
    column_count = len(column_labels)
    ax.set_xlim(-1.05, column_count)
    ax.set_ylim(-0.2, row_count + 0.72)
    ax.axis("off")
    ax.set_title(title, pad=12, fontweight="bold")
    for column, label in enumerate(column_labels):
        ax.text(
            column + 0.5,
            row_count + 0.34,
            label,
            ha="center",
            va="center",
            fontsize=9.5,
            fontweight="bold",
        )
    for row, label in enumerate(row_labels):
        y = row_count - row - 1
        ax.text(-0.08, y + 0.5, label, ha="right", va="center", fontsize=10)
        for column in range(column_count):
            ax.add_patch(
                Rectangle(
                    (column + 0.03, y + 0.04),
                    0.94,
                    0.92,
                    facecolor=colors[row][column],
                    edgecolor="white",
                    linewidth=2,
                )
            )
            ax.text(
                column + 0.5,
                y + 0.5,
                texts[row][column],
                ha="center",
                va="center",
                fontsize=10,
                fontweight="bold",
                color="#222222",
            )


def plot_filter_qualitative(metadata: dict, packet: dict[str, np.ndarray]) -> None:
    conditions = (
        ("distractor_context", "mixed_thumbnails"),
        ("redundant_context", "same_scene_thumbnails"),
    )
    row_labels = (
        "A  別scene画像を4枚追加\n別scene 4/4を除外，正しい8/8を保持",
        "B  同じsceneの近傍画像を4枚追加\n正しい遠方画像2枚を誤って除外",
    )
    fig = plt.figure(figsize=(17.2, 6.0))
    grid = fig.add_gridspec(
        3,
        12,
        height_ratios=(0.23, 1.0, 1.0),
        left=0.12,
        right=0.99,
        top=0.86,
        bottom=0.11,
        hspace=0.34,
        wspace=0.055,
    )
    header = fig.add_subplot(grid[0, :])
    header.set_xlim(0, 12)
    header.set_ylim(0, 1)
    header.axis("off")
    groups = (
        (0, 5, "基準画像と大きく重なる5枚", "#DCEAF7"),
        (5, 6, "両側に\n重なる1枚", "#FBE3C2"),
        (6, 8, "基準側とは直接ほぼ重ならない正しい2枚", "#DDF1DF"),
        (8, 12, "比較する4枚だけを変更", "#EEEEEE"),
    )
    for start, stop, label, color in groups:
        header.add_patch(
            Rectangle(
                (start + 0.04, 0.04),
                stop - start - 0.08,
                0.92,
                facecolor=color,
                edgecolor="white",
                linewidth=2,
            )
        )
        header.text((start + stop) / 2, 0.5, label, ha="center", va="center", fontsize=9)

    for row_index, ((condition, array_name), row_label) in enumerate(
        zip(conditions, row_labels)
    ):
        decisions = metadata["conditions"][condition]
        for column in range(12):
            axis = fig.add_subplot(grid[row_index + 1, column])
            axis.imshow(packet[array_name][column])
            axis.set_xticks([])
            axis.set_yticks([])
            rejected = bool(decisions[column]["rejected"])
            border = "#D55E00" if rejected else "#009E73"
            for spine in axis.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(3.0)
                spine.set_color(border)
            if rejected:
                mark = axis.text(
                    0.5,
                    0.52,
                    "×",
                    transform=axis.transAxes,
                    ha="center",
                    va="center",
                    color="#D55E00",
                    fontsize=39,
                    fontweight="bold",
                )
                mark.set_path_effects(
                    [path_effects.Stroke(linewidth=4.0, foreground="white"), path_effects.Normal()]
                )
            axis.text(
                0.5,
                -0.08,
                f"score {decisions[column]['score']:.2f}",
                transform=axis.transAxes,
                ha="center",
                va="top",
                fontsize=7.3,
                color="#D55E00" if rejected else "#333333",
            )
            if column == 0:
                axis.text(
                    -0.22,
                    0.5,
                    row_label,
                    transform=axis.transAxes,
                    ha="right",
                    va="center",
                    fontsize=9.5,
                    fontweight="bold",
                )
    fig.suptitle(
        "同じ正しい8枚でも，残り4枚を変えると画像除外の判定が反転する",
        y=0.97,
        fontsize=15,
        fontweight="bold",
    )
    fig.text(
        0.56,
        0.025,
        "緑枠＝保持，赤枠と×＝棄却．公開設定ではscoreが0.4未満の画像を除外する．",
        ha="center",
        fontsize=9.5,
    )
    fig.savefig(FIGURES / "filter_qualitative_example.png", bbox_inches="tight")
    plt.close(fig)


def plot_projectivity_qualitative(metadata: dict, packet: dict[str, np.ndarray]) -> None:
    distractor = packet["distractor_shift_percent"]
    redundant = packet["redundant_shift_percent"]
    limit = 10.0
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 4.4), constrained_layout=True)
    axes[0].imshow(packet["remote_rgb"])
    axes[0].set_title("共通する同じ遠方画像")
    image = axes[1].imshow(distractor, cmap="magma", vmin=0.0, vmax=limit)
    axes[1].set_title(
        "別scene画像4枚を追加\npoint map変位の中央値 3.28%",
        color="#A33B00",
    )
    axes[2].imshow(redundant, cmap="magma", vmin=0.0, vmax=limit)
    axes[2].set_title(
        "同じsceneの近傍画像4枚を追加\npoint map変位の中央値 1.51%",
        color="#005A8D",
    )
    for axis in axes:
        axis.set_xticks([])
        axis.set_yticks([])
        for spine in axis.spines.values():
            spine.set_visible(False)
    colorbar = fig.colorbar(image, ax=axes[1:], fraction=0.035, pad=0.025)
    colorbar.set_label("同じpixelの予測3D点の変位 / camera撮影範囲の直径（%）\n10%より大きい値は同じ色で表示")
    fig.suptitle(
        "除外前の同じVGGT推論では，正しい画像の3D出力もcontextで変わる",
        fontsize=14,
        fontweight="bold",
    )
    fig.savefig(FIGURES / "projectivity_qualitative_example.png", bbox_inches="tight")
    plt.close(fig)


def plot_experiment_design() -> None:
    fig, ax = plt.subplots(figsize=(12.0, 6.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.5, 0.96, "Two tests ask what actually limits feed-forward 3D", ha="center", va="top", fontsize=15)
    ax.text(0.03, 0.87, "TEST 1  Does the source of image correspondences change the final pose?", weight="bold", fontsize=11.5)
    ax.text(
        0.97,
        0.80,
        "Hold fixed: images, VGGT estimate, and BA solver   |   Change: correspondence source and coverage",
        ha="right",
        fontsize=9.5,
        color="#555555",
    )

    _box(ax, 0.02, 0.56, 0.12, 0.16, "Multi-view\nRGB", "#f1f1f1")
    _box(ax, 0.19, 0.56, 0.17, 0.16, "Fixed VGGT estimate\ncameras + depth", "#dce9f8")
    _box(
        ax,
        0.41,
        0.51,
        0.20,
        0.26,
        "Change image correspondences\n\nExternal tracker\nVGGT track head\nGround-truth correspondences",
        "#d9f0ed",
        fontsize=9.2,
    )
    _box(ax, 0.66, 0.56, 0.14, 0.16, "Same bundle-\nadjustment solver", "#eee3f6")
    _box(ax, 0.85, 0.56, 0.12, 0.16, "Pose score\nor invalid BA result", "#f6dddd", fontsize=9.2)
    _arrow(ax, (0.14, 0.64), (0.19, 0.64))
    _arrow(ax, (0.36, 0.64), (0.41, 0.64))
    _arrow(ax, (0.61, 0.64), (0.66, 0.64))
    _arrow(ax, (0.80, 0.64), (0.85, 0.64))

    ax.text(
        0.5,
        0.40,
        "Ground-truth correspondences define an upper bound; they are not a deployable method.",
        ha="center",
        fontsize=10.5,
        color="#333333",
    )

    ax.plot([0.03, 0.97], [0.34, 0.34], color="#cccccc", linewidth=1)
    ax.text(0.03, 0.27, "TEST 2  Does one Déjà View checkpoint keep improving as we add iterations?", weight="bold", fontsize=11.5)
    _box(ax, 0.10, 0.07, 0.14, 0.12, "Multi-view\nRGB", "#f1f1f1")
    _box(ax, 0.32, 0.07, 0.20, 0.12, "Déjà View\nshared block repeated", "#dce9f8")
    _box(ax, 0.60, 0.07, 0.16, 0.12, "8, 12, 16, ...\n48, 64 applications", "#f9e7b3")
    _box(ax, 0.84, 0.07, 0.12, 0.12, "Pose + depth\nquality", "#f6dddd")
    _arrow(ax, (0.24, 0.13), (0.32, 0.13))
    _arrow(ax, (0.52, 0.13), (0.60, 0.13))
    _arrow(ax, (0.76, 0.13), (0.84, 0.13))

    fig.tight_layout()
    fig.savefig(FIGURES / "experiment_design.png", bbox_inches="tight")
    plt.close(fig)


def plot_dvlt(rows: list[dict]) -> None:
    ks = [row["K"] for row in rows]
    pose = [row["pose_auc30"] for row in rows]
    absrel = [row["depth_absrel"] for row in rows]

    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.2))
    for ax in axes:
        ax.axvspan(8, 16, color="#dce9f8", alpha=0.85, label="trained step-count range")
        ax.axvline(16, color="#4c78a8", linestyle="--", linewidth=1)
        ax.axvline(32, color="#e45756", linestyle=":", linewidth=1.4)
        ax.set_xticks(ks)
        ax.grid(axis="y", color="#dddddd", linewidth=0.7)

    axes[0].plot(ks, pose, marker="o", color="#4c78a8", linewidth=2.2)
    axes[0].set_title("Long out-of-range iteration degrades pose")
    axes[0].set_xlabel("Number of recurrent applications")
    axes[0].set_ylabel("ETH3D Pose AUC@30 (higher is better)")
    axes[0].set_ylim(0, 1.03)
    axes[0].annotate("0.954", (16, pose[2]), xytext=(18, 0.84), arrowprops={"arrowstyle": "->"})
    axes[0].text(33.3, 0.69, "first tested count\nbelow 16-step baseline", color="#b33939", fontsize=8.2)
    axes[0].annotate("0.021", (64, pose[-1]), xytext=(49, 0.22), arrowprops={"arrowstyle": "->"})

    axes[1].plot(ks, absrel, marker="o", color="#e45756", linewidth=2.2)
    axes[1].set_yscale("log")
    axes[1].set_title("Depth error is ~17.2x worse at 64 vs 16 applications")
    axes[1].set_xlabel("Number of recurrent applications")
    axes[1].set_ylabel("ETH3D Depth AbsRel (lower is better, log scale)")
    axes[1].annotate("0.018", (16, absrel[2]), xytext=(21, 0.027), arrowprops={"arrowstyle": "->"})
    axes[1].annotate("0.313", (64, absrel[-1]), xytext=(45, 0.16), arrowprops={"arrowstyle": "->"})
    axes[1].legend(frameon=False, loc="upper left")

    fig.suptitle("More iterations eventually break one Déjà View checkpoint", y=1.03, fontsize=14)
    fig.tight_layout()
    fig.savefig(FIGURES / "dvlt_k_sweep.png", bbox_inches="tight")
    plt.close(fig)


def plot_action_ceiling(summary: dict) -> None:
    ceiling = summary["oracle_action_ceiling"]
    groups = ["all", "easy", "hard"]
    medians = [ceiling[group]["median_gain_auc30"] for group in groups]
    actions = ceiling["all"]["best_action_counts"]

    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.2), gridspec_kw={"width_ratios": [1.2, 1]})
    colors = ["#4c78a8", "#72b7b2", "#f2cf5b"]
    bars = axes[0].bar(["All (n=24)", "Standard-view (n=15)", "Difficult-view (n=9)"], medians, color=colors)
    axes[0].set_ylabel("Median gain of the best available intervention")
    axes[0].set_title("Best-of-three pose gain is positive")
    axes[0].set_ylim(0, 0.061)
    axes[0].grid(axis="y", color="#dddddd", linewidth=0.7)
    axes[0].bar_label(bars, fmt="%.3f", padding=3)

    action_keys = ["KEEP", "REFINE", "REPAIR"]
    names = ["Keep\nVGGT", "BA with\nlearned tracks", "BA with ground-\ntruth tracks"]
    counts = [actions[name] for name in action_keys]
    bars = axes[1].bar(names, counts, color=["#9d9d9d", "#f58518", "#54a24b"])
    axes[1].set_ylabel("Sequences where intervention gives the largest gain")
    axes[1].set_title("Which choice gives the best pose?")
    axes[1].set_ylim(0, 24)
    axes[1].bar_label(bars, padding=3)

    fig.suptitle("Upper bound on sequences with all three results available", y=1.03, fontsize=14)
    fig.tight_layout()
    fig.savefig(FIGURES / "oracle_action_ceiling.png", bbox_inches="tight")
    plt.close(fig)


def plot_correspondence_diagnostics(summary: dict) -> None:
    gaps = summary["easy_oracle_gap"]
    refusals = summary["hard_refusal_attempt_level"]

    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.2))
    labels = ["External tracker", "VGGT track head"]

    gap_values = [gaps["a1_external_tracker"]["median_auc30"], gaps["a2_vggt_track_head"]["median_auc30"]]
    bars = axes[0].bar(labels, gap_values, color=["#72b7b2", "#4c78a8"])
    axes[0].set_ylabel("Median Pose AUC@30 gap to ground truth")
    axes[0].set_title("Standard-view data: a small gap remains")
    axes[0].set_ylim(0, 0.04)
    axes[0].bar_label(bars, fmt="%.4f", padding=3)

    refusal_values = [refusals["a1_external_tracker"], refusals["a2_vggt_track_head"]]
    bars = axes[1].bar(labels, refusal_values, color=["#f2cf5b", "#e45756"])
    axes[1].set_ylabel("Runs without an accepted BA result")
    axes[1].set_title("Difficult-view data: BA often fails quality checks")
    axes[1].set_ylim(0, 1.0)
    axes[1].bar_label(bars, labels=[f"{100*x:.1f}%" for x in refusal_values], padding=3)

    fig.suptitle("Learned correspondences leave a gap to ground truth", y=1.03, fontsize=14)
    fig.tight_layout()
    fig.savefig(FIGURES / "correspondence_diagnostics.png", bbox_inches="tight")
    plt.close(fig)


def plot_constraint_output_hypothesis() -> None:
    fig, ax = plt.subplots(figsize=(11.8, 6.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.5,
        0.96,
        "What should a feed-forward 3D model predict?",
        ha="center",
        va="top",
        fontsize=16,
        weight="bold",
    )

    ax.text(0.04, 0.84, "CURRENT CONTRACT", fontsize=11.5, weight="bold", color="#315a86")
    _box(ax, 0.04, 0.61, 0.14, 0.15, "Multi-view\nRGB", "#f1f1f1")
    _box(ax, 0.25, 0.61, 0.18, 0.15, "Feed-forward\n3D model", "#dce9f8")
    _box(ax, 0.50, 0.56, 0.20, 0.25, "Coordinate-bearing outputs\n\ncameras\ndepth / pointmaps\ntracks", "#f9e7b3", fontsize=9.6)
    _box(ax, 0.78, 0.61, 0.17, 0.15, "Optional global\noptimization", "#eee3f6")
    _arrow(ax, (0.18, 0.685), (0.25, 0.685))
    _arrow(ax, (0.43, 0.685), (0.50, 0.685))
    _arrow(ax, (0.70, 0.685), (0.78, 0.685))

    ax.plot([0.04, 0.96], [0.49, 0.49], color="#cfcfcf", linewidth=1)

    ax.text(0.04, 0.42, "HYPOTHESIZED CONTRACT", fontsize=11.5, weight="bold", color="#27786f")
    _box(ax, 0.04, 0.18, 0.14, 0.15, "Multi-view\nRGB", "#f1f1f1")
    _box(ax, 0.25, 0.18, 0.18, 0.15, "Same-capacity\n3D model", "#d9f0ed")
    _box(ax, 0.50, 0.13, 0.20, 0.25, "Only local geometric\nconstraints\n\nno camera, depth,\npointmap, or track output", "#cce8e4", fontsize=9.5)
    _box(ax, 0.78, 0.18, 0.17, 0.15, "One shared\nnullspace readout", "#d8efe2")
    _arrow(ax, (0.18, 0.255), (0.25, 0.255))
    _arrow(ax, (0.43, 0.255), (0.50, 0.255))
    _arrow(ax, (0.70, 0.255), (0.78, 0.255))

    ax.text(
        0.5,
        0.045,
        "Open question: does the output contract itself improve ordinary camera and 3D reconstruction?",
        ha="center",
        fontsize=10.5,
        color="#333333",
    )

    fig.tight_layout()
    fig.savefig(FIGURES / "constraint_output_hypothesis.png", bbox_inches="tight")
    plt.close(fig)


def plot_constraint_matched_test() -> None:
    fig, ax = plt.subplots(figsize=(12.0, 6.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.5,
        0.96,
        "The first experiment must separate representation from extra privileges",
        ha="center",
        va="top",
        fontsize=15,
        weight="bold",
    )
    ax.text(
        0.5,
        0.885,
        "Hold fixed: backbone, image supports, supervision, solver rights, refinement, compute, and seeds",
        ha="center",
        fontsize=9.7,
        color="#555555",
    )

    labels = [
        ("Predict constraints\ndirectly", "#cce8e4"),
        ("Predict coordinates\nthen convert to the\nsame constraints", "#dce9f8"),
        ("Predict coordinates\nthen run same-support\nSfM", "#f9e7b3"),
        ("Predict constraints\nwith a matched learned\nreadout", "#eee3f6"),
    ]
    xs = [0.03, 0.275, 0.52, 0.765]
    for x, (label, color) in zip(xs, labels):
        _box(ax, x, 0.59, 0.205, 0.19, label, color, fontsize=9.6)
        _arrow(ax, (x + 0.1025, 0.59), (x + 0.1025, 0.47))
        _box(ax, x, 0.31, 0.205, 0.14, "Camera pose +\nobserved 3D quality\n(before / after refinement)", "#f3f3f3", fontsize=8.9)

    ax.plot([0.04, 0.96], [0.24, 0.24], color="#cfcfcf", linewidth=1)
    _box(ax, 0.055, 0.055, 0.26, 0.12, "ADVANCE\nDirect constraints win, and\nthe fixed readout is causal", "#d8efe2", fontsize=8.8)
    _box(ax, 0.37, 0.055, 0.26, 0.12, "PIVOT\nOnly conditioning or\npre-refinement consistency changes", "#fff1c9", fontsize=8.8)
    _box(ax, 0.685, 0.055, 0.26, 0.12, "KILL\nA matched coordinate arm\nmatches or wins", "#f6dddd", fontsize=8.8)

    fig.tight_layout()
    fig.savefig(FIGURES / "constraint_matched_test.png", bbox_inches="tight")
    plt.close(fig)


def plot_set_relative_filter_geometry(geometry: dict) -> None:
    rows = geometry["rows"]
    scene_labels = ("森林 1", "森林 2", "病院 1", "病院 2")
    columns = (
        "別scene画像を\n4枚追加",
        "同じsceneの近傍画像を\n4枚追加",
    )
    decision_texts = []
    decision_colors = []
    geometry_texts = []
    geometry_colors = []
    for row in rows:
        remote = [
            item
            for item in row["shared_source_views"]
            if item["role"] in {"extension_center", "extension"}
        ]
        mixed_score = float(np.mean([item["score_with_distractors"] for item in remote]))
        same_score = float(np.mean([item["score_all_valid"] for item in remote]))
        mixed_retained = sum(not item["rejected_with_distractors"] for item in remote)
        same_retained = sum(not item["rejected_all_valid"] for item in remote)
        decision_texts.append(
            [
                f"平均score {mixed_score:.2f}\n{mixed_retained}枚とも保持" if mixed_retained == 2 else f"平均score {mixed_score:.2f}\n2枚とも除外",
                f"平均score {same_score:.2f}\n{same_retained}枚とも保持" if same_retained == 2 else f"平均score {same_score:.2f}\n2枚とも除外",
            ]
        )
        decision_colors.append(
            ["#D8EFE2" if mixed_retained == 2 else "#F6D9D5", "#D8EFE2" if same_retained == 2 else "#F6D9D5"]
        )
        deltas = (
            100.0 * row["geometry"]["base_anchor_reference"]["filtering_delta"],
            100.0 * row["geometry"]["all_valid"]["filtering_delta"],
        )
        geometry_texts.append(
            [
                f"除外後 − 除外前\n{value:+.1f}ポイント（{'改善' if value > 0.5 else '悪化' if value < -0.5 else 'ほぼ不変'}）"
                for value in deltas
            ]
        )
        geometry_colors.append(
            ["#D8EFE2" if value > 0.5 else "#F6D9D5" if value < -0.5 else "#F8EDC8" for value in deltas]
        )

    fig, axis = plt.subplots(figsize=(7.4, 5.4), constrained_layout=True)
    _result_table(
        axis,
        list(scene_labels),
        list(columns),
        decision_texts,
        decision_colors,
        "最後の4枚だけを変えると，同じ遠方2画像の判定が反転した",
    )
    fig.text(
        0.57,
        0.025,
        "scoreが0.4未満の画像を除外する",
        ha="center",
        fontsize=10.5,
        color="#333333",
    )
    fig.savefig(FIGURES / "filter_decision_flip.png", bbox_inches="tight")
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(7.4, 5.4), constrained_layout=True)
    _result_table(
        axis,
        list(scene_labels),
        list(columns),
        geometry_texts,
        geometry_colors,
        "画像除外によって，遠方側の3D表面の再構成率がどう変わったか",
    )
    fig.text(
        0.57,
        0.025,
        "負の値ほど，除外によって未再構成の表面が増えた",
        ha="center",
        fontsize=10.5,
        color="#333333",
    )
    fig.savefig(FIGURES / "filter_geometry_effect.png", bbox_inches="tight")
    plt.close(fig)


def plot_iterative_filter_cascade(cascade: dict) -> None:
    chains = cascade["chains"]
    example = next(
        row
        for row in chains
        if row["scene"] == "gascola_P003" and row["condition"] == "base_anchor_reference"
    )
    assert [item["survivor_count"] for item in example["rounds"]] == [8, 6, 4, 2, 2]
    fig, axis = plt.subplots(figsize=(14.5, 4.2))
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")
    x_positions = (0.015, 0.225, 0.435, 0.645, 0.855)
    stage_texts = (
        "入力\n12枚",
        "1回目後\n8枚",
        "2回目後\n6枚",
        "3回目後\n4枚",
        "4回目後\n2枚で安定",
    )
    stage_colors = ("#EEEEEE", "#E2EEF7", "#F8E0DB", "#F8E0DB", "#F8E0DB")
    for x, text, color in zip(x_positions, stage_texts, stage_colors):
        _box(axis, x, 0.39, 0.13, 0.18, text, color, fontsize=11)
    arrow_labels = (
        ("別scene画像4枚\nを正しく除外", "#333333"),
        ("同じsceneの正しい画像2枚\nを誤って除外", "#B43C2D"),
        ("同じsceneの正しい画像2枚\nを誤って除外", "#B43C2D"),
        ("同じsceneの正しい画像2枚\nを誤って除外", "#B43C2D"),
    )
    for index, (label, color) in enumerate(arrow_labels):
        start = (x_positions[index] + 0.132, 0.48)
        end = (x_positions[index + 1] - 0.004, 0.48)
        _arrow(axis, start, end)
        axis.text(
            (start[0] + end[0]) / 2,
            0.63 if index != 3 else 0.65,
            label,
            ha="center",
            va="bottom",
            fontsize=8.7,
            color=color,
            fontweight="bold" if color != "#333333" else "normal",
        )
    axis.set_title(
        "1回目に別scene画像を除いた後も，正しい画像の除外が続いた\n（森林1の一例，左から右へ1回ずつ除外処理を適用）",
        fontsize=14,
        fontweight="bold",
        pad=18,
    )
    fig.savefig(FIGURES / "iterative_filter_example.png", bbox_inches="tight")
    plt.close(fig)

    scene_order = ("gascola_P003", "gascola_P005", "hospital_P000", "hospital_P003")
    scene_labels = {
        "gascola_P003": "森林 1",
        "gascola_P005": "森林 2",
        "hospital_P000": "病院 1",
        "hospital_P003": "病院 2",
    }
    condition_order = ("base_anchor_reference", "all_valid")
    condition_labels = (
        "別scene画像4枚を含む入力",
        "12枚すべて同じsceneの入力",
    )
    by_key = {(row["scene"], row["condition"]): row for row in chains}
    texts = []
    colors = []
    for scene in scene_order:
        scene_texts = []
        scene_colors = []
        for condition in condition_order:
            row = by_key[(scene, condition)]
            counts = [row["rounds"][0]["input_count"]]
            counts.extend(item["survivor_count"] for item in row["rounds"])
            scene_texts.append(" → ".join(str(value) for value in counts))
            scene_colors.append("#F8E0DB")
        texts.append(scene_texts)
        colors.append(scene_colors)

    fig, axis = plt.subplots(figsize=(9.2, 5.4), constrained_layout=True)
    _result_table(
        axis,
        [scene_labels[scene] for scene in scene_order],
        list(condition_labels),
        texts,
        colors,
        "8条件すべてで，2回目以降も残る画像が減り続けた",
    )
    fig.text(
        0.59,
        0.025,
        "数字は各回の処理後に残った画像枚数．末尾の同じ数字は，次の処理で変化しなかったことを表す",
        ha="center",
        fontsize=9.8,
        color="#333333",
    )
    fig.savefig(FIGURES / "iterative_filter_all_conditions.png", bbox_inches="tight")
    plt.close(fig)


def plot_distractor_subset_law(results: dict) -> None:
    scene_order = ("gascola_P003", "gascola_P005", "hospital_P000", "hospital_P003")
    scene_labels = {
        "gascola_P003": "森林 1",
        "gascola_P005": "森林 2",
        "hospital_P000": "病院 1",
        "hospital_P003": "病院 2",
    }
    texts = []
    colors = []
    for scene in scene_order:
        fractions = [
            results["scenes"][scene]["by_distractor_count"][str(count)][
                "both_retained_fraction"
            ]
            for count in range(5)
        ]
        texts.append([f"{100.0 * value:.0f}%" for value in fractions])
        colors.append(
            [
                "#D8EFE2" if value >= 0.999 else "#F8EDC8" if value > 0 else "#F6D9D5"
                for value in fractions
            ]
        )
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(13.8, 4.8),
        gridspec_kw={"width_ratios": (1.45, 0.8)},
        constrained_layout=True,
    )
    _result_table(
        axes[0],
        [scene_labels[scene] for scene in scene_order],
        [f"{count}枚" for count in range(5)],
        texts,
        colors,
        "遠方2画像をともに保持した組合せの割合",
    )
    axes[1].set_xlim(0, 1)
    axes[1].set_ylim(0, 1)
    axes[1].axis("off")
    _box(
        axes[1],
        0.08,
        0.66,
        0.84,
        0.20,
        "主効果は枚数\n別scene画像の枚数だけでscore変動の平均93%を説明",
        "#E2EEF7",
        fontsize=10.5,
    )
    _box(
        axes[1],
        0.08,
        0.39,
        0.84,
        0.20,
        "ただし画像の選び方も効く\n同じ枚数でも，保持する組合せと棄却する組合せが存在",
        "#FFF3D6",
        fontsize=10.5,
    )
    _box(
        axes[1],
        0.08,
        0.12,
        0.84,
        0.20,
        "scoreの尺度決めが必要\n救済した44条件は，再正規化だけで44→0条件へ消失",
        "#F6D9D5",
        fontsize=10.5,
    )
    fig.suptitle(
        "別scene画像が増えるほど正しい遠方画像は保持されやすいが，枚数だけでは決まらない",
        fontsize=14,
        fontweight="bold",
    )
    fig.savefig(FIGURES / "distractor_count_summary.png", bbox_inches="tight")
    plt.close(fig)


def plot_shared_output_projectivity(results: dict) -> None:
    labels = ("森林 1", "森林 2", "病院 1", "病院 2")
    rows = results["scenes"]
    error_texts = []
    error_colors = []
    role_texts = []
    role_colors = []
    for row in rows:
        error_values = (
            100.0 * row["point_error_relative_change"]["distractor_context"],
            100.0 * row["point_error_relative_change"]["redundant_context"],
        )
        error_texts.append(
            [
                f"{value:+.1f}%\n{'悪化' if value > 0 else '改善'}"
                for value in error_values
            ]
        )
        error_colors.append(
            ["#F6D9D5" if value > 0 else "#D8EFE2" for value in error_values]
        )
        comparison = row["comparisons_to_common_only"]["distractor_context"][
            "point_shift_fraction_of_camera_diameter"
        ]
        role_values = (100.0 * comparison["core"]["median"], 100.0 * comparison["extension"]["median"])
        role_texts.append([f"{value:.2f}%" for value in role_values])
        role_colors.append(["#E2EEF7", "#F4DCEB"])

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.0), constrained_layout=True)
    _result_table(
        axes[0],
        list(labels),
        ["別scene画像を\n4枚追加", "同じsceneの近傍画像を\n4枚追加"],
        error_texts,
        error_colors,
        "共通8画像のpoint map誤差の変化",
    )
    _result_table(
        axes[1],
        list(labels),
        ["基準画像と重なる\n5画像", "基準側と直接ほぼ\n重ならない2画像"],
        role_texts,
        role_colors,
        "別scene画像追加時の3D点の変位",
    )
    fig.suptitle(
        "別scene画像を正しく除外できても，除外前の正しい画像の3Dはすでに変化している",
        fontsize=14,
        fontweight="bold",
    )
    fig.savefig(FIGURES / "shared_output_context_summary.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate data and generated files")
    args = parser.parse_args()

    FIGURES.mkdir(parents=True, exist_ok=True)
    validate_checksums()
    rows = load_csv()
    summary = load_summary()
    set_filter_geometry, iterative_filter, subset_law, projectivity = load_set_filter_results()
    qualitative_metadata, qualitative_packet = load_qualitative_results()
    validate(rows, summary)
    validate_set_filter_results(
        set_filter_geometry, iterative_filter, subset_law, projectivity
    )
    validate_qualitative_results(qualitative_metadata, qualitative_packet)
    style()
    plot_experiment_design()
    plot_dvlt(rows)
    plot_action_ceiling(summary)
    plot_correspondence_diagnostics(summary)
    plot_constraint_output_hypothesis()
    plot_constraint_matched_test()
    japanese_style()
    plot_filter_qualitative(qualitative_metadata, qualitative_packet)
    plot_set_relative_filter_geometry(set_filter_geometry)
    plot_iterative_filter_cascade(iterative_filter)
    plot_distractor_subset_law(subset_law)
    plot_projectivity_qualitative(qualitative_metadata, qualitative_packet)
    plot_shared_output_projectivity(projectivity)

    if args.check:
        for name in (
            "experiment_design.png",
            "dvlt_k_sweep.png",
            "oracle_action_ceiling.png",
            "correspondence_diagnostics.png",
            "constraint_output_hypothesis.png",
            "constraint_matched_test.png",
            "filter_qualitative_example.png",
            "filter_decision_flip.png",
            "filter_geometry_effect.png",
            "iterative_filter_example.png",
            "iterative_filter_all_conditions.png",
            "distractor_count_summary.png",
            "projectivity_qualitative_example.png",
            "shared_output_context_summary.png",
        ):
            path = FIGURES / name
            assert path.exists() and path.stat().st_size > 10_000, path
        print("CHECK_OK: data, headline values, and figures are consistent")


if __name__ == "__main__":
    main()
