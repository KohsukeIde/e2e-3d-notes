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


def plot_dvlt(rows: list[dict]) -> None:
    ks = [row["K"] for row in rows]
    pose = [row["pose_auc30"] for row in rows]
    absrel = [row["depth_absrel"] for row in rows]

    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.2))
    for ax in axes:
        ax.axvspan(8, 16, color="#dce9f8", alpha=0.85, label="trained K range")
        ax.axvline(16, color="#4c78a8", linestyle="--", linewidth=1)
        ax.axvline(32, color="#e45756", linestyle=":", linewidth=1.4)
        ax.set_xticks(ks)
        ax.grid(axis="y", color="#dddddd", linewidth=0.7)

    axes[0].plot(ks, pose, marker="o", color="#4c78a8", linewidth=2.2)
    axes[0].set_title("Pose quality collapses beyond the sweet spot")
    axes[0].set_xlabel("Recurrent applications K")
    axes[0].set_ylabel("ETH3D Pose AUC@30 (higher is better)")
    axes[0].set_ylim(0, 1.03)
    axes[0].annotate("0.954", (16, pose[2]), xytext=(18, 0.84), arrowprops={"arrowstyle": "->"})
    axes[0].annotate("0.021", (64, pose[-1]), xytext=(49, 0.22), arrowprops={"arrowstyle": "->"})

    axes[1].plot(ks, absrel, marker="o", color="#e45756", linewidth=2.2)
    axes[1].set_yscale("log")
    axes[1].set_title("Depth error is ~17.2x worse at K=64 vs K=16")
    axes[1].set_xlabel("Recurrent applications K")
    axes[1].set_ylabel("ETH3D Depth AbsRel (lower is better, log scale)")
    axes[1].annotate("0.018", (16, absrel[2]), xytext=(21, 0.027), arrowprops={"arrowstyle": "->"})
    axes[1].annotate("0.313", (64, absrel[-1]), xytext=(45, 0.16), arrowprops={"arrowstyle": "->"})
    axes[1].legend(frameon=False, loc="upper left")

    fig.suptitle("Déjà View / DVLT: more test-time iteration is not a safe anytime knob", y=1.03, fontsize=14)
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
    bars = axes[0].bar(["All (n=24)", "Easy (n=15)", "Hard (n=9)"], medians, color=colors)
    axes[0].set_ylabel("Median oracle action gain in Pose AUC@30")
    axes[0].set_title("Potential value exists in both regimes")
    axes[0].set_ylim(0, 0.061)
    axes[0].grid(axis="y", color="#dddddd", linewidth=0.7)
    axes[0].bar_label(bars, fmt="%.3f", padding=3)

    names = ["KEEP", "REFINE", "REPAIR"]
    counts = [actions[name] for name in names]
    bars = axes[1].bar(names, counts, color=["#9d9d9d", "#f58518", "#54a24b"])
    axes[1].set_ylabel("Sequences where action is oracle-best")
    axes[1].set_title("The ceiling is repair-dominant")
    axes[1].set_ylim(0, 24)
    axes[1].bar_label(bars, padding=3)

    fig.suptitle("Oracle KEEP / REFINE / REPAIR ceiling", y=1.03, fontsize=14)
    fig.tight_layout()
    fig.savefig(FIGURES / "oracle_action_ceiling.png", bbox_inches="tight")
    plt.close(fig)


def plot_correspondence_diagnostics(summary: dict) -> None:
    gaps = summary["easy_oracle_gap"]
    refusals = summary["hard_refusal_attempt_level"]

    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.2))
    labels = ["External tracker\n(a1)", "VGGT track head\n(a2)"]

    gap_values = [gaps["a1_external_tracker"]["median_auc30"], gaps["a2_vggt_track_head"]["median_auc30"]]
    bars = axes[0].bar(labels, gap_values, color=["#72b7b2", "#4c78a8"])
    axes[0].set_ylabel("Median oracle - learned Pose AUC@30")
    axes[0].set_title("Easy sequences: small but nonzero gap")
    axes[0].set_ylim(0, 0.04)
    axes[0].bar_label(bars, fmt="%.4f", padding=3)

    refusal_values = [refusals["a1_external_tracker"], refusals["a2_vggt_track_head"]]
    bars = axes[1].bar(labels, refusal_values, color=["#f2cf5b", "#e45756"])
    axes[1].set_ylabel("Hard-tier refusal rate (attempt level)")
    axes[1].set_title("Hard sequences: correspondence pipeline breaks")
    axes[1].set_ylim(0, 1.0)
    axes[1].bar_label(bars, labels=[f"{100*x:.1f}%" for x in refusal_values], padding=3)

    fig.suptitle("Track source matters, but even the stronger external tracker is not enough", y=1.03, fontsize=14)
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
    plot_dvlt(rows)
    plot_action_ceiling(summary)
    plot_correspondence_diagnostics(summary)

    if args.check:
        for name in ("dvlt_k_sweep.png", "oracle_action_ceiling.png", "correspondence_diagnostics.png"):
            path = FIGURES / name
            assert path.exists() and path.stat().st_size > 10_000, path
        print("CHECK_OK: data, headline values, and figures are consistent")


if __name__ == "__main__":
    main()
