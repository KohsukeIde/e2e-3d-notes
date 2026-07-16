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
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402


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


def load_set_filter_results() -> tuple[dict, dict]:
    geometry = json.loads((DATA / "set_relative_filter_geometry.json").read_text())
    cascade = json.loads((DATA / "iterative_filter_cascade.json").read_text())
    return geometry, cascade


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


def validate_set_filter_results(geometry: dict, cascade: dict) -> None:
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
    labels = [row["scene"].replace("_", " ") for row in rows]
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    roles = ("connector", "extension_center", "extension")
    markers = {"connector": "o", "extension_center": "s", "extension": "^"}
    x = np.arange(len(rows), dtype=float)
    for role in roles:
        with_distractors = []
        all_valid = []
        for row in rows:
            shared = next(item for item in row["shared_source_views"] if item["role"] == role)
            with_distractors.append(shared["score_with_distractors"])
            all_valid.append(shared["score_all_valid"])
        axes[0].scatter(x - 0.08, with_distractors, marker=markers[role], label=f"{role}: distractors")
        axes[0].scatter(
            x + 0.08,
            all_valid,
            marker=markers[role],
            facecolors="none",
            label=f"{role}: all valid",
        )
        for index in range(len(rows)):
            axes[0].plot(
                [x[index] - 0.08, x[index] + 0.08],
                [with_distractors[index], all_valid[index]],
                color="0.75",
            )
    axes[0].axhline(0.4, color="black", linestyle="--", linewidth=1)
    axes[0].set_xticks(x, labels, rotation=25, ha="right")
    axes[0].set_ylim(-0.02, 1.02)
    axes[0].set_ylabel("View score")
    axes[0].set_title("Removing distractors rejects valid frontier views")
    axes[0].legend(fontsize=7, ncol=2, frameon=False)

    observed_extension = []
    same_forward_valid_only = []
    actual_all_valid = []
    for row in rows:
        counterfactual = [
            item
            for item in row["same_forward_counterfactual"]
            if item["role"] in {"extension_center", "extension"}
        ]
        shared = [
            item
            for item in row["shared_source_views"]
            if item["role"] in {"extension_center", "extension"}
        ]
        observed_extension.append(
            float(np.mean([item["observed_score_with_distractors"] for item in counterfactual]))
        )
        same_forward_valid_only.append(
            float(np.mean([item["valid_only_score_same_forward"] for item in counterfactual]))
        )
        actual_all_valid.append(float(np.mean([item["score_all_valid"] for item in shared])))
    width = 0.25
    axes[1].bar(x - width, observed_extension, width, label="observed with distractors")
    axes[1].bar(x, same_forward_valid_only, width, label="same raw scores, valid-only min-max")
    axes[1].bar(x + width, actual_all_valid, width, label="actual all-valid forward")
    axes[1].axhline(0.4, color="black", linestyle="--", linewidth=1)
    axes[1].set_xticks(x, labels, rotation=25, ha="right")
    axes[1].set_ylim(0.0, 0.75)
    axes[1].set_ylabel("Mean extension score")
    axes[1].set_title("Min-max calibration alone is sufficient")
    axes[1].legend(fontsize=7, frameon=False)

    distractor_delta = [
        row["geometry"]["base_anchor_reference"]["filtering_delta"] for row in rows
    ]
    all_valid_delta = [row["geometry"]["all_valid"]["filtering_delta"] for row in rows]
    axes[2].bar(x - 0.18, distractor_delta, 0.36, label="filter distractor set")
    axes[2].bar(x + 0.18, all_valid_delta, 0.36, label="filter all-valid set")
    axes[2].axhline(0.0, color="black", linewidth=1)
    axes[2].set_xticks(x, labels, rotation=25, ha="right")
    axes[2].set_ylabel("Held-out completeness change")
    axes[2].set_title("Filtering clean sets is consistently more harmful")
    axes[2].legend(fontsize=8, frameon=False)

    fig.tight_layout()
    fig.savefig(FIGURES / "set_relative_filter_geometry.png", bbox_inches="tight")
    plt.close(fig)


def plot_iterative_filter_cascade(cascade: dict) -> None:
    chains = cascade["chains"]
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    colors = {
        "gascola_P003": "#1f77b4",
        "gascola_P005": "#17becf",
        "hospital_P000": "#ff7f0e",
        "hospital_P003": "#d62728",
    }
    for row in chains:
        x = [item["round"] for item in row["rounds"]]
        y = [item["input_count"] for item in row["rounds"]]
        y.append(row["rounds"][-1]["survivor_count"])
        x.append(x[-1] + 1)
        linestyle = "-" if row["condition"] == "base_anchor_reference" else "--"
        condition = "distractors" if linestyle == "-" else "all valid"
        label = f"{row['scene'].replace('_', ' ')} / {condition}"
        axes[0].step(
            x,
            y,
            where="post",
            color=colors[row["scene"]],
            linestyle=linestyle,
            marker="o",
            label=label,
        )
    axes[0].set_xlabel("Filter application")
    axes[0].set_ylabel("Remaining views")
    axes[0].set_ylim(0, 13)
    axes[0].set_title("Repeated filtering does not stop after cleanup")
    axes[0].legend(fontsize=7, ncol=2, frameon=False)

    categories = ("distractor", "extension", "connector", "core / redundant")
    category_colors = ("#d62728", "#2ca02c", "#ff7f0e", "#6baed6")
    max_round = max(max(item["round"] for item in row["rounds"]) for row in chains)
    counts = np.zeros((len(categories), max_round + 1), dtype=np.int64)
    for row in chains:
        for item in row["rounds"]:
            for role in item["rejected_roles"]:
                if role == "distractor":
                    category = 0
                elif role in {"extension_center", "extension"}:
                    category = 1
                elif role == "connector":
                    category = 2
                else:
                    category = 3
                counts[category, item["round"]] += 1
    bottom = np.zeros(max_round + 1, dtype=np.int64)
    for category, color, values in zip(categories, category_colors, counts):
        axes[1].bar(range(max_round + 1), values, bottom=bottom, label=category, color=color)
        bottom += values
    axes[1].set_xlabel("Filter application")
    axes[1].set_ylabel("Views newly rejected across eight chains")
    axes[1].set_title("The identity of the outlier moves inward")
    axes[1].legend(fontsize=8, frameon=False)

    labels = [
        f"{row['scene'].replace('_', ' ')}\n"
        f"{'distractors' if row['condition'] == 'base_anchor_reference' else 'all valid'}"
        for row in chains
    ]
    final_count = [row["final_survivor_count"] for row in chains]
    starting_valid = [8 if row["condition"] == "base_anchor_reference" else 12 for row in chains]
    x = np.arange(len(chains))
    axes[2].bar(x, starting_valid, color="0.85", label="valid views at start")
    axes[2].bar(x, final_count, color="#4c78a8", label="fixed-point survivors")
    axes[2].set_xticks(x, labels, rotation=45, ha="right", fontsize=7)
    axes[2].set_ylabel("View count")
    axes[2].set_ylim(0, 13)
    axes[2].set_title("The fixed point retains only 2–3 views")
    axes[2].legend(fontsize=8, frameon=False)

    fig.tight_layout()
    fig.savefig(FIGURES / "iterative_filter_cascade.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate data and generated files")
    args = parser.parse_args()

    FIGURES.mkdir(parents=True, exist_ok=True)
    validate_checksums()
    rows = load_csv()
    summary = load_summary()
    set_filter_geometry, iterative_filter = load_set_filter_results()
    validate(rows, summary)
    validate_set_filter_results(set_filter_geometry, iterative_filter)
    style()
    plot_experiment_design()
    plot_dvlt(rows)
    plot_action_ceiling(summary)
    plot_correspondence_diagnostics(summary)
    plot_constraint_output_hypothesis()
    plot_constraint_matched_test()
    plot_set_relative_filter_geometry(set_filter_geometry)
    plot_iterative_filter_cascade(iterative_filter)

    if args.check:
        for name in (
            "experiment_design.png",
            "dvlt_k_sweep.png",
            "oracle_action_ceiling.png",
            "correspondence_diagnostics.png",
            "constraint_output_hypothesis.png",
            "constraint_matched_test.png",
            "set_relative_filter_geometry.png",
            "iterative_filter_cascade.png",
        ):
            path = FIGURES / name
            assert path.exists() and path.stat().st_size > 10_000, path
        print("CHECK_OK: data, headline values, and figures are consistent")


if __name__ == "__main__":
    main()
