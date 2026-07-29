#!/usr/bin/env python3
"""Validate the public Counter-World packet and regenerate its figures."""

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
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch  # noqa: E402
from PIL import Image  # noqa: E402


SUMMARY_PATH = ROOT / "data" / "counterworld_stage0_summary.json"
PACKET_PATH = ROOT / "data" / "counterworld_stage0_qualitative.npz"
FIGURE_DIR = ROOT / "figures"
FIGURE_NAMES = (
    "counterworld_geometry_and_reduction.png",
    "counterworld_viewpoint_example.png",
    "counterworld_measurement_gate.png",
)
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
            "font.size": 10.5,
            "axes.titlesize": 13,
            "axes.labelsize": 10.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 140,
            "savefig.dpi": 220,
            "savefig.facecolor": "white",
        }
    )


def load_public_data() -> tuple[dict, dict[str, np.ndarray]]:
    summary = json.loads(SUMMARY_PATH.read_text())
    with np.load(PACKET_PATH, allow_pickle=False) as packet:
        arrays = {name: packet[name] for name in packet.files}
    return summary, arrays


def validate_public_data(
    summary: dict, packet: dict[str, np.ndarray]
) -> None:
    assert summary["status"] == "complete_with_invalid_measurement"
    endpoints = summary["query_and_endpoints"]
    assert endpoints["near_depth_factor"] == 0.75
    assert endpoints["far_depth_factor"] == 1.4
    assert endpoints["required_relative_answer_margin"] == 0.2
    analytic = summary["analytic_result"]
    assert analytic["two_endpoints_define_full_segment"] is True
    assert analytic["one_world_and_query_define_both_endpoints"] is True
    assert analytic["uses_input_images_after_worlds_are_given"] is False

    run = summary["run_2"]
    assert run["calibration_scene_count"] == 64
    assert run["test_scene_count"] == 256
    assert run["journal_start_event_count"] == 320
    assert run["journal_completion_event_count"] == 320
    assert run["measurement_gate"] is False
    assert run["scientific_evidence"] is False
    measurement = run["measurement"]
    assert measurement["renderer_comparison_count"] == 768
    assert measurement["passed_renderer_comparison_count"] == 752
    assert measurement["failed_renderer_comparison_count"] == 16
    assert measurement["failed_calibration_scene_count"] == 8
    assert measurement["all_comparisons_were_required"] is True
    gates = measurement["gate_pass_counts"]
    assert gates == {
        "object_id_and_finite_depth_pattern": 768,
        "full_image_mutual_depth": 768,
        "spot_coverage": 768,
        "high_precision_reference_stability": 768,
        "vector_route_against_reference": 758,
        "scalar_route_against_reference": 754,
        "complete_comparison": 752,
    }
    failures = measurement["route_failure_counts_with_overlap"]
    assert failures == {
        "vector_rgb": 10,
        "scalar_rgb": 14,
        "vector_depth": 0,
        "scalar_depth": 0,
    }
    localization = measurement["failure_localization"]
    assert localization["failed_comparisons"] == 16
    assert localization["failed_scenes"] == 8
    assert localization["same_camera_failed_for_near_and_far_endpoints"] is True
    assert localization["maximum_error_object"] == "位置を固定した球"
    assert localization["maximum_error_region"] == "球の輪郭に最も近い検査点"
    maxima = measurement["maximum_absolute_errors"]
    assert max(maxima["vector_depth"], maxima["scalar_depth"]) < measurement[
        "route_depth_max_abs_threshold"
    ]
    assert max(maxima["vector_rgb"], maxima["scalar_rgb"]) > measurement[
        "route_rgb_max_abs_threshold"
    ]
    assert max(
        maxima["reference_256_512_depth"],
        maxima["reference_256_512_rgb"],
    ) < measurement["reference_stability_abs_threshold"]
    diagnostics = run["test_diagnostics_not_interpreted"]
    assert diagnostics["valid_scene_count"] == 256
    for name, count in diagnostics.items():
        if name != "valid_scene_count":
            assert count == 256

    expected_arrays = {
        "initial_near_rgb",
        "initial_far_rgb",
        "translated_near_rgb",
        "translated_far_rgb",
        "query_depth",
        "near_depth",
        "far_depth",
        "camera_translation",
    }
    assert set(packet) == expected_arrays
    for name in (
        "initial_near_rgb",
        "initial_far_rgb",
        "translated_near_rgb",
        "translated_far_rgb",
    ):
        assert packet[name].shape == (128, 128, 3)
        assert packet[name].dtype == np.float32
        assert np.isfinite(packet[name]).all()
    assert packet["camera_translation"].shape == (3,)
    query = float(packet["query_depth"])
    assert math.isclose(float(packet["near_depth"]), 0.75 * query)
    assert math.isclose(float(packet["far_depth"]), 1.40 * query)
    assert np.max(
        np.abs(packet["initial_near_rgb"] - packet["initial_far_rgb"])
    ) < 1.0e-10
    assert np.max(
        np.abs(packet["translated_near_rgb"] - packet["translated_far_rgb"])
    ) > 0.1


def _box(
    axis: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    text: str,
    facecolor: str,
    edgecolor: str,
    fontsize: float = 11,
) -> None:
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.018,rounding_size=0.018",
        linewidth=1.5,
        facecolor=facecolor,
        edgecolor=edgecolor,
        transform=axis.transAxes,
    )
    axis.add_patch(patch)
    axis.text(
        x + width / 2,
        y + height / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        fontweight="bold",
        transform=axis.transAxes,
    )


def _arrow(
    axis: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    color: str = "#333333",
) -> None:
    axis.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=15,
            linewidth=1.7,
            color=color,
            transform=axis.transAxes,
        )
    )


def plot_geometry_and_reduction(summary: dict, output_dir: Path) -> None:
    figure = plt.figure(figsize=(12.8, 7.6), constrained_layout=True)
    grid = figure.add_gridspec(2, 1, height_ratios=(1.04, 0.96))
    geometry = figure.add_subplot(grid[0, 0])
    reduction = figure.add_subplot(grid[1, 0])

    query_depth = 5.0
    near_depth = (
        summary["query_and_endpoints"]["near_depth_factor"] * query_depth
    )
    far_depth = (
        summary["query_and_endpoints"]["far_depth_factor"] * query_depth
    )
    radius_ratio = 0.0625
    near_radius = radius_ratio * near_depth
    far_radius = radius_ratio * far_depth
    tangent_slope = math.tan(math.asin(radius_ratio))

    geometry.plot(
        [0.0, 8.2],
        [0.0, tangent_slope * 8.2],
        color="#787878",
        linewidth=1.4,
        linestyle="--",
    )
    geometry.plot(
        [0.0, 8.2],
        [0.0, -tangent_slope * 8.2],
        color="#787878",
        linewidth=1.4,
        linestyle="--",
    )
    geometry.axvline(
        query_depth,
        color="#444444",
        linewidth=1.5,
        linestyle=":",
    )
    geometry.add_patch(
        Circle(
            (far_depth, 0.0),
            far_radius,
            facecolor="#F28E2B33",
            edgecolor="#D66F05",
            linewidth=2.5,
        )
    )
    geometry.add_patch(
        Circle(
            (near_depth, 0.0),
            near_radius,
            facecolor="#4C78A844",
            edgecolor="#315F91",
            linewidth=2.5,
        )
    )
    geometry.scatter(
        [0.0],
        [0.0],
        marker=">",
        s=190,
        color="#222222",
        zorder=5,
    )
    geometry.text(0.10, -0.12, "カメラ中心", ha="left", va="top")
    geometry.text(
        query_depth,
        0.60,
        "距離の問いの境界",
        ha="center",
        va="bottom",
        fontsize=10.5,
        color="#333333",
    )
    geometry.annotate(
        "近い候補\n中心距離 0.75倍\n半径も0.75倍",
        xy=(near_depth, near_radius),
        xytext=(2.35, 0.70),
        arrowprops={"arrowstyle": "->", "color": "#315F91"},
        color="#244D78",
        ha="center",
        fontsize=10.5,
    )
    geometry.annotate(
        "遠い候補\n中心距離 1.40倍\n半径も1.40倍",
        xy=(far_depth, far_radius),
        xytext=(7.05, -0.77),
        arrowprops={"arrowstyle": "->", "color": "#D66F05"},
        color="#A54E00",
        ha="center",
        fontsize=10.5,
    )
    geometry.text(
        4.15,
        -0.83,
        "同じ二本の視線に接するため，\n共有したカメラ中心からの投影は同じになる",
        ha="center",
        va="top",
        fontsize=10.8,
        color="#333333",
    )
    geometry.set_xlim(-0.35, 8.35)
    geometry.set_ylim(-1.02, 1.02)
    geometry.set_aspect("equal", adjustable="box")
    geometry.axis("off")
    geometry.set_title(
        "同じ画像でも，距離の答えは反対になり得る",
        fontweight="bold",
        pad=14,
    )

    reduction.axis("off")
    reduction.text(
        0.5,
        0.98,
        "連続な候補は，新しい出力機能になっているか",
        ha="center",
        va="top",
        fontsize=13,
        fontweight="bold",
        transform=reduction.transAxes,
    )
    _box(
        reduction,
        0.04,
        0.67,
        0.28,
        0.15,
        "近い端点と\n遠い端点",
        "#EAF2FA",
        "#315F91",
    )
    _box(
        reduction,
        0.68,
        0.67,
        0.28,
        0.15,
        "端点間の\n連続な全候補",
        "#F3EDFA",
        "#76539A",
    )
    _arrow(reduction, (0.34, 0.745), (0.66, 0.745), "#76539A")
    reduction.text(
        0.50,
        0.82,
        "中心と半径を同じ割合で補間",
        ha="center",
        fontsize=9.5,
        color="#5D3C7A",
        transform=reduction.transAxes,
    )

    _box(
        reduction,
        0.04,
        0.40,
        0.28,
        0.15,
        "任意の一候補と\n距離の問い",
        "#EAF6EE",
        "#3D7D4B",
    )
    _box(
        reduction,
        0.68,
        0.40,
        0.28,
        0.15,
        "固定倍率の\n二つの端点",
        "#FFF2E3",
        "#C96808",
    )
    _arrow(reduction, (0.34, 0.475), (0.66, 0.475), "#3D7D4B")
    reduction.text(
        0.50,
        0.55,
        "方向と見かけの大きさを保存",
        ha="center",
        fontsize=9.5,
        color="#2F683B",
        transform=reduction.transAxes,
    )

    _box(
        reduction,
        0.08,
        0.07,
        0.84,
        0.18,
        "どちらの変換も画像を見ない\n"
        "この球だけからなる設定では，連続区間を直接出す必要はない",
        "#FFF4F1",
        "#B54A3A",
        fontsize=11.2,
    )
    figure.suptitle(
        "純回転で残る距離の曖昧さと，出力表現の解析的還元",
        fontsize=16,
        fontweight="bold",
    )
    figure.savefig(
        output_dir / "counterworld_geometry_and_reduction.png",
        bbox_inches="tight",
    )
    plt.close(figure)


def _shared_crop(packet: dict[str, np.ndarray]) -> tuple[slice, slice]:
    images = [
        packet["initial_near_rgb"],
        packet["initial_far_rgb"],
        packet["translated_near_rgb"],
        packet["translated_far_rgb"],
    ]
    union = np.zeros(images[0].shape[:2], dtype=bool)
    for image in images:
        background = image[0, 0]
        union |= np.max(np.abs(image - background), axis=-1) > 0.01
    rows, columns = np.nonzero(union)
    assert rows.size > 0 and columns.size > 0
    padding = 12
    row_min = max(int(rows.min()) - padding, 0)
    row_max = min(int(rows.max()) + padding + 1, images[0].shape[0])
    column_min = max(int(columns.min()) - padding, 0)
    column_max = min(int(columns.max()) + padding + 1, images[0].shape[1])
    return slice(row_min, row_max), slice(column_min, column_max)


def plot_viewpoint_example(
    packet: dict[str, np.ndarray], output_dir: Path
) -> None:
    row_slice, column_slice = _shared_crop(packet)
    panels = (
        (
            packet["initial_near_rgb"],
            packet["initial_far_rgb"],
            "光学中心を共有し，回転だけが異なる入力",
            "中心距離と半径を比例させても，二つの投影は同じである",
        ),
        (
            packet["translated_near_rgb"],
            packet["translated_far_rgb"],
            "カメラを横へ移動した追加画像",
            "視差が生じ，紫の対象物体の位置が近い候補と遠い候補で分かれる",
        ),
    )
    figure, axes = plt.subplots(
        2,
        2,
        figsize=(10.8, 7.4),
        constrained_layout=True,
    )
    for row, (near, far, row_title, explanation) in enumerate(panels):
        axes[row, 0].imshow(
            np.clip(near[row_slice, column_slice], 0.0, 1.0),
            interpolation="nearest",
        )
        axes[row, 1].imshow(
            np.clip(far[row_slice, column_slice], 0.0, 1.0),
            interpolation="nearest",
        )
        axes[row, 0].set_title("距離の境界より近い3D候補")
        axes[row, 1].set_title("距離の境界より遠い3D候補")
        for axis in axes[row]:
            axis.set_xticks([])
            axis.set_yticks([])
            for spine in axis.spines.values():
                spine.set_visible(False)
        axes[row, 0].text(
            -0.04,
            0.5,
            row_title,
            rotation=90,
            ha="right",
            va="center",
            fontsize=11,
            fontweight="bold",
            transform=axes[row, 0].transAxes,
        )
        axes[row, 0].text(
            1.05,
            -0.10,
            explanation,
            ha="center",
            va="top",
            fontsize=10.2,
            color="#333333",
            transform=axes[row, 0].transAxes,
        )
    figure.suptitle(
        "一つの既知解による問題設定の図示",
        fontsize=16,
        fontweight="bold",
    )
    figure.text(
        0.5,
        0.015,
        "紫が距離を問う対象物体，黄緑が位置を固定した物体である．"
        "この図は問題設定の可視化であり，無効になった数値実験の成功証拠ではない．",
        ha="center",
        fontsize=9.5,
        color="#555555",
    )
    figure.savefig(
        output_dir / "counterworld_viewpoint_example.png",
        bbox_inches="tight",
    )
    plt.close(figure)


def plot_measurement_gate(summary: dict, output_dir: Path) -> None:
    measurement = summary["run_2"]["measurement"]
    passed = measurement["passed_renderer_comparison_count"]
    failed = measurement["failed_renderer_comparison_count"]
    total = measurement["renderer_comparison_count"]
    gates = measurement["gate_pass_counts"]
    maxima = measurement["maximum_absolute_errors"]

    figure = plt.figure(figsize=(12.2, 5.7), constrained_layout=True)
    grid = figure.add_gridspec(1, 2, width_ratios=(1.12, 0.88))
    bar_axis = figure.add_subplot(grid[0, 0])
    checklist = figure.add_subplot(grid[0, 1])

    bar_axis.barh(
        [0],
        [passed],
        color="#59A14F",
        edgecolor="white",
        height=0.42,
    )
    bar_axis.barh(
        [0],
        [failed],
        left=[passed],
        color="#D94F45",
        edgecolor="white",
        height=0.42,
    )
    bar_axis.text(
        passed / 2,
        0,
        f"RGB上限内\n{passed}比較",
        ha="center",
        va="center",
        color="white",
        fontsize=12,
        fontweight="bold",
    )
    bar_axis.annotate(
        f"上限超過\n{failed}比較",
        xy=(passed + failed / 2, 0.0),
        xytext=(passed - 100, 0.54),
        arrowprops={"arrowstyle": "->", "color": "#A92E28", "linewidth": 1.6},
        color="#A92E28",
        fontsize=11,
        fontweight="bold",
        ha="center",
    )
    bar_axis.set_xlim(0, total)
    bar_axis.set_ylim(-0.58, 0.82)
    bar_axis.set_yticks([])
    bar_axis.set_xlabel("計測器の事前検査で必須としたレンダラ比較")
    bar_axis.set_title(
        "768比較すべてが上限内である必要があった",
        fontweight="bold",
        pad=12,
    )
    bar_axis.grid(axis="x", color="#DDDDDD", linewidth=0.8)
    bar_axis.set_axisbelow(True)
    bar_axis.text(
        0.0,
        -0.40,
        "16比較のRGB誤差が事前上限を越えたため，2回目の実行全体を無効とした．",
        fontsize=10.5,
        color="#6D231F",
    )

    checklist.axis("off")
    checklist.set_title(
        "どの検査が通り，どこで止まったか",
        fontweight="bold",
        pad=12,
    )
    rows = (
        ("物体IDと交点距離の有限性", gates["object_id_and_finite_depth_pattern"]),
        ("全画素の相互距離検査", gates["full_image_mutual_depth"]),
        ("幾何から選んだ検査点の網羅", gates["spot_coverage"]),
        ("256/512-bit参照の安定性", gates["high_precision_reference_stability"]),
        ("両実装のRGBが参照上限内", gates["complete_comparison"]),
    )
    for index, (label, count) in enumerate(rows):
        y = 0.84 - index * 0.14
        complete = count == total
        color = "#3D7D4B" if complete else "#B43C33"
        facecolor = "#EAF6EE" if complete else "#FBE9E7"
        checklist.add_patch(
            FancyBboxPatch(
                (0.02, y - 0.045),
                0.09,
                0.09,
                boxstyle="round,pad=0.008,rounding_size=0.012",
                facecolor=facecolor,
                edgecolor=color,
                linewidth=1.2,
                transform=checklist.transAxes,
            )
        )
        checklist.text(
            0.065,
            y,
            "OK" if complete else "NG",
            ha="center",
            va="center",
            color=color,
            fontsize=10.5,
            fontweight="bold",
            transform=checklist.transAxes,
        )
        checklist.text(
            0.14,
            y,
            label,
            ha="left",
            va="center",
            fontsize=10.5,
            transform=checklist.transAxes,
        )
        checklist.text(
            0.96,
            y,
            f"{count} / {total}",
            ha="right",
            va="center",
            color=color,
            fontsize=10.5,
            fontweight="bold",
            transform=checklist.transAxes,
        )
    checklist.text(
        0.02,
        0.10,
        "最大RGB誤差　"
        f"{max(maxima['vector_rgb'], maxima['scalar_rgb']):.2e}"
        "　（上限 1.00e−12）\n"
        "最大交点距離誤差　"
        f"{max(maxima['vector_depth'], maxima['scalar_depth']):.2e}"
        "　（上限 1.00e−11）\n"
        "高精度参照の最大差　"
        f"{max(maxima['reference_256_512_depth'], maxima['reference_256_512_rgb']):.2e}",
        ha="left",
        va="bottom",
        fontsize=9.7,
        color="#333333",
        linespacing=1.55,
        transform=checklist.transAxes,
    )
    figure.suptitle(
        "2回目の実行は還元の失敗ではなく，計測系のRGB検査で無効になった",
        fontsize=16,
        fontweight="bold",
    )
    figure.savefig(
        output_dir / "counterworld_measurement_gate.png",
        bbox_inches="tight",
    )
    plt.close(figure)


def render_all(
    summary: dict,
    packet: dict[str, np.ndarray],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_geometry_and_reduction(summary, output_dir)
    plot_viewpoint_example(packet, output_dir)
    plot_measurement_gate(summary, output_dir)


def decoded_pixels(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGBA")).copy()


def validate_deterministic_pngs(
    summary: dict, packet: dict[str, np.ndarray]
) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        comparison_dir = Path(temporary)
        render_all(summary, packet, comparison_dir)
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
        help="validate public data and deterministic PNG pixels",
    )
    arguments = parser.parse_args()

    summary, packet = load_public_data()
    validate_public_data(summary, packet)
    configure_style()
    render_all(summary, packet, FIGURE_DIR)
    if arguments.check:
        validate_deterministic_pngs(summary, packet)
        print(
            "CHECK_OK: analytic scope, invalid measurement gate, "
            "qualitative packet, and three figures are consistent"
        )


if __name__ == "__main__":
    main()
