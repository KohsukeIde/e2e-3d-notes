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

    ax.text(0.5, 0.96, "Two diagnostics isolate measurement construction and recurrent application count", ha="center", va="top", fontsize=14.5)
    ax.text(0.03, 0.87, "TEST 1  Does the measurement-construction path change the attainable result?", weight="bold", fontsize=11.5)
    ax.text(
        0.97,
        0.80,
        "Hold fixed: images, VGGT estimate, and solver   |   Swap: measurement-construction path",
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
        "Swap measurement construction\n\nExternal tracker\nVGGT track head\nGround-truth projection",
        "#d9f0ed",
        fontsize=9.2,
    )
    _box(ax, 0.66, 0.56, 0.14, 0.16, "Same bundle-\nadjustment solver", "#eee3f6")
    _box(ax, 0.85, 0.56, 0.12, 0.16, "Pose score\nor refusal", "#f6dddd")
    _arrow(ax, (0.14, 0.64), (0.19, 0.64))
    _arrow(ax, (0.36, 0.64), (0.41, 0.64))
    _arrow(ax, (0.61, 0.64), (0.66, 0.64))
    _arrow(ax, (0.80, 0.64), (0.85, 0.64))

    ax.text(
        0.5,
        0.40,
        "A changed result attributes part of the gap to the measurement path; it does not isolate match correctness alone.",
        ha="center",
        fontsize=10.5,
        color="#333333",
    )

    ax.plot([0.03, 0.97], [0.34, 0.34], color="#cccccc", linewidth=1)
    ax.text(0.03, 0.27, "TEST 2  What happens when one checkpoint is applied beyond its trained iteration range?", weight="bold", fontsize=11.5)
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
    axes[0].set_title("Pose quality degrades under long extrapolation")
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

    fig.suptitle("Déjà View: one checkpoint under out-of-range recurrent application", y=1.03, fontsize=14)
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
    bars = axes[0].bar(["All (n=24)", "Standard (n=15)", "Stress (n=9)"], medians, color=colors)
    axes[0].set_ylabel("Median gain of the best available intervention")
    axes[0].set_title("Post-hoc best-of-three ceiling is positive")
    axes[0].set_ylim(0, 0.061)
    axes[0].grid(axis="y", color="#dddddd", linewidth=0.7)
    axes[0].bar_label(bars, fmt="%.3f", padding=3)

    action_keys = ["KEEP", "REFINE", "REPAIR"]
    names = ["Return\nestimate", "Optimize\nfixed tracks", "Replace\ntracks"]
    counts = [actions[name] for name in action_keys]
    bars = axes[1].bar(names, counts, color=["#9d9d9d", "#f58518", "#54a24b"])
    axes[1].set_ylabel("Sequences where intervention gives the largest gain")
    axes[1].set_title("Ground-truth measurements win most often")
    axes[1].set_ylim(0, 24)
    axes[1].bar_label(bars, padding=3)

    fig.suptitle("Complete-case ceiling from three post-hoc choices", y=1.03, fontsize=14)
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
    axes[0].set_ylabel("Median perfect - learned Pose AUC@30")
    axes[0].set_title("Standard group: small but nonzero gap")
    axes[0].set_ylim(0, 0.04)
    axes[0].bar_label(bars, fmt="%.4f", padding=3)

    refusal_values = [refusals["a1_external_tracker"], refusals["a2_vggt_track_head"]]
    bars = axes[1].bar(labels, refusal_values, color=["#f2cf5b", "#e45756"])
    axes[1].set_ylabel("Stress-group refusal rate (attempt level)")
    axes[1].set_title("Stress group: measurement pipeline is often refused")
    axes[1].set_ylim(0, 1.0)
    axes[1].bar_label(bars, labels=[f"{100*x:.1f}%" for x in refusal_values], padding=3)

    fig.suptitle("Two diagnostics of the measurement-construction pipeline", y=1.03, fontsize=14)
    fig.tight_layout()
    fig.savefig(FIGURES / "correspondence_diagnostics.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate data and generated files")
    args = parser.parse_args()

    FIGURES.mkdir(parents=True, exist_ok=True)
    validate_checksums()
    rows = load_csv()
    summary = load_summary()
    validate(rows, summary)
    style()
    plot_experiment_design()
    plot_dvlt(rows)
    plot_action_ceiling(summary)
    plot_correspondence_diagnostics(summary)

    if args.check:
        for name in (
            "experiment_design.png",
            "dvlt_k_sweep.png",
            "oracle_action_ceiling.png",
            "correspondence_diagnostics.png",
        ):
            path = FIGURES / name
            assert path.exists() and path.stat().st_size > 10_000, path
        print("CHECK_OK: data, headline values, and figures are consistent")


if __name__ == "__main__":
    main()
