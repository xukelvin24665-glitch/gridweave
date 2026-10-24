"""Render honest submission graphics from committed results and an actual test log.

Optional authoring dependencies: matplotlib and Pillow. No impact on app runtime.
"""

import json
from pathlib import Path
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission"
EVIDENCE = OUT / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)
MAIN = json.loads((ROOT / "results/benchmark.json").read_text())
DEMO = json.loads((ROOT / "results/demo.json").read_text())
HOLDOUT = json.loads((ROOT / "results/holdout/benchmark.json").read_text())
PAPER, INK, GREEN, LIME, MUTED = "#f6f7f2", "#193b2b", "#287a4c", "#b5ce83", "#74816e"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.spines.left": False, "axes.spines.bottom": False,
                     "axes.labelcolor": MUTED, "xtick.color": MUTED,
                     "ytick.color": INK, "figure.facecolor": PAPER,
                     "axes.facecolor": PAPER, "text.color": INK})


def font(size, bold=False, mono=False):
    prop = font_manager.FontProperties(family="DejaVu Sans Mono" if mono else "DejaVu Sans",
                                       weight="bold" if bold else "normal")
    return ImageFont.truetype(font_manager.findfont(prop), size)


def thumbnail():
    image = Image.new("RGB", (1600, 900), INK)
    draw = ImageDraw.Draw(image)
    draw.text((90, 72), "ENERGY + COMPUTE, IN SYNC", font=font(21, True), fill="#b5ce83")
    draw.text((86, 176), "GridWeave.", font=font(104, True), fill="#f6f7f2")
    draw.text((92, 343), "Smarter compute.", font=font(56), fill="#f6f7f2")
    draw.text((92, 414), "Cleaner power.", font=font(56), fill="#d4ed9a")
    draw.text((94, 527), "AI workloads. Renewable power. Battery storage.", font=font(22), fill="#afc3ac")
    draw.text((94, 563), "One coordinated schedule.", font=font(22), fill="#afc3ac")
    draw.line((94, 737, 1506, 737), fill="#3a5d47", width=2)
    draw.text((94, 786), "HACKSHSID 2026  /  SUSTAINABILITY", font=font(19, True), fill="#b5ce83")
    draw.text((1166, 786), "SYNTHETIC DEMO", font=font(17), fill="#afc3ac")
    box = (910, 165, 1510, 655)
    draw.rounded_rectangle(box, radius=28, fill="#254d38", outline="#3a5d47", width=2)
    draw.text((950, 203), "POWER FOLLOWS POSSIBILITY", font=font(18, True), fill="#d4ed9a")
    left, right, top, bottom = 954, 1468, 285, 529
    for i in range(4):
        y = top + i * (bottom - top) / 3
        draw.line((left, y, right, y), fill="#3a5d47", width=1)
    s = DEMO["scenario"]
    p = DEMO["policies"]["rolling_mpc"]["schedule"]
    f = s["facility"]
    renew = s["renewable_mw"]
    demand = [f["pue"] * (f["idle_it_mw"] + f["mw_per_gpu"] *
              (s["inference_gpus"][t] + sum(row[t] for row in p["allocation_gpus"]))) for t in range(24)]
    maximum = max(renew + demand) * 1.15
    points = lambda values: [(left + i * (right - left) / 23, bottom - v / maximum * (bottom - top)) for i, v in enumerate(values)]
    draw.polygon([(left, bottom)] + points(renew) + [(right, bottom)], fill="#4e7047")
    draw.line(points(renew), fill="#d4ed9a", width=5, joint="curve")
    draw.line(points(demand), fill="#f6f7f2", width=4, joint="curve")
    draw.text((left, 551), "00:00", font=font(16), fill="#afc3ac")
    draw.text((right - 48, 551), "23:00", font=font(16), fill="#afc3ac")
    draw.rectangle((956, 605, 978, 610), fill="#d4ed9a")
    draw.text((989, 594), "Renewable", font=font(17), fill="#d4ed9a")
    draw.rectangle((1240, 605, 1262, 610), fill="#f6f7f2")
    draw.text((1274, 594), "Facility load", font=font(17), fill="#f6f7f2")
    image.save(OUT / "gridweave-thumbnail.png", optimize=True)


def stress_chart():
    fig, ax = plt.subplots(figsize=(13.6, 8), dpi=160)
    fig.subplots_adjust(left=.22, right=.92, top=.77, bottom=.18)
    keys = list(MAIN["summaries"])
    labels = ["Balanced day", "Cloudy day", "Evening price spike", "Tight deadlines",
              "Forecast shock", "Grid connection stress", "Lower battery efficiency"]
    ys = np.arange(len(keys))
    for offset, metric, color, label in [(-.18, "cost_savings_pct", GREEN, "Operating cost savings"),
                                        (.18, "carbon_savings_pct", LIME, "Grid emissions savings")]:
        values = [MAIN["summaries"][k][metric] for k in keys]
        means = np.array([v["mean"] for v in values])
        errors = np.array([[v["mean"] - v["ci95_low"] for v in values],
                           [v["ci95_high"] - v["mean"] for v in values]])
        ax.barh(ys + offset, means, height=.3, color=color, label=label, zorder=3)
        ax.errorbar(means, ys + offset, xerr=errors, color=INK, capsize=3, fmt="none", lw=1, zorder=4)
        for y, value in zip(ys + offset, means):
            ax.text(value + 2.5, y, f"{value:.1f}%", va="center", fontsize=11, color=INK)
    ax.set_yticks(ys, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 85)
    ax.set_xticks([0, 20, 40, 60, 80], ["0%", "20%", "40%", "60%", "80%"])
    ax.tick_params(axis="both", length=0, pad=10)
    ax.grid(axis="x", color="#dfe5d7", zorder=0)
    ax.set_xlabel("Paired improvement over immediate EDF execution", labelpad=15)
    fig.text(.06, .935, "Seven conditions. One transparent comparison.", fontsize=24, weight="bold")
    fig.text(.06, .882, "Rolling control vs immediate execution · 20 seeds per condition · 95% confidence intervals", fontsize=12, color=MUTED)
    ax.legend(loc="lower left", bbox_to_anchor=(-.01, 1.035), ncol=2, frameon=False, fontsize=11)
    fig.text(.06, .078, "140/140 scenarios feasible for every policy. Default battery: 2.4 MWh. Carbon value: $80/tonne.", fontsize=11)
    fig.text(.06, .04, "Synthetic data only. Intervals describe seed variability; they do not establish real-world performance.", fontsize=10, color=MUTED)
    fig.savefig(EVIDENCE / "02-stress-tests.png", facecolor=PAPER)
    plt.close(fig)


def policy_chart():
    keys = ["immediate_edf", "compute_only", "battery_only", "joint_oracle", "rolling_mpc"]
    labels = ["Immediate EDF", "Compute only\n(perfect forecast)", "Battery only\n(perfect forecast)",
              "Joint oracle\n(perfect forecast)", "GridWeave rolling\n(uncertain forecasts)"]
    colors = ["#b5beae", "#8aa481", "#6c9474", LIME, GREEN]
    fig, axes = plt.subplots(1, 2, figsize=(14, 8.6), dpi=150, sharey=True)
    fig.subplots_adjust(left=.22, right=.94, top=.77, bottom=.2, wspace=.3)
    y = np.arange(5)
    for ax, metric, title, maximum in [(axes[0], "operating_cost_usd", "Operating cost (USD)", 730),
                                        (axes[1], "carbon_kg", "Grid emissions (kg CO2)", 4550)]:
        values = [DEMO["policies"][k]["metrics"][metric] for k in keys]
        ax.barh(y, values, height=.56, color=colors, zorder=3)
        ax.set_xlim(0, maximum)
        ax.tick_params(axis="both", length=0, pad=12)
        ax.grid(axis="x", color="#dfe5d7", zorder=0)
        ax.set_title(title, loc="left", fontsize=13, pad=22, weight="bold")
        for yi, v in zip(y, values):
            text = f"${v:,.2f}" if metric == "operating_cost_usd" else f"{v:,.0f}"
            ax.text(v + maximum * .025, yi, text, va="center", fontsize=11)
    axes[0].set_yticks(y, labels)
    axes[0].invert_yaxis()
    fig.text(.06, .936, "Same workload. Different dispatch.", fontsize=25, weight="bold")
    fig.text(.06, .879, "Default synthetic day · seed 42 · 24 hours · 16/16 jobs on time for all five policies", fontsize=12, color=MUTED)
    m = DEMO["savings_vs_immediate"]
    fig.text(.06, .105, f"Rolling result: {m['cost_pct']:.1f}% lower operating cost and {m['carbon_pct']:.1f}% fewer grid emissions vs immediate EDF.", fontsize=12, weight="bold")
    fig.text(.06, .061, "Operating cost includes energy, battery wear, and peak fees; capital costs are excluded.", fontsize=10, color=MUTED)
    fig.text(.06, .031, "Oracle bounds apply to the model. Rolling control has no global optimality guarantee. All inputs are synthetic.", fontsize=10, color=MUTED)
    fig.savefig(EVIDENCE / "03-policy-comparison.png", facecolor=PAPER)
    plt.close(fig)


def test_log():
    text = (EVIDENCE / "unit-tests.txt").read_text()
    lines = text.splitlines()
    assert lines[-1].strip() == "OK", "Evidence must use an actual passing test log"
    tests = [line for line in lines if line.startswith("test_")]
    assert len(tests) == 26
    summary = next(line for line in lines if line.startswith("Ran 26 tests"))
    image = Image.new("RGB", (1800, 1320), PAPER)
    draw = ImageDraw.Draw(image)
    draw.text((75, 53), "TESTED, WITH THE LOG TO PROVE IT", font=font(22, True), fill=GREEN)
    draw.text((70, 105), "26 tests passed.", font=font(65, True), fill=INK)
    draw.text((75, 198), "Actual local run · 24 October 2026 · Python 3.13", font=font(23), fill=MUTED)
    draw.rounded_rectangle((70, 267, 1730, 1195), radius=20, fill="#182a21")
    draw.text((105, 296), "$ python -m unittest discover -s tests -v", font=font(22, mono=True), fill="#d4ed9a")
    y = 354
    for line in tests:
        # Exact test names from the captured log; verbose module path omitted for readability.
        name = line.split(" (", 1)[0]
        draw.text((105, y), name, font=font(20, mono=True), fill="#e2eadc")
        y += 27
    draw.text((105, y + 21), summary, font=font(22, mono=True), fill="#d4ed9a")
    draw.text((105, y + 57), "OK", font=font(26, True, mono=True), fill="#d4ed9a")
    total = len(MAIN["runs"]) + len(HOLDOUT["runs"])
    assert total == 280 and all(not r["errors"] for report in (MAIN, HOLDOUT) for r in report["runs"])
    draw.text((75, 1232), "Also validated: 280 synthetic cases / 1,400 feasible policy evaluations.", font=font(24, True), fill=INK)
    draw.text((75, 1276), "Full raw log: submission/evidence/unit-tests.txt. Real deployment performance is not measured.", font=font(19), fill=MUTED)
    image.save(EVIDENCE / "04-test-results.png", optimize=True)


thumbnail()
stress_chart()
policy_chart()
test_log()
shutil.copy2(ROOT / "docs/screenshots/dashboard.jpg", EVIDENCE / "01-dashboard.jpg")
for path in [OUT / "gridweave-thumbnail.png", *sorted(EVIDENCE.glob("*.png")), *sorted(EVIDENCE.glob("*.jpg"))]:
    assert path.stat().st_size < 5_000_000
    print(f"{path.relative_to(ROOT)}: {path.stat().st_size:,} bytes")
