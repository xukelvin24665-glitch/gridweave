"use strict";

const $ = (id) => document.getElementById(id);
const state = { data: null, chart: "power", query: "", busy: false };
const colors = { renewable: "#b6ce8f", load: "#306a45", grid: "#c38e57", baseline: "#aab3a2", charge: "#8cae59", discharge: "#c38e57" };
const escapeHtml = (v) => String(v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (v) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(v);
const number = (v, digits = 1) => Number(v).toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });
const hour = (v) => `${String(v).padStart(2, "0")}:00`;
const policyOrder = ["immediate_edf", "compute_only", "battery_only", "joint_oracle", "rolling_mpc"];

async function getJson(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function setBusy(busy) {
  state.busy = busy;
  document.body.classList.toggle("busy", busy);
  $("controls").querySelectorAll("input, select, button").forEach((el) => { el.disabled = busy; });
  $("frontier-run").disabled = busy || !state.data;
  $("export").disabled = busy || !state.data;
  $("run").textContent = busy ? "Calculating…" : "↗  Run experiment";
  $("run-status").classList.toggle("updating-indicator", busy);
}

function changeBadge(id, value) {
  const el = $(id);
  el.classList.toggle("negative", value != null && value < 0);
  el.textContent = value == null ? "No valid comparison" : `${value >= 0 ? "↓" : "↑"} ${number(Math.abs(value))}%`;
}

async function runExperiment(event) {
  if (event) event.preventDefault();
  if (state.busy || !$("controls").reportValidity()) return;
  const query = new URLSearchParams({ scenario: $("scenario").value, seed: $("seed").value,
    carbon_price: $("carbon").value, battery: $("battery").value }).toString();
  setBusy(true);
  $("error").hidden = true;
  $("run-status").textContent = "Solving five policies and checking every constraint…";
  const start = performance.now();
  try {
    state.data = await getJson(`/api/experiment?${query}`);
    state.query = query;
    render();
    const ours = state.data.policies.rolling_mpc;
    const valid = ours && ours.metrics.validation.valid;
    $("run-status").textContent = `${valid ? "✓ Constraint checks passed" : "Review feasibility below"} · ${number((performance.now() - start) / 1000, 2)}s`;
    $("frontier-chart").innerHTML = '<span class="frontier-symbol" aria-hidden="true">⌁</span><p>Six carbon values. One set of physical constraints.<br>Trace the perfect-forecast trade-off for this scenario.</p>';
  } catch (error) {
    $("error").textContent = error.message;
    $("error").hidden = false;
    $("run-status").textContent = state.data ? "Run failed · previous results shown" : "Run failed";
  } finally { setBusy(false); }
}

function render() {
  const d = state.data, s = d.scenario, f = s.facility;
  const ours = d.policies.rolling_mpc;
  $("context").textContent = `${s.name.replaceAll("_", " ")} · seed ${s.seed} · ${s.price_usd_per_mwh.length} hourly intervals · ${f.total_gpus.toLocaleString()} GPUs`;
  $("jobs-pill").textContent = `${s.jobs.length} RESERVED JOBS`;
  if (Object.keys(d.errors).length) {
    $("error").textContent = Object.entries(d.errors).map(([key, value]) => `${key}: ${value}`).join(" · ");
    $("error").hidden = false;
  }
  if (ours) {
    const m = ours.metrics;
    $("metric-cost").textContent = money(m.operating_cost_usd);
    $("metric-carbon").innerHTML = `${number(m.carbon_kg / 1000, 2)}<small>t CO₂</small>`;
    $("metric-service").innerHTML = `${m.jobs_on_time}<small>/ ${m.jobs_total}</small>`;
    $("service-label").textContent = m.validation.valid ? "✓ All service & power checks pass" : "! Constraint violation";
    $("metric-clean").innerHTML = `${number(m.renewable_input_pct, 1)}<small>%</small>`;
    $("clean-detail").textContent = `${number(m.renewable_used_mwh)} MWh of renewable input`;
    changeBadge("change-cost", d.savings_vs_immediate?.cost_pct);
    changeBadge("change-carbon", d.savings_vs_immediate?.carbon_pct);
    renderChart(); renderHeatmap(); renderInsights();
  } else {
    for (const id of ["metric-cost", "metric-carbon", "metric-service", "metric-clean"]) $(id).textContent = "Unavailable";
    $("service-label").textContent = "No feasible rolling schedule";
    $("dispatch-chart").textContent = "The rolling controller could not find a feasible schedule.";
    $("heatmap").textContent = "No rolling schedule available.";
    $("insights").textContent = "Inspect the reported failure and change the scenario assumptions.";
    $("clean-detail").textContent = "Unavailable";
    changeBadge("change-cost", null); changeBadge("change-carbon", null);
  }
  renderComparison(); renderCertificate();
}

function svgFrame(title, description, content, width = 800, height = 250) {
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(title)}"><title>${escapeHtml(title)}</title><desc>${escapeHtml(description)}</desc>${content}</svg>`;
}

function renderChart() {
  if (!state.data?.policies.rolling_mpc) return;
  const d = state.data, s = d.scenario, f = s.facility;
  const plan = d.policies.rolling_mpc.schedule;
  const n = s.price_usd_per_mwh.length;
  const flex = Array.from({ length: n }, (_, t) => plan.allocation_gpus.reduce((v, row) => v + row[t], 0));
  const baseline = d.policies.immediate_edf?.schedule;
  let series, unit, note;
  if (state.chart === "power") {
    series = [{ name: "Available renewable", values: s.renewable_mw, color: colors.renewable, area: true },
      { name: "Facility demand", values: flex.map((v, t) => f.pue * (f.idle_it_mw + f.mw_per_gpu * (v + s.inference_gpus[t]))), color: colors.load },
      { name: "Grid import", values: plan.grid_mw, color: colors.grid, dashed: true }];
    unit = "MW";
    note = "Facility demand includes cooling. Grid import can exceed demand while the battery charges. Surplus renewable may be curtailed.";
  } else if (state.chart === "compute") {
    series = [{ name: "Rolling flexible compute", values: flex, color: colors.load, area: true },
      { name: "Reserved inference", values: s.inference_gpus, color: colors.grid }];
    if (baseline) series.push({ name: "Immediate flexible compute", values: Array.from({ length: n }, (_, t) => baseline.allocation_gpus.reduce((v, row) => v + row[t], 0)), color: colors.baseline, dashed: true });
    unit = "GPUs";
    note = "GPU equivalents are divisible and preemptible. The same reserved inference profile runs in its original slots for every policy.";
  } else {
    series = [{ name: "Stored energy", values: plan.soc_mwh, color: colors.load, area: true }];
    unit = "MWh";
    note = `Battery reserve: ${number(f.battery_mwh * f.reserve_soc_fraction, 2)} MWh. Initial and final energy: ${number(f.battery_mwh * f.initial_soc_fraction, 2)} MWh. Round-trip efficiency: ${number(f.charge_efficiency * f.discharge_efficiency * 100, 1)}%.`;
  }
  $("chart-footnote").textContent = note;
  $("chart-legend").innerHTML = series.map((line) => `<span class="legend-item"><i class="legend-line${line.dashed ? " dashed" : ""}" data-color="${line.color}"></i>${line.name}</span>`).join("");
  $("chart-legend").querySelectorAll("i").forEach((el) => { el.style.backgroundColor = el.dataset.color; el.style.setProperty("--legend-color", el.dataset.color); });
  const W = Math.max(320, $("dispatch-chart").clientWidth - 30), H = 250, left = 43, right = 15, top = 22, bottom = 32;
  const plotW = W - left - right, plotH = H - top - bottom;
  const maxValue = Math.max(0.1, ...series.flatMap((v) => v.values)) * 1.12;
  const x = (t) => left + plotW * t / n, y = (v) => top + plotH * (1 - v / maxValue);
  let svg = `<text x="${left}" y="10" class="axis-label">${unit}</text>`;
  for (let i = 0; i <= 4; i++) {
    const value = maxValue * i / 4;
    svg += `<line x1="${left}" y1="${y(value)}" x2="${W - right}" y2="${y(value)}" class="grid-line"/><text x="${left - 10}" y="${y(value) + 3}" text-anchor="end" class="axis-label">${state.chart === "compute" ? Math.round(value) : value.toFixed(1)}</text>`;
  }
  for (let t = 0; t <= n; t += 3) svg += `<text x="${x(t)}" y="${H - 9}" text-anchor="middle" class="axis-label">${hour(t)}</text>`;
  for (const line of series) {
    const points = line.values.map((v, t) => [x(line.values.length === n + 1 ? t : t + 0.5), y(v)]);
    const path = points.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(2)},${p[1].toFixed(2)}`).join(" ");
    if (line.area) svg += `<path d="${path} L${points.at(-1)[0]},${y(0)} L${points[0][0]},${y(0)} Z" fill="${line.color}" opacity="${state.chart === "power" ? ".35" : ".11"}"/>`;
    svg += `<path d="${path}" fill="none" stroke="${line.color}" stroke-width="${line.dashed ? 1.8 : 2.4}" stroke-linejoin="round" ${line.dashed ? 'stroke-dasharray="5 4"' : ""}/>`;
  }
  for (let t = 0; t < n; t++) {
    const description = `${hour(t)}: ${series.map((line) => `${line.name} ${number(line.values[t], 2)} ${unit}`).join("; ")}`;
    svg += `<rect x="${x(t)}" y="${top}" width="${plotW / n}" height="${plotH}" fill="transparent"><title>${escapeHtml(description)}</title></rect>`;
  }
  $("dispatch-chart").innerHTML = svgFrame(`${state.chart} dispatch over 24 hours`, "Hover over an hour to inspect its values. Exact schedules are available in Export results.", svg, W, H);
}

function renderHeatmap() {
  const s = state.data.scenario, p = state.data.policies.rolling_mpc.schedule;
  const W = 1060, left = 226, top = 32, rowH = 27, colW = 30.5, H = top + rowH * s.jobs.length + 10;
  let svg = '<text x="0" y="13" fill="#8c9b80" font-size="9">WORKLOAD / GPU-HOURS</text>';
  for (let t = 0; t < 24; t++) svg += `<text x="${left + (t + 0.5) * colW}" y="13" text-anchor="middle" fill="#8c9b80" font-size="9">${String(t).padStart(2, "0")}</text>`;
  s.jobs.forEach((job, j) => {
    const y = top + j * rowH;
    svg += `<text x="0" y="${y + 12}" fill="#5a6e4f" font-size="10">${escapeHtml(job.name)}</text><text x="204" y="${y + 12}" text-anchor="end" fill="#9ca78f" font-size="9">${number(job.work_gpu_h, 0)}</text>`;
    for (let t = 0; t < 24; t++) {
      const value = p.allocation_gpus[j][t];
      const available = t >= job.release && t < job.deadline;
      const ratio = value / job.max_gpus;
      const fill = !available ? "#f5f6f1" : value < 0.01 ? "#eaf0e1" : `rgb(${Math.round(221 - ratio * 160)},${Math.round(233 - ratio * 110)},${Math.round(203 - ratio * 128)})`;
      const label = `${job.name}, ${hour(t)}, ${number(value)} of ${job.max_gpus} GPUs${available ? "" : ", outside allowed window"}`;
      svg += `<rect x="${left + t * colW}" y="${y}" width="${colW - 3}" height="17" rx="2" fill="${fill}"><title>${escapeHtml(label)}</title></rect>`;
    }
    svg += `<line x1="${left + job.deadline * colW - 1}" x2="${left + job.deadline * colW - 1}" y1="${y - 1}" y2="${y + 18}" stroke="#b39154" stroke-width="1.5"/>`;
  });
  $("heatmap").innerHTML = svgFrame("Workload execution heatmap", "Each row is a reserved job. Columns are hourly slots. Darker green indicates a higher GPU allocation. Gold ticks indicate deadlines. Hover over a cell for the exact GPU allocation. Export results provides all numeric values.", svg, W, H);
}

function renderInsights() {
  const d = state.data, s = d.scenario, p = d.policies.rolling_mpc.schedule;
  const flex = p.grid_mw.map((_, t) => p.allocation_gpus.reduce((v, row) => v + row[t], 0));
  const peakSlot = flex.indexOf(Math.max(...flex));
  const m = d.policies.rolling_mpc.metrics;
  const regret = d.rolling_regret_vs_oracle_pct;
  const lines = [
    `<strong>${hour(peakSlot)} · busiest flexible slot</strong><br>${number(flex[peakSlot], 0)} GPU equivalents allocated.`,
    `<strong>${number(m.battery_throughput_mwh)} MWh · battery throughput</strong><br>${number(m.battery_wear_usd, 2)} USD of modeled wear is included.`,
    `<strong>${regret == null ? "No valid oracle comparison" : `${number(regret)}% objective regret`}</strong><br>${regret == null ? "Review the reported solver failure." : "Rolling forecast compared with perfect foresight."}`,
  ];
  $("insights").innerHTML = lines.map((text, i) => `<div class="insight-item"><span class="insight-index">${i + 1}</span><span>${text}</span></div>`).join("");
}

function renderComparison() {
  const d = state.data;
  const sublabels = { immediate_edf: "Run ready work now · storage idle", compute_only: "Shift compute · no storage · perfect forecast", battery_only: "Immediate compute · optimized storage · perfect forecast", joint_oracle: "Joint schedule · perfect foresight", rolling_mpc: "Joint schedule · uncertain renewable forecasts" };
  $("comparison-body").innerHTML = policyOrder.map((key) => {
    const v = d.policies[key];
    if (!v) return `<tr><td>${escapeHtml(key)}<small>${escapeHtml(d.errors[key] || "Unavailable")}</small></td><td colspan="4">No feasible result</td></tr>`;
    const m = v.metrics, gap = v.schedule.solver.relative_gap;
    return `<tr class="${key === "rolling_mpc" ? "highlight" : ""}"><td><span class="row-dot"></span>${escapeHtml(v.label)}<small>${sublabels[key]}</small></td><td>${money(m.operating_cost_usd)}</td><td>${number(m.carbon_kg / 1000, 2)} t CO₂</td><td>${m.jobs_on_time}/${m.jobs_total}${m.validation.valid ? " ✓" : " · invalid"}</td><td>${gap == null ? "—" : `${number(gap * 100, 4)}%`}</td></tr>`;
  }).join("");
}

function renderCertificate() {
  const d = state.data, oracle = d.policies.joint_oracle;
  const ours = d.policies.rolling_mpc;
  const rows = [
    ["Oracle objective", oracle ? money(oracle.metrics.objective_usd) : "Unavailable"],
    ["Oracle lower bound", oracle ? money(oracle.schedule.solver.dual_bound_usd) : "Unavailable"],
    ["Oracle model gap", oracle ? `${number(oracle.schedule.solver.relative_gap * 100, 4)}%` : "Unavailable"],
    ["Rolling constraint residual", ours ? ours.metrics.validation.max_residual.toExponential(1) : "Unavailable"],
    ["Carbon value", `$${d.carbon_price_usd_per_tonne}/tonne`],
  ];
  $("certificate").innerHTML = rows.map(([key, value]) => `<div><dt>${key}</dt><dd>${value}</dd></div>`).join("");
}

async function traceFrontier() {
  if (!state.data || state.busy) return;
  const button = $("frontier-run"); button.disabled = true; button.textContent = "Tracing…";
  try {
    const { points } = await getJson(`/api/frontier?${state.query}`);
    state.data.frontier = points;
    const W = Math.max(320, $("frontier-chart").clientWidth - 35), H = 215, left = 55, right = 25, top = 28, bottom = 42;
    const costs = points.map((p) => p.operating_cost_usd), carbon = points.map((p) => p.carbon_kg / 1000);
    const xmin = Math.min(...carbon), xmax = Math.max(...carbon);
    const ymin = Math.min(...costs), ymax = Math.max(...costs);
    const xpad = Math.max((xmax - xmin) * 0.2, 0.01), ypad = Math.max((ymax - ymin) * 0.2, 1);
    const x = (v) => left + (v - xmin + xpad) / (xmax - xmin + 2 * xpad) * (W - left - right);
    const y = (v) => H - bottom - (v - ymin + ypad) / (ymax - ymin + 2 * ypad) * (H - top - bottom);
    let svg = `<text x="${left}" y="12" class="axis-label">Operating cost (USD)</text>`;
    for (let i = 0; i <= 3; i++) {
      const cost = ymin - ypad + (ymax - ymin + 2 * ypad) * i / 3;
      const c = xmin - xpad + (xmax - xmin + 2 * xpad) * i / 3;
      svg += `<line x1="${left}" x2="${W - right}" y1="${y(cost)}" y2="${y(cost)}" class="grid-line"/><text x="${left - 10}" y="${y(cost) + 3}" text-anchor="end" class="axis-label">${money(cost)}</text><text x="${x(c)}" y="${H - 24}" text-anchor="middle" class="axis-label">${number(c, 2)}</text>`;
    }
    svg += `<text x="${(W + left) / 2}" y="${H - 4}" text-anchor="middle" class="axis-label">Grid emissions (tonnes CO₂) · perfect forecast</text><path d="${points.map((p, i) => `${i ? "L" : "M"}${x(p.carbon_kg / 1000)},${y(p.operating_cost_usd)}`).join(" ")}" fill="none" stroke="#82a55b" stroke-width="2"/>`;
    points.forEach((p, i) => {
      svg += `<circle cx="${x(p.carbon_kg / 1000)}" cy="${y(p.operating_cost_usd)}" r="4" fill="#447e4b" stroke="#fff" stroke-width="2"><title>$${p.carbon_price_usd_per_tonne}/tonne: ${money(p.operating_cost_usd)}, ${number(p.carbon_kg / 1000, 3)} t CO2</title></circle>`;
      if (i === 0 || i === points.length - 1) svg += `<text x="${x(p.carbon_kg / 1000)}" y="${y(p.operating_cost_usd) - 10}" text-anchor="middle" fill="#6e8756" font-size="9">$${p.carbon_price_usd_per_tonne}/t</text>`;
    });
    $("frontier-chart").innerHTML = svgFrame("Cost and carbon trade-off frontier", "Each point is an optimal perfect-forecast schedule at a different carbon price. Exact values are included in Export results.", svg, W, H);
  } catch (error) { $("frontier-chart").textContent = error.message; }
  finally { button.disabled = false; button.textContent = "Trace the frontier ↗"; }
}

function exportResults() {
  if (!state.data) return;
  const blob = new Blob([JSON.stringify(state.data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob), a = document.createElement("a");
  a.href = url; a.download = `gridweave-${state.data.scenario.name}-${state.data.scenario.seed}.json`; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function loadEvidence() {
  try {
    const r = await getJson("/evidence.json");
    const total = Object.values(r.summaries).reduce((n, s) => n + s.attempted_seeds, 0);
    $("benchmark-evidence").innerHTML = `<h3>Beyond one good day · ${total} reproducible runs</h3><p>The committed benchmark uses seeds ${r.seed_range[0]}–${r.seed_range[1]} and $${r.carbon_price_usd_per_tonne}/tonne. These are saved results at the default 2.4 MWh battery, independent of the controls above. Intervals describe synthetic seed variability, not real-world confidence.</p><div class="table-scroll"><table><caption class="sr-only">Committed multi-seed stress test evidence</caption><thead><tr><th>Scenario</th><th>Paired runs</th><th>Cost savings · 95% CI</th><th>CO₂ savings · 95% CI</th><th>Failures</th></tr></thead><tbody>${Object.entries(r.summaries).map(([key, s]) => {
      const fmt = (v) => v.mean == null ? "Unavailable" : `${number(v.mean)}%${v.ci95_low == null ? "" : ` [${number(v.ci95_low)}, ${number(v.ci95_high)}]`}`;
      return `<tr><td>${escapeHtml(key.replaceAll("_", " "))}</td><td>${s.cost_savings_pct.n}/${s.attempted_seeds}</td><td>${fmt(s.cost_savings_pct)}</td><td>${fmt(s.carbon_savings_pct)}</td><td>${s.failures.length}</td></tr>`;
    }).join("")}</tbody></table></div>`;
  } catch { $("benchmark-evidence").textContent = "Run the benchmark command to generate the multi-seed evidence snapshot. See the repository README for instructions."; }
}

$("controls").addEventListener("submit", runExperiment);
$("carbon").addEventListener("input", () => { $("carbon-value").textContent = `$${$("carbon").value}/t`; });
$("battery").addEventListener("input", () => { $("battery-value").textContent = `${number($("battery").value)} MWh`; });
$("controls").addEventListener("input", () => { if (state.data) $("run-status").textContent = "Settings changed · run to apply"; });
$("export").addEventListener("click", exportResults);
$("frontier-run").addEventListener("click", traceFrontier);
document.querySelectorAll(".chart-tab").forEach((button) => button.addEventListener("click", () => {
  state.chart = button.dataset.chart;
  document.querySelectorAll(".chart-tab").forEach((b) => { const selected = b === button; b.classList.toggle("selected", selected); b.setAttribute("aria-pressed", selected); });
  renderChart();
}));
const observer = new IntersectionObserver((entries) => {
  for (const entry of entries) {
    if (entry.isIntersecting) document.querySelectorAll(".nav-link").forEach((link) => {
      const active = link.getAttribute("href") === `#${entry.target.id}`;
      link.classList.toggle("active", active);
      if (active) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
    });
  }
}, { rootMargin: "-10% 0px -65% 0px", threshold: 0 });
document.querySelectorAll("#overview, #workloads, #experiments, #method").forEach((section) => observer.observe(section));
new ResizeObserver(() => renderChart()).observe($("dispatch-chart"));
runExperiment(); loadEvidence();
