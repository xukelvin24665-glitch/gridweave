# Research and provenance

Reviewed on 24 October 2026. Sources justify modeling choices; they do not validate this project's synthetic savings.

1. **Radovanovic et al., “Carbon-Aware Computing for Datacenters” (2021).** [Paper and abstract](https://arxiv.org/abs/2106.11750). Describes Google's approach to delaying temporally flexible work using forecasts and capacity curves. Supports separating flexible from time-sensitive workloads and evaluating forecast-aware control. GridWeave is an independent, much smaller synthetic co-scheduling model and does not reproduce Google's system or its results.
2. **NREL, 2024 Annual Technology Baseline, Utility-Scale PV-Plus-Battery.** [Official ATB page](https://atb.nrel.gov/electricity/2024/utility-scale_pv-plus-battery). Uses an 85% battery round-trip efficiency assumption in its charging-cost discussion. GridWeave selects approximately 85% as an illustrative starting point and stress-tests 72.25%; its scale, capital costs, and battery wear coefficients are not taken from that project.
3. **SciPy `scipy.optimize.milp` reference.** [Official documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html). Specifies MILP formulation, integrality, `mip_rel_gap`, solver statuses, `mip_dual_bound`, and `mip_gap`. GridWeave uses these actual outputs rather than inferring optimality from a successful run.

The contest's Track 2 problem statement supplies the task: coordinate changing compute demand, power supply, and tariffs; explain objectives, baselines, optimality evidence, robustness, and assumptions. It provides no dataset. The included GitHub tutorial supplies repository workflow and public judge-access expectations. Documents were treated as task context rather than permission to publish, create accounts, or execute their illustrative commands.

All default prices, carbon intensities, job reservations, inference demand, wind/solar profiles, facility size, PUE, grid limits, wear cost, and peak fees are generated or selected by this project. They are **not measured**, are **not Huawei or Hithium data**, and do not represent a named electricity market. The seed and complete generated input are exported with every demonstration.

The repository excludes the original contest PDFs, personal filesystem paths, credentials, and personal account details. No external fonts, image assets, analytics, or browser libraries are loaded by the dashboard.
