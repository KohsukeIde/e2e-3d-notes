#!/usr/bin/env python3
"""Validate the public ReCal3R packet and regenerate its four figures."""

from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mplconfig"))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
from PIL import Image  # noqa: E402


DATA_PATH = ROOT / "data" / "recal3r_single_write_screen.json"
PACKET_PATH = ROOT / "data" / "recal3r_single_write_qualitative.npz"
FIGURE_DIR = ROOT / "figures"
FIGURE_NAMES = (
    "recal3r_write_intervention_design.png",
    "recal3r_write_recording_effect.png",
    "recal3r_write_event_effect.png",
    "recal3r_write_qualitative.png",
)
RECORDING_ORDER = (
    "walking static",
    "walking xyz",
    "walking rpy",
    "walking halfsphere",
)
INTERVENTION_ORDER = ("11枚目→12枚目", "21枚目→22枚目")

# Select a concrete Japanese font file when one of these known files exists.
# This intentionally avoids querying the host's font catalog.
FONT_CANDIDATES = (
    Path("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf"),
)


def configure_style() -> None:
    font_path = next((path for path in FONT_CANDIDATES if path.is_file()), None)
    if font_path is not None:
        font_manager.fontManager.addfont(str(font_path))
        font_family = font_manager.FontProperties(fname=str(font_path)).get_name()
    else:
        font_family = "DejaVu Sans"
    plt.rcParams.update(
        {
            "font.family": font_family,
            "axes.unicode_minus": False,
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 140,
            "savefig.dpi": 220,
            "savefig.facecolor": "white",
        }
    )


def load_public_data() -> tuple[dict, dict[str, np.ndarray]]:
    results = json.loads(DATA_PATH.read_text())
    with np.load(PACKET_PATH, allow_pickle=False) as packet:
        arrays = {name: packet[name] for name in packet.files}
    return results, arrays


def _assert_finite_numbers(value: object) -> None:
    if isinstance(value, dict):
        for child in value.values():
            _assert_finite_numbers(child)
    elif isinstance(value, list):
        for child in value:
            _assert_finite_numbers(child)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        assert math.isfinite(value)


def validate_public_data(results: dict, packet: dict[str, np.ndarray]) -> None:
    assert results["status"] == "complete"
    assert results["settings"]["recording_count"] == 4
    assert results["settings"]["event_count"] == 8
    assert results["settings"]["interventions"] == list(INTERVENTION_ORDER)
    _assert_finite_numbers(results)

    serialized = json.dumps(results, ensure_ascii=False)
    for forbidden in (
        "zero_based",
        "/Users/",
        "_theme_exploration",
        "camera_center_error",
        "camera_rotation_error",
    ):
        assert forbidden not in serialized

    events = results["events"]
    aggregates = results["recording_aggregates"]
    assert len(events) == 8
    assert len(aggregates) == 4
    assert {event["recording"] for event in events} == set(RECORDING_ORDER)
    assert {row["recording"] for row in aggregates} == set(RECORDING_ORDER)

    for recording in RECORDING_ORDER:
        recording_events = [
            event for event in events if event["recording"] == recording
        ]
        assert len(recording_events) == 2
        assert {
            event["intervention"] for event in recording_events
        } == set(INTERVENTION_ORDER)
        aggregate = next(
            row for row in aggregates if row["recording"] == recording
        )
        assert aggregate["event_count"] == 2
        endpoint_passes = []
        for endpoint, raw_key in (
            ("depth", "depth_absrel"),
            ("aligned_3d_point", "aligned_3d_point_error"),
        ):
            normal_values = [
                event["normal_write_errors"][raw_key] for event in recording_events
            ]
            disabled_values = [
                event["disabled_write_errors"][raw_key]
                for event in recording_events
            ]
            normal_mean = float(np.mean(normal_values))
            disabled_mean = float(np.mean(disabled_values))
            expected_change = abs(disabled_mean - normal_mean) / normal_mean * 100.0
            stored_change = aggregate["absolute_relative_change_percent"][endpoint]
            assert math.isclose(
                stored_change, expected_change, rel_tol=1.0e-12, abs_tol=1.0e-12
            )
            assert math.isclose(
                aggregate["mean_raw_errors"][f"normal_write_{raw_key}"],
                normal_mean,
                rel_tol=1.0e-12,
                abs_tol=1.0e-12,
            )
            assert math.isclose(
                aggregate["mean_raw_errors"][f"disabled_write_{raw_key}"],
                disabled_mean,
                rel_tol=1.0e-12,
                abs_tol=1.0e-12,
            )
            sham_floor = results["frozen_continuation_rule"][
                "sham_floor_percent"
            ][endpoint]
            threshold = max(1.0, 10.0 * sham_floor)
            assert math.isclose(
                results["frozen_continuation_rule"][
                    "effective_threshold_percent"
                ][endpoint],
                threshold,
            )
            endpoint_passes.append(expected_change > threshold)
        assert aggregate["recording_passed"] is any(endpoint_passes)

        for event in recording_events:
            assert set(event["normal_write_errors"]) == {
                "depth_absrel",
                "aligned_3d_point_error",
            }
            assert set(event["disabled_write_errors"]) == {
                "depth_absrel",
                "aligned_3d_point_error",
            }
            for endpoint, raw_key in (
                ("depth", "depth_absrel"),
                ("aligned_3d_point", "aligned_3d_point_error"),
            ):
                normal = event["normal_write_errors"][raw_key]
                disabled = event["disabled_write_errors"][raw_key]
                expected = (disabled - normal) / normal * 100.0
                assert math.isclose(
                    event["signed_effect_percent"][endpoint],
                    expected,
                    rel_tol=1.0e-12,
                    abs_tol=1.0e-12,
                )
            assert event["invalid_output_rate"] == {
                "normal_write": 0.0,
                "disabled_write": 0.0,
            }

    passed = sum(row["recording_passed"] for row in aggregates)
    gate = results["frozen_continuation_rule"]
    assert passed == 0
    assert gate["passed_recordings"] == passed
    assert gate["required_recordings"] == 3
    assert gate["status"] == "FAIL"
    assert results["controls"]["control_reports"] == 16
    assert results["controls"]["all_control_reports_valid"] is True
    assert results["controls"]["all_checks_passed"] is True
    assert results["controls"]["invalid_episodes"] == 0
    assert results["controls"]["invalid_outputs"] == 0
    assert results["rerun_agreement"]["screen_scalars"] == (
        "Every scalar was reproduced exactly."
    )
    assert results["rerun_agreement"]["qualitative_arrays"] == (
        "Every array element was reproduced exactly."
    )

    expected_packet_keys = {
        "next_image_rgb",
        "ground_truth_depth",
        "valid_mask",
        "normal_write_aligned_depth",
        "disabled_write_aligned_depth",
        "normal_write_absrel_error",
        "disabled_write_absrel_error",
        "error_difference_disabled_minus_normal",
        "recording_label",
        "intervention_label",
        "time_gap_seconds",
        "depth_signed_effect_percent",
        "aligned_3d_point_signed_effect_percent",
        "selection_scope",
        "sign_explanation",
    }
    assert set(packet) == expected_packet_keys
    assert packet["next_image_rgb"].shape == (384, 512, 3)
    for name in (
        "ground_truth_depth",
        "valid_mask",
        "normal_write_aligned_depth",
        "disabled_write_aligned_depth",
        "normal_write_absrel_error",
        "disabled_write_absrel_error",
        "error_difference_disabled_minus_normal",
    ):
        assert packet[name].shape == (384, 512)
    valid = packet["valid_mask"].astype(bool)
    assert np.any(valid) and np.any(~valid)
    for name in (
        "ground_truth_depth",
        "normal_write_aligned_depth",
        "disabled_write_aligned_depth",
        "normal_write_absrel_error",
        "disabled_write_absrel_error",
        "error_difference_disabled_minus_normal",
    ):
        assert np.isfinite(packet[name][valid]).all()
    assert np.all(packet["ground_truth_depth"][valid] > 0.0)
    np.testing.assert_allclose(
        packet["error_difference_disabled_minus_normal"][valid],
        (
            packet["disabled_write_absrel_error"]
            - packet["normal_write_absrel_error"]
        )[valid],
        rtol=1.0e-6,
        atol=1.0e-7,
    )

    qualitative = results["qualitative_selection"]
    assert packet["recording_label"].item() == qualitative["recording"]
    assert packet["intervention_label"].item() == qualitative["intervention"]
    assert "zero" not in packet["selection_scope"].item().lower()
    assert "/Users/" not in packet["selection_scope"].item()
    selected_event = next(
        event
        for event in events
        if event["recording"] == qualitative["recording"]
        and event["intervention"] == qualitative["intervention"]
    )
    assert math.isclose(
        packet["time_gap_seconds"].item(), selected_event["time_gap_seconds"]
    )
    assert math.isclose(
        packet["depth_signed_effect_percent"].item(),
        selected_event["signed_effect_percent"]["depth"],
    )
    assert math.isclose(
        packet["aligned_3d_point_signed_effect_percent"].item(),
        selected_event["signed_effect_percent"]["aligned_3d_point"],
    )


def _rounded_box(
    axis,
    xy: tuple[float, float],
    width: float,
    height: float,
    text: str,
    color: str,
    *,
    fontsize: float = 10,
    border: str = "#3F3F3F",
) -> None:
    x, y = xy
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        facecolor=color,
        edgecolor=border,
        linewidth=1.4,
    )
    axis.add_patch(patch)
    axis.text(
        x + width / 2,
        y + height / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
    )


def _arrow(
    axis,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str = "#555555",
) -> None:
    axis.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=1.5,
            color=color,
        )
    )


def plot_intervention_design(output_dir: Path) -> None:
    fig, axis = plt.subplots(figsize=(14.4, 6.8))
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")
    axis.set_title(
        "一回のscene-state書き込みだけを変える対応比較",
        fontsize=16,
        fontweight="bold",
        pad=15,
    )

    _rounded_box(
        axis,
        (0.025, 0.60),
        0.16,
        0.18,
        "1〜10枚目\n共通の履歴",
        "#E9EEF3",
        fontsize=11,
    )
    _rounded_box(
        axis,
        (0.235, 0.60),
        0.20,
        0.18,
        "11枚目（書き込み対象）\n現在の3Dを先に予測",
        "#D8EAF6",
        fontsize=10.5,
    )
    _rounded_box(
        axis,
        (0.505, 0.73),
        0.22,
        0.14,
        "通常条件\nscene stateへ書き込む",
        "#DCEFD8",
        fontsize=10.5,
    )
    _rounded_box(
        axis,
        (0.505, 0.48),
        0.22,
        0.14,
        "介入条件\nscene stateだけ書き込まない",
        "#F7DDD8",
        fontsize=10.5,
    )
    _rounded_box(
        axis,
        (0.80, 0.60),
        0.17,
        0.18,
        "12枚目\n自身の書き込み前に\n3D誤差を測る",
        "#F4E7BB",
        fontsize=10.5,
    )
    _arrow(axis, (0.185, 0.69), (0.235, 0.69))
    _arrow(axis, (0.435, 0.69), (0.505, 0.80), color="#37835A")
    _arrow(axis, (0.435, 0.69), (0.505, 0.55), color="#B24A3B")
    _arrow(axis, (0.725, 0.80), (0.80, 0.71), color="#37835A")
    _arrow(axis, (0.725, 0.55), (0.80, 0.65), color="#B24A3B")

    _rounded_box(
        axis,
        (0.19, 0.20),
        0.62,
        0.15,
        "両条件で固定：同じ入力履歴・11枚目・現在出力・姿勢メモリ・既知の補助状態",
        "#F2F2F2",
        fontsize=10.5,
        border="#777777",
    )
    axis.text(
        0.5,
        0.10,
        "同じ設計を「21枚目→22枚目」にも適用する．次画像までの時間差は0.772〜1.214秒．",
        ha="center",
        fontsize=10,
        color="#444444",
    )
    fig.savefig(
        output_dir / "recal3r_write_intervention_design.png",
        bbox_inches="tight",
    )
    plt.close(fig)


def plot_recording_effect(results: dict, output_dir: Path) -> None:
    rows = {
        row["recording"]: row for row in results["recording_aggregates"]
    }
    labels = ("static", "xyz", "rpy", "halfsphere")
    depth = np.asarray(
        [
            rows[recording]["absolute_relative_change_percent"]["depth"]
            for recording in RECORDING_ORDER
        ]
    )
    points = np.asarray(
        [
            rows[recording]["absolute_relative_change_percent"][
                "aligned_3d_point"
            ]
            for recording in RECORDING_ORDER
        ]
    )
    x = np.arange(4)
    width = 0.34
    fig, axis = plt.subplots(figsize=(10.8, 5.5), constrained_layout=True)
    depth_bars = axis.bar(
        x - width / 2,
        depth,
        width,
        label="奥行き AbsRel",
        color="#3B82B4",
    )
    point_bars = axis.bar(
        x + width / 2,
        points,
        width,
        label="位置合わせ後の3D点誤差",
        color="#E28C3C",
    )
    axis.axhline(
        1.0,
        color="#A32020",
        linestyle="--",
        linewidth=1.7,
        label="継続基準 1%",
    )
    axis.text(
        3.52,
        1.015,
        "1%",
        color="#A32020",
        ha="right",
        va="bottom",
        fontweight="bold",
    )
    axis.bar_label(depth_bars, labels=[f"{v:.4f}%" for v in depth], padding=3)
    axis.bar_label(point_bars, labels=[f"{v:.4f}%" for v in points], padding=3)
    axis.set_xticks(x, labels)
    axis.set_ylabel("系列内で2介入の誤差を平均した後の絶対相対変化（%）")
    axis.set_ylim(0.0, 1.16)
    axis.grid(axis="y", color="#DDDDDD", linewidth=0.7)
    axis.set_axisbelow(True)
    axis.legend(frameon=False, ncol=3, loc="upper center")
    axis.set_title(
        "4系列すべてで，二つの評価指標が事前の1%基準を下回った",
        fontsize=14,
        fontweight="bold",
        pad=14,
    )
    fig.savefig(
        output_dir / "recal3r_write_recording_effect.png",
        bbox_inches="tight",
    )
    plt.close(fig)


def plot_event_effect(results: dict, output_dir: Path) -> None:
    event_by_key = {
        (event["recording"], event["intervention"]): event
        for event in results["events"]
    }
    event_order = [
        (recording, intervention)
        for recording in RECORDING_ORDER
        for intervention in INTERVENTION_ORDER
    ]
    y = np.arange(len(event_order))
    y_labels = [
        f"{recording.removeprefix('walking ')}  {intervention}"
        for recording, intervention in event_order
    ]
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(13.6, 6.6),
        sharex=True,
        sharey=True,
    )
    fig.subplots_adjust(
        left=0.18,
        right=0.98,
        bottom=0.16,
        top=0.82,
        wspace=0.08,
    )
    for axis, endpoint, title in (
        (axes[0], "depth", "奥行き AbsRel"),
        (axes[1], "aligned_3d_point", "位置合わせ後の3D点誤差"),
    ):
        values = np.asarray(
            [
                event_by_key[key]["signed_effect_percent"][endpoint]
                for key in event_order
            ]
        )
        colors = ["#3979A8" if value >= 0 else "#D05B3F" for value in values]
        bars = axis.barh(y, values, color=colors, height=0.66)
        axis.axvline(0.0, color="#333333", linewidth=1.1)
        axis.set_xlim(-0.62, 3.05)
        axis.set_xlabel("符号付き効果（%）")
        axis.set_title(title, fontweight="bold", pad=10)
        axis.grid(axis="x", color="#DDDDDD", linewidth=0.7)
        axis.set_axisbelow(True)
        for bar, value in zip(bars, values):
            if value < -0.15:
                text_x = value / 2.0
                horizontal_alignment = "center"
                text_color = "white"
                display_label = f"{value:+.3f}%"
                label_size = 8.0
            elif value < 0:
                text_x = value - 0.05
                horizontal_alignment = "right"
                text_color = "#222222"
                display_label = f"{value:+.4f}%"
                label_size = 8.8
            else:
                text_x = value + 0.055
                horizontal_alignment = "left"
                text_color = "#222222"
                display_label = f"{value:+.4f}%"
                label_size = 8.8
            axis.text(
                text_x,
                bar.get_y() + bar.get_height() / 2,
                display_label,
                ha=horizontal_alignment,
                va="center",
                fontsize=label_size,
                color=text_color,
            )
    axes[0].set_yticks(y, y_labels)
    axes[0].invert_yaxis()
    fig.suptitle(
        "一回の書き込み効果は観測時点で異なった",
        fontsize=15,
        fontweight="bold",
        y=0.97,
    )
    fig.text(
        0.5,
        0.035,
        "正：通常の書き込みが次画像の誤差を減らした　　負：書き込みを止めた方が誤差を減らした",
        ha="center",
        fontsize=10,
        color="#333333",
    )
    fig.savefig(
        output_dir / "recal3r_write_event_effect.png",
        bbox_inches="tight",
    )
    plt.close(fig)


def _masked(array: np.ndarray, valid: np.ndarray) -> np.ma.MaskedArray:
    return np.ma.array(array, mask=~valid)


def plot_qualitative(packet: dict[str, np.ndarray], output_dir: Path) -> None:
    valid = packet["valid_mask"].astype(bool)
    rgb = packet["next_image_rgb"].copy()
    rgb[~valid] = np.asarray([145, 145, 145], dtype=np.uint8)
    ground_truth = packet["ground_truth_depth"]
    normal_depth = packet["normal_write_aligned_depth"]
    disabled_depth = packet["disabled_write_aligned_depth"]
    normal_error = packet["normal_write_absrel_error"]
    disabled_error = packet["disabled_write_absrel_error"]
    difference = packet["error_difference_disabled_minus_normal"]

    depth_values = np.concatenate(
        [ground_truth[valid], normal_depth[valid], disabled_depth[valid]]
    )
    depth_min, depth_max = np.percentile(depth_values, (1.0, 99.0))
    error_values = np.concatenate([normal_error[valid], disabled_error[valid]])
    error_max = float(np.percentile(error_values, 99.0))
    difference_max = float(np.percentile(np.abs(difference[valid]), 99.0))

    depth_cmap = plt.colormaps["viridis"].copy()
    error_cmap = plt.colormaps["magma"].copy()
    difference_cmap = plt.colormaps["coolwarm"].copy()
    for cmap in (depth_cmap, error_cmap, difference_cmap):
        cmap.set_bad("#919191")

    fig = plt.figure(figsize=(15.8, 8.8))
    grid = fig.add_gridspec(
        2,
        4,
        left=0.035,
        right=0.965,
        bottom=0.11,
        top=0.83,
        hspace=0.27,
        wspace=0.20,
    )
    axes = [fig.add_subplot(grid[row, column]) for row in range(2) for column in range(4)]
    axes[0].imshow(rgb)
    axes[0].set_title("次のRGB画像")
    gt_image = axes[1].imshow(
        _masked(ground_truth, valid),
        cmap=depth_cmap,
        vmin=depth_min,
        vmax=depth_max,
    )
    axes[1].set_title("正解奥行き")
    axes[2].imshow(
        _masked(normal_depth, valid),
        cmap=depth_cmap,
        vmin=depth_min,
        vmax=depth_max,
    )
    axes[2].set_title("通常の書き込み：位置合わせ後")
    axes[3].imshow(
        _masked(disabled_depth, valid),
        cmap=depth_cmap,
        vmin=depth_min,
        vmax=depth_max,
    )
    axes[3].set_title("書き込み停止：位置合わせ後")
    normal_image = axes[4].imshow(
        _masked(normal_error, valid),
        cmap=error_cmap,
        vmin=0.0,
        vmax=error_max,
    )
    axes[4].set_title("通常の書き込み：画素別AbsRel")
    axes[5].imshow(
        _masked(disabled_error, valid),
        cmap=error_cmap,
        vmin=0.0,
        vmax=error_max,
    )
    axes[5].set_title("書き込み停止：画素別AbsRel")
    difference_image = axes[6].imshow(
        _masked(difference, valid),
        cmap=difference_cmap,
        vmin=-difference_max,
        vmax=difference_max,
    )
    axes[6].set_title("AbsRel差：停止 − 通常")
    axes[7].axis("off")
    axes[7].text(
        0.04,
        0.78,
        "差分図の符号",
        fontsize=12,
        fontweight="bold",
        transform=axes[7].transAxes,
    )
    axes[7].text(
        0.04,
        0.58,
        "赤（正）\n書き込みを止めると誤差が増えた",
        color="#A32626",
        fontsize=10.5,
        transform=axes[7].transAxes,
    )
    axes[7].text(
        0.04,
        0.34,
        "青（負）\n書き込みを止めると誤差が減った",
        color="#245A9B",
        fontsize=10.5,
        transform=axes[7].transAxes,
    )
    axes[7].text(
        0.04,
        0.12,
        "灰色：正解上の無効画素",
        color="#555555",
        fontsize=10,
        transform=axes[7].transAxes,
    )
    for axis in axes[:7]:
        axis.set_xticks([])
        axis.set_yticks([])
        for spine in axis.spines.values():
            spine.set_visible(False)
    depth_colorbar = fig.colorbar(
        gt_image,
        ax=axes[1:4],
        orientation="horizontal",
        fraction=0.045,
        pad=0.06,
    )
    depth_colorbar.set_label("共通表示範囲の奥行き")
    error_colorbar = fig.colorbar(
        normal_image,
        ax=axes[4:6],
        orientation="horizontal",
        fraction=0.045,
        pad=0.06,
    )
    error_colorbar.set_label("共通表示範囲の画素別AbsRel")
    difference_colorbar = fig.colorbar(
        difference_image,
        ax=axes[6],
        orientation="horizontal",
        fraction=0.045,
        pad=0.06,
    )
    difference_colorbar.set_label("停止 − 通常")
    fig.suptitle(
        "事後選択した例：walking xyz，11枚目→12枚目",
        fontsize=15,
        fontweight="bold",
        y=0.965,
    )
    fig.text(
        0.5,
        0.885,
        "8介入時点のうち奥行きの正の効果が最大だった例であり，独立な検証例ではない",
        ha="center",
        fontsize=10.5,
        color="#444444",
    )
    fig.savefig(
        output_dir / "recal3r_write_qualitative.png",
        bbox_inches="tight",
    )
    plt.close(fig)


def render_all(
    results: dict, packet: dict[str, np.ndarray], output_dir: Path
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_intervention_design(output_dir)
    plot_recording_effect(results, output_dir)
    plot_event_effect(results, output_dir)
    plot_qualitative(packet, output_dir)


def decoded_pixels(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGBA")).copy()


def validate_deterministic_pngs(
    results: dict, packet: dict[str, np.ndarray]
) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        comparison_dir = Path(temporary)
        render_all(results, packet, comparison_dir)
        for name in FIGURE_NAMES:
            expected_path = FIGURE_DIR / name
            comparison_path = comparison_dir / name
            assert expected_path.exists() and expected_path.stat().st_size > 10_000
            expected_pixels = decoded_pixels(expected_path)
            comparison_pixels = decoded_pixels(comparison_path)
            assert expected_pixels.shape == comparison_pixels.shape, name
            assert np.array_equal(expected_pixels, comparison_pixels), name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate data, recompute the gate, and check deterministic PNG pixels",
    )
    args = parser.parse_args()

    results, packet = load_public_data()
    validate_public_data(results, packet)
    configure_style()
    render_all(results, packet, FIGURE_DIR)
    if args.check:
        validate_deterministic_pngs(results, packet)
        print(
            "CHECK_OK: 4 recordings, 8 events, frozen gate, qualitative "
            "metadata, and deterministic PNG pixels are consistent"
        )


if __name__ == "__main__":
    main()
