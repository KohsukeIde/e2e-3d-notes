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
from matplotlib.lines import Line2D  # noqa: E402
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


def load_one_world_results() -> tuple[dict, dict[str, np.ndarray]]:
    results = json.loads((DATA / "one_world_vggt.json").read_text())
    with np.load(DATA / "one_world_vggt_qualitative.npz", allow_pickle=False) as packet:
        arrays = {name: packet[name] for name in packet.files}
    return results, arrays


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


def validate_one_world_results(results: dict, packet: dict[str, np.ndarray]) -> None:
    assert results["status"] == "complete"
    protocol = results["protocol"]
    assert protocol["model"] == "facebook/VGGT-1B"
    assert protocol["model_forward_count"] == 48
    assert protocol["successful_forward_count"] == 48
    assert protocol["failed_forward_count"] == 0
    assert protocol["independent_scene_sequence_count"] == 4
    assert protocol["query_count"] == 48
    assert protocol["noise"]["maximum_mean_psnr_difference_between_paired_arms_db"] < 0.003
    assert protocol["noise"]["allowed_mean_psnr_difference_db"] == 0.05

    controls = results["known_answer_controls"]
    assert controls["overall_pass"] is True
    assert controls["synthetic_case_count"] == 51
    assert controls["maximum_primary_change_after_confidence_swap"] == 0.0
    assert controls["analytic_replacement_maximum_px_on_real_outputs"] == 0.0
    assert controls["minimum_detected_planted_offset_px_on_real_outputs"] > 32.0

    decision = results["preregistered_decision"]
    assert decision["label"] == "hypothesis_not_supported"
    assert decision["all_positive_depth_pairs"]["2"] == {
        "confidence_maintained_or_increased_scene_count_of_4": 4,
        "extra_mismatch_increase_scene_count_of_4": 2,
        "joint_preregistered_condition_passed": False,
    }
    assert decision["all_positive_depth_pairs"]["4"] == {
        "confidence_maintained_or_increased_scene_count_of_4": 3,
        "extra_mismatch_increase_scene_count_of_4": 2,
        "joint_preregistered_condition_passed": False,
    }
    assert decision["ordinary_metric_independent_pair_count_of_24"] == 0
    visible = results["visibility_loophole_audit"]["ground_truth_visible_pairs"]
    assert visible["2"]["extra_mismatch_increase_scene_count_of_4"] == 2
    assert visible["4"]["extra_mismatch_increase_scene_count_of_4"] == 2
    assert len(results["paired_acquisition_effects"]) == 24

    view_rows = results["view_composition_posthoc"]["scene_rows"]
    assert len(view_rows) == 4
    for row in view_rows:
        effects = row["four_positions_minus_two_positions"]
        assert effects["visible_extra_mismatch_px"]["positive_count_of_6"] == 6
        assert effects["ordinary_tracking_error_px"]["positive_count_of_6"] == 6
        assert effects["visible_tracking_confidence"]["positive_count_of_6"] == 0

    assert packet["rgb"].shape == (384, 512, 3)
    assert packet["points_xy"].shape == (4, 2)
    assert packet["point_names"].tolist() == [
        "tracking_head",
        "depth_and_camera",
        "direct_3d_point",
        "ground_truth",
    ]
    qualitative = results["qualitative"]
    assert qualitative["ground_truth_visible"] is True
    assert qualitative["all_four_positions_inside_selection_margin"] is True
    assert math.isclose(qualitative["selection_border_margin_fraction"], 0.05)
    assert math.isclose(
        qualitative["tracking_head_extra_mismatch_px_model_input"],
        7.318077697167545,
    )
    assert math.isclose(
        qualitative["tracking_head_extra_mismatch_px_original_image"],
        9.006110380237281,
    )
    width, height = qualitative["resized_image_size_wh"]
    margin = qualitative["selection_border_margin_fraction"]
    points = packet["points_xy"]
    assert np.all(points[:, 0] >= margin * width)
    assert np.all(points[:, 0] <= (1.0 - margin) * width)
    assert np.all(points[:, 1] >= margin * height)
    assert np.all(points[:, 1] <= (1.0 - margin) * height)


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
    score_groups = ([], [])
    geometry_groups = ([], [])
    for row in rows:
        remote = [
            item
            for item in row["shared_source_views"]
            if item["role"] in {"extension_center", "extension"}
        ]
        score_groups[0].append([item["score_with_distractors"] for item in remote])
        score_groups[1].append([item["score_all_valid"] for item in remote])
        geometry_groups[0].append(
            100.0 * row["geometry"]["base_anchor_reference"]["filtering_delta"]
        )
        geometry_groups[1].append(
            100.0 * row["geometry"]["all_valid"]["filtering_delta"]
        )

    fig, axis = plt.subplots(figsize=(10.6, 5.5), constrained_layout=True)
    score_titles = (
        "別scene画像を4枚追加",
        "同じsceneの近傍画像を4枚追加",
    )
    score_colors = ("#3B78A8", "#C65D3B")
    y = np.arange(len(scene_labels))
    offsets = (-0.16, 0.16)
    for groups, title, color, offset in zip(score_groups, score_titles, score_colors, offsets):
        for index, values in enumerate(groups):
            low, high = min(values), max(values)
            mean = float(np.mean(values))
            position = index + offset
            axis.hlines(position, low, high, color=color, linewidth=4, alpha=0.75)
            axis.scatter(values, [position, position], s=46, facecolor="white", edgecolor=color, linewidth=1.8, zorder=3)
            axis.scatter(mean, position, s=70, marker="D", color=color, edgecolor="white", linewidth=0.8, zorder=4)
            axis.text(mean + 0.022, position, f"{mean:.2f}", va="center", fontsize=9.2, fontweight="bold")
        axis.plot([], [], color=color, linewidth=4, marker="D", label=title)
    axis.axvspan(-0.02, 0.4, color="#C94C3C", alpha=0.045)
    axis.axvspan(0.4, 0.70, color="#3F8F67", alpha=0.045)
    axis.axvline(0.4, color="#333333", linestyle="--", linewidth=1.4)
    axis.text(0.19, -0.72, "score 0.4未満：除外", ha="center", va="center", fontsize=9, color="#555555")
    axis.text(0.55, -0.72, "score 0.4以上：保持", ha="center", va="center", fontsize=9, color="#555555")
    axis.set_xlim(-0.02, 0.70)
    axis.set_ylim(len(scene_labels) - 0.5, -0.9)
    axis.set_xticks(np.arange(0.0, 0.8, 0.1))
    axis.set_xlabel("共通する遠方2画像のscore")
    axis.set_yticks(y, scene_labels)
    axis.grid(axis="x", color="#D8D8D8", linewidth=0.7)
    axis.set_axisbelow(True)
    axis.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2, frameon=False)
    axis.set_title(
        "最後の4枚だけを変えると，同じ遠方2画像のscoreがthresholdをまたいだ",
        fontsize=14,
        fontweight="bold",
        pad=48,
    )
    fig.savefig(FIGURES / "filter_score_comparison.png", bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.1), sharex=True, sharey=True, constrained_layout=True)
    for axis, values, title in zip(axes, geometry_groups, score_titles):
        colors = ["#3F8F67" if value > 0.5 else "#C94C3C" if value < -0.5 else "#B39B42" for value in values]
        axis.barh(y, values, height=0.58, color=colors, alpha=0.9)
        axis.axvline(0.0, color="#333333", linewidth=1.1)
        for index, value in enumerate(values):
            axis.text(
                value + (0.7 if value >= 0 else -0.7),
                index,
                f"{value:+.1f}",
                ha="left" if value >= 0 else "right",
                va="center",
                fontweight="bold",
            )
        axis.set_title(title, fontweight="bold", pad=12)
        axis.set_xlim(-30, 15)
        axis.set_xlabel("画像除外後 − 除外前（ポイント）")
        axis.set_yticks(y, scene_labels)
        axis.grid(axis="x", color="#D8D8D8", linewidth=0.7)
        axis.set_axisbelow(True)
    axes[0].invert_yaxis()
    fig.suptitle(
        "遠方側の3D表面の再構成率は，正しい遠方画像を除外すると一貫して低下した",
        fontsize=14,
        fontweight="bold",
    )
    fig.savefig(FIGURES / "filter_geometry_change.png", bbox_inches="tight")
    plt.close(fig)


def plot_iterative_filter_cascade(cascade: dict) -> None:
    chains = cascade["chains"]
    scene_order = ("gascola_P003", "gascola_P005", "hospital_P000", "hospital_P003")
    scene_labels = {
        "gascola_P003": "森林 1",
        "gascola_P005": "森林 2",
        "hospital_P000": "病院 1",
        "hospital_P003": "病院 2",
    }
    condition_order = ("base_anchor_reference", "all_valid")
    condition_labels = (
        "別scene画像4枚を含む入力\n1回目だけは別scene画像を正しく除外",
        "12枚すべて同じsceneの入力\n画像が減る処理はすべて誤除外",
    )
    by_key = {(row["scene"], row["condition"]): row for row in chains}
    correct_color = "#3B78A8"
    error_color = "#C94C3C"
    stable_color = "#777777"
    fig, axes = plt.subplots(4, 2, figsize=(11.8, 10.8), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.11, right=0.98, bottom=0.08, top=0.81, hspace=0.15, wspace=0.08)
    for scene_index, scene in enumerate(scene_order):
        for condition_index, condition in enumerate(condition_order):
            axis = axes[scene_index, condition_index]
            row = by_key[(scene, condition)]
            counts = [row["rounds"][0]["input_count"]]
            counts.extend(item["survivor_count"] for item in row["rounds"])
            rounds = np.arange(len(counts))
            for step in range(len(counts) - 1):
                if counts[step + 1] == counts[step]:
                    color = stable_color
                elif condition_index == 0 and step == 0:
                    color = correct_color
                else:
                    color = error_color
                axis.plot(
                    rounds[step : step + 2],
                    counts[step : step + 2],
                    color=color,
                    linewidth=2.8,
                    marker="o",
                    markersize=5.5,
                )
            for round_index, count in zip(rounds[:-1], counts[:-1]):
                axis.text(round_index, count + 0.55, str(count), ha="center", va="bottom", fontsize=8.5)
            axis.text(
                rounds[-1],
                counts[-1] + 0.55,
                f"{counts[-1]}枚で安定",
                ha="center",
                va="bottom",
                fontsize=8.5,
                fontweight="bold",
            )
            axis.set_xlim(-0.25, 7.45)
            axis.set_ylim(0, 14)
            axis.set_xticks(range(8))
            axis.set_yticks((0, 4, 8, 12))
            axis.grid(color="#DEDEDE", linewidth=0.65)
            axis.set_axisbelow(True)
            if scene_index == 0:
                axis.set_title(condition_labels[condition_index], fontweight="bold", pad=12)
            if condition_index == 0:
                axis.set_ylabel(scene_labels[scene])
    legend = (
        Line2D([0], [0], color=correct_color, marker="o", linewidth=2.8, label="別scene画像だけを正しく除外"),
        Line2D([0], [0], color=error_color, marker="o", linewidth=2.8, label="正しい画像を誤って除外"),
        Line2D([0], [0], color=stable_color, marker="o", linewidth=2.8, label="画像集合は変化なし"),
    )
    fig.legend(handles=legend, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.925))
    fig.supxlabel("除外処理の適用回数", y=0.025)
    fig.supylabel("残った画像枚数", x=0.025)
    fig.suptitle(
        "同じ除外処理を繰り返すと，8条件すべてで正しい画像まで除外された",
        fontsize=14,
        fontweight="bold",
        y=0.985,
    )
    fig.savefig(FIGURES / "iterative_filter_small_multiples.png", bbox_inches="tight")
    plt.close(fig)


def plot_distractor_subset_law(results: dict) -> None:
    scene_order = ("gascola_P003", "gascola_P005", "hospital_P000", "hospital_P003")
    scene_labels = {
        "gascola_P003": "森林 1",
        "gascola_P005": "森林 2",
        "hospital_P000": "病院 1",
        "hospital_P003": "病院 2",
    }
    counts = np.arange(5)
    fig, axes = plt.subplots(2, 2, figsize=(9.4, 7.4), sharex=True, sharey=True, constrained_layout=True)
    for axis, scene in zip(axes.flat, scene_order):
        fractions = np.array(
            [
                results["scenes"][scene]["by_distractor_count"][str(count)][
                    "both_retained_fraction"
                ]
                for count in counts
            ]
        )
        percentages = 100.0 * fractions
        axis.plot(counts, percentages, color="#3B78A8", linewidth=2.6, marker="o", markersize=7)
        for count, value in zip(counts, percentages):
            axis.text(count, value + 5.0, f"{value:.0f}%", ha="center", va="bottom", fontsize=9.2)
        axis.set_title(scene_labels[scene], fontweight="bold")
        axis.set_xlim(-0.25, 4.25)
        axis.set_ylim(-5, 115)
        axis.set_xticks(counts)
        axis.set_yticks((0, 25, 50, 75, 100))
        axis.grid(color="#DEDEDE", linewidth=0.7)
        axis.set_axisbelow(True)
    fig.supxlabel("最後の4枠に含めた別scene画像の枚数")
    fig.supylabel("遠方2画像をともに保持した組合せ（%）")
    fig.suptitle(
        "別scene画像が増えるほど，正しい遠方2画像は保持されやすくなった",
        fontsize=14,
        fontweight="bold",
    )
    fig.savefig(FIGURES / "distractor_count_curves.png", bbox_inches="tight")
    plt.close(fig)


def plot_shared_output_projectivity(results: dict) -> None:
    labels = ("森林 1", "森林 2", "病院 1", "病院 2")
    rows = results["scenes"]
    distractor_errors = []
    valid_errors = []
    core_shifts = []
    remote_shifts = []
    for row in rows:
        distractor_errors.append(
            100.0 * row["point_error_relative_change"]["distractor_context"]
        )
        valid_errors.append(
            100.0 * row["point_error_relative_change"]["redundant_context"]
        )
        comparison = row["comparisons_to_common_only"]["distractor_context"][
            "point_shift_fraction_of_camera_diameter"
        ]
        core_shifts.append(100.0 * comparison["core"]["median"])
        remote_shifts.append(100.0 * comparison["extension"]["median"])

    y = np.arange(len(labels))
    height = 0.32
    fig, axes = plt.subplots(1, 2, figsize=(13.8, 6.4))
    fig.subplots_adjust(left=0.07, right=0.98, bottom=0.25, top=0.78, wspace=0.16)
    left_series = (
        (np.array(distractor_errors), -height / 1.8, "#C94C3C", "別scene画像4枚を追加"),
        (np.array(valid_errors), height / 1.8, "#3B78A8", "同じsceneの近傍画像4枚を追加"),
    )
    for values, offset, color, label in left_series:
        axes[0].barh(y + offset, values, height=height, color=color, alpha=0.9, label=label)
        for index, value in enumerate(values):
            axes[0].text(
                value + (0.8 if value >= 0 else -0.8),
                index + offset,
                f"{value:+.1f}%",
                ha="left" if value >= 0 else "right",
                va="center",
                fontsize=9,
            )
    axes[0].axvline(0.0, color="#333333", linewidth=1.1)
    axes[0].set_xlim(-23, 43)
    axes[0].set_xlabel("8画像だけの入力に対する誤差変化")
    axes[0].set_title("共通8画像のpoint map誤差", fontweight="bold")
    axes[0].set_yticks(y, labels)
    axes[0].invert_yaxis()
    axes[0].legend(loc="upper center", bbox_to_anchor=(0.5, -0.20), ncol=1, frameon=False, fontsize=9)
    axes[0].grid(axis="x", color="#DEDEDE", linewidth=0.7)
    axes[0].set_axisbelow(True)

    right_series = (
        (np.array(core_shifts), -height / 1.8, "#6A8FB3", "基準側と重なる5画像"),
        (np.array(remote_shifts), height / 1.8, "#A76D9D", "基準側と直接ほぼ重ならない2画像"),
    )
    for values, offset, color, label in right_series:
        axes[1].barh(y + offset, values, height=height, color=color, alpha=0.9, label=label)
        for index, value in enumerate(values):
            axes[1].text(value + 0.06, index + offset, f"{value:.2f}%", ha="left", va="center", fontsize=9)
    axes[1].set_xlim(0, 3.0)
    axes[1].set_xlabel("camera撮影範囲の直径に対する3D点変位")
    axes[1].set_title("別scene画像追加時の3D点変位", fontweight="bold")
    axes[1].set_yticks(y, labels)
    axes[1].invert_yaxis()
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.20), ncol=1, frameon=False, fontsize=9)
    axes[1].grid(axis="x", color="#DEDEDE", linewidth=0.7)
    axes[1].set_axisbelow(True)
    fig.suptitle(
        "別scene画像を正しく除外できても，除外前の正しい画像の3Dはすでに変化している",
        fontsize=14,
        fontweight="bold",
        y=0.96,
    )
    fig.savefig(FIGURES / "shared_output_change_plots.png", bbox_inches="tight")
    plt.close(fig)


def plot_one_world_design() -> None:
    fig, axis = plt.subplots(figsize=(13.2, 6.2))
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")
    axis.set_title(
        "同じsensor noise模様の反復だけを変える比較",
        fontsize=15,
        fontweight="bold",
        pad=14,
    )

    _box(axis, 0.01, 0.64, 0.15, 0.18, "4つの独立な\n画像系列", "#F1F1F1", fontsize=11)
    _box(axis, 0.21, 0.73, 0.17, 0.14, "2つの撮影位置を\n各6回使用", "#D9EDF7", fontsize=10.5)
    _box(axis, 0.21, 0.55, 0.17, 0.14, "4つの撮影位置を\n各3回使用", "#D9EDF7", fontsize=10.5)
    _box(axis, 0.44, 0.73, 0.18, 0.14, "同じnoise模様を\n同じ位置で反復", "#FCE5CD", fontsize=10.5)
    _box(axis, 0.44, 0.55, 0.18, 0.14, "毎回異なる\nnoise模様を付加", "#FCE5CD", fontsize=10.5)
    _box(
        axis,
        0.69,
        0.64,
        0.29,
        0.18,
        "12枚・順序・基準画像を固定\n基準画像上の48点を追跡\n公式VGGTを1回実行",
        "#E2F0D9",
        fontsize=10.5,
    )
    for start, end in (
        ((0.16, 0.73), (0.21, 0.80)),
        ((0.16, 0.73), (0.21, 0.62)),
        ((0.38, 0.80), (0.44, 0.80)),
        ((0.38, 0.62), (0.44, 0.62)),
        ((0.62, 0.80), (0.69, 0.75)),
        ((0.62, 0.62), (0.69, 0.70)),
    ):
        _arrow(axis, start, end)

    axis.text(
        0.01,
        0.43,
        "同じ点の移動先を，VGGTの三つの出力から求める",
        fontsize=12,
        fontweight="bold",
    )
    _box(axis, 0.02, 0.12, 0.25, 0.20, "奥行きとcameraから\n計算した位置", "#CFE2F3", fontsize=10.5)
    _box(axis, 0.375, 0.12, 0.25, 0.20, "3D点の直接予測から\n計算した位置", "#D9EAD3", fontsize=10.5)
    _box(axis, 0.73, 0.12, 0.25, 0.20, "追跡headが直接\n予測した位置", "#F4CCCC", fontsize=10.5)
    axis.plot((0.27, 0.375), (0.22, 0.22), color="#444444", linewidth=2)
    axis.text(0.3225, 0.255, "3D出力同士のずれ", ha="center", fontsize=9.5)
    _arrow(axis, (0.625, 0.22), (0.73, 0.22))
    axis.text(
        0.6775,
        0.265,
        "二つの3D予測の間から\n追跡予測が外れた距離",
        ha="center",
        fontsize=9.2,
    )
    axis.text(
        0.5,
        0.03,
        "主指標の計算と点の選択にはconfidenceを使わない",
        ha="center",
        color="#8B0000",
        fontweight="bold",
        fontsize=10.5,
    )
    fig.savefig(FIGURES / "vggt_noise_experiment_design.png", bbox_inches="tight")
    plt.close(fig)


def plot_one_world_acquisition_effects(results: dict) -> None:
    scene_order = ("gascola_P003", "gascola_P005", "hospital_P000", "hospital_P003")
    scene_labels = ("Gascola 1", "Gascola 2", "Hospital 1", "Hospital 2")
    rows = results["paired_acquisition_effects"]
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 7.4), sharex=True, constrained_layout=True)
    panels = (
        (2, "tracking_head_extra_mismatch_px", "追跡headだけに残る追加ずれ (px)"),
        (4, "tracking_head_extra_mismatch_px", "追跡headだけに残る追加ずれ (px)"),
        (2, "tracking_confidence", "追跡confidence"),
        (4, "tracking_confidence", "追跡confidence"),
    )
    for panel_index, (axis, (position_count, metric, metric_label)) in enumerate(
        zip(axes.flat, panels)
    ):
        for scene_index, scene in enumerate(scene_order):
            values = np.asarray(
                [
                    row["same_minus_independent_noise"][metric]
                    for row in rows
                    if row["scene"] == scene
                    and row["view_position_count"] == position_count
                ],
                dtype=float,
            )
            assert len(values) == 3
            center = float(np.median(values))
            axis.errorbar(
                scene_index,
                center,
                yerr=np.array([[center - np.min(values)], [np.max(values) - center]]),
                fmt="o",
                markersize=7,
                capsize=4,
                color="#287DB2" if metric.endswith("px") else "#D95F02",
            )
        axis.axhline(0.0, color="#555555", linewidth=1.0, linestyle="--")
        axis.set_xticks(range(4), scene_labels)
        if panel_index % 2 == 0:
            axis.set_ylabel("同じnoise − 異なるnoise\n" + metric_label)
        if panel_index < 2:
            axis.set_title(f"{position_count}つの撮影位置", fontweight="bold")
    fig.suptitle(
        "同じnoise模様を反復した効果：0より上なら反復条件の方が大きい\n"
        "点は各画像系列の3回の中央値，ひげはその範囲",
        fontsize=14,
        fontweight="bold",
    )
    fig.savefig(FIGURES / "vggt_noise_acquisition_effects.png", bbox_inches="tight")
    plt.close(fig)


def plot_one_world_ordinary_error_audit(results: dict) -> None:
    scene_order = ("gascola_P003", "gascola_P005", "hospital_P000", "hospital_P003")
    scene_labels = {
        "gascola_P003": "Gascola 1",
        "gascola_P005": "Gascola 2",
        "hospital_P000": "Hospital 1",
        "hospital_P003": "Hospital 2",
    }
    rows = results["paired_acquisition_effects"]
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 5.1), constrained_layout=True)
    for axis, position_count in zip(axes, (2, 4)):
        for scene_index, scene in enumerate(scene_order):
            scene_rows = [
                row
                for row in rows
                if row["scene"] == scene
                and row["view_position_count"] == position_count
            ]
            x = float(
                np.median(
                    [
                        row["same_minus_independent_noise"]["ordinary_tracking_error_px"]
                        for row in scene_rows
                    ]
                )
            )
            y = float(
                np.median(
                    [
                        row["same_minus_independent_noise"]["tracking_head_extra_mismatch_px"]
                        for row in scene_rows
                    ]
                )
            )
            axis.scatter(x, y, s=70, color=f"C{scene_index}", zorder=3)
            axis.annotate(scene_labels[scene], (x, y), xytext=(6, 6), textcoords="offset points")
        axis.axhline(0.0, color="#555555", linewidth=1.0, linestyle="--")
        axis.axvline(0.0, color="#555555", linewidth=1.0, linestyle="--")
        axis.set_xlabel("通常の追跡誤差の変化 (px)")
        axis.set_ylabel("追跡headだけに残る追加ずれの変化 (px)")
        axis.set_title(f"{position_count}つの撮影位置", fontweight="bold")
    fig.suptitle(
        "追加ずれは通常の追跡誤差とは別に変化したか\n"
        "各点は一つの画像系列，横軸・縦軸とも「同じnoise − 異なるnoise」",
        fontsize=14,
        fontweight="bold",
    )
    fig.savefig(FIGURES / "vggt_noise_ordinary_error_audit.png", bbox_inches="tight")
    plt.close(fig)


def plot_one_world_qualitative(results: dict, packet: dict[str, np.ndarray]) -> None:
    image = packet["rgb"]
    points = packet["points_xy"].astype(float)
    native, depth, direct_point, ground_truth = points
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.9))
    margin_x = max(8.0, float(np.ptp(points[:, 0])) * 0.8)
    margin_y = max(8.0, float(np.ptp(points[:, 1])) * 0.8)
    x_min = float(np.min(points[:, 0]) - margin_x)
    x_max = float(np.max(points[:, 0]) + margin_x)
    y_min = float(np.min(points[:, 1]) - margin_y)
    y_max = float(np.max(points[:, 1]) + margin_y)
    entries = (
        (native, "o", "#D62728", "追跡head"),
        (depth, "X", "#1F77B4", "奥行き＋camera"),
        (direct_point, "P", "#2CA02C", "3D点の直接予測"),
        (ground_truth, "*", "#FFDD57", "正解位置"),
    )

    def draw(axis, marker_size: float) -> None:
        axis.imshow(image, zorder=0)
        axis.plot(
            (depth[0], direct_point[0]),
            (depth[1], direct_point[1]),
            color="#222222",
            linewidth=2.5,
            zorder=2,
        )
        for coordinates, marker, color, text in entries:
            axis.scatter(
                *coordinates,
                s=marker_size,
                marker=marker,
                color=color,
                edgecolor="black" if marker == "*" else "white",
                linewidth=1.1,
                zorder=3,
            )

    draw(axes[0], marker_size=85)
    draw(axes[1], marker_size=145)
    axes[0].add_patch(
        Rectangle(
            (x_min, y_min),
            x_max - x_min,
            y_max - y_min,
            fill=False,
            edgecolor="white",
            linewidth=2.0,
            linestyle="--",
            zorder=4,
        )
    )
    axes[0].set_title("画像全体（白枠を右で拡大）", fontweight="bold")
    axes[1].set_xlim(x_min, x_max)
    axes[1].set_ylim(y_max, y_min)
    axes[1].set_title("画像内の局所的な位置関係", fontweight="bold")

    segment = direct_point - depth
    denominator = float(np.dot(segment, segment))
    fraction = (
        float(np.clip(np.dot(native - depth, segment) / denominator, 0.0, 1.0))
        if denominator > 1.0e-16
        else 0.0
    )
    closest = depth + fraction * segment
    axes[1].plot(
        (native[0], closest[0]),
        (native[1], closest[1]),
        color="#D62728",
        linewidth=2.0,
        linestyle="--",
        zorder=2,
    )
    mismatch = results["qualitative"]["tracking_head_extra_mismatch_px_original_image"]
    midpoint = (native + closest) / 2.0
    axes[1].annotate(
        f"元画像で {mismatch:.1f} px",
        midpoint,
        xytext=(0, -18),
        textcoords="offset points",
        ha="center",
        fontsize=8.8,
        fontweight="bold",
        color="#9E1B1B",
        bbox={"boxstyle": "round,pad=0.2", "facecolor": "white", "alpha": 0.9, "edgecolor": "none"},
    )
    for axis in axes:
        axis.set_xlabel("画像のx座標 (px)")
        axis.set_ylabel("画像のy座標 (px)")

    legend_handles = [
        Line2D([], [], marker=marker, linestyle="none", markersize=9, markerfacecolor=color,
               markeredgecolor="black" if marker == "*" else "white", label=label)
        for _point, marker, color, label in entries
    ]
    legend_handles.extend(
        [
            Line2D([], [], color="#222222", linewidth=2.5, label="二つの3D経路が示す範囲"),
            Line2D([], [], color="#D62728", linewidth=2.0, linestyle="--", label="追跡headだけに残る追加ずれ"),
        ]
    )
    fig.legend(handles=legend_handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.01))
    fig.suptitle(
        "実例：正解位置と三つの予測位置がすべて画像内にある場合",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    fig.subplots_adjust(left=0.07, right=0.98, top=0.86, bottom=0.20, wspace=0.22)
    fig.savefig(FIGURES / "vggt_noise_qualitative.png", bbox_inches="tight")
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
    one_world_results, one_world_packet = load_one_world_results()
    validate(rows, summary)
    validate_set_filter_results(
        set_filter_geometry, iterative_filter, subset_law, projectivity
    )
    validate_qualitative_results(qualitative_metadata, qualitative_packet)
    validate_one_world_results(one_world_results, one_world_packet)
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
    plot_one_world_design()
    plot_one_world_acquisition_effects(one_world_results)
    plot_one_world_ordinary_error_audit(one_world_results)
    plot_one_world_qualitative(one_world_results, one_world_packet)

    if args.check:
        for name in (
            "experiment_design.png",
            "dvlt_k_sweep.png",
            "oracle_action_ceiling.png",
            "correspondence_diagnostics.png",
            "constraint_output_hypothesis.png",
            "constraint_matched_test.png",
            "filter_qualitative_example.png",
            "filter_score_comparison.png",
            "filter_geometry_change.png",
            "iterative_filter_small_multiples.png",
            "distractor_count_curves.png",
            "projectivity_qualitative_example.png",
            "shared_output_change_plots.png",
            "vggt_noise_experiment_design.png",
            "vggt_noise_acquisition_effects.png",
            "vggt_noise_ordinary_error_audit.png",
            "vggt_noise_qualitative.png",
        ):
            path = FIGURES / name
            assert path.exists() and path.stat().st_size > 10_000, path
        print("CHECK_OK: data, headline values, and figures are consistent")


if __name__ == "__main__":
    main()
