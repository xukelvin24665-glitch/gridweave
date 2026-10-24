# Reproducible experiment results

Paired percentages compare rolling control with immediate EDF on identical inputs. Student-t 95% confidence intervals describe synthetic seed variability, not uncertainty about real deployments. Failed comparisons are counted and listed; they are not silently assigned savings.

Carbon price: $80/tonne. Seeds: 100-119. All data is synthetic.

| Scenario | Valid paired runs | Cost saving, mean [95% CI] | CO2 saving, mean [95% CI] | Rolling objective regret vs oracle | Failed runs |
|---|---:|---:|---:|---:|---:|
| balanced | 20/20 | 39.67% [38.28, 41.06] | 26.68% [25.13, 28.22] | 1.03% [0.54, 1.52] | 0 |
| cloudy | 20/20 | 17.91% [17.54, 18.28] | 4.24% [3.83, 4.65] | 0.41% [0.33, 0.49] | 0 |
| price_spike | 20/20 | 72.03% [71.29, 72.76] | 26.68% [25.14, 28.23] | 1.02% [0.54, 1.51] | 0 |
| tight | 20/20 | 39.24% [38.17, 40.31] | 23.36% [22.09, 24.62] | 1.57% [1.13, 2.00] | 0 |
| forecast_shock | 20/20 | 16.20% [15.59, 16.81] | 9.59% [8.92, 10.26] | 2.32% [2.17, 2.47] | 0 |
| grid_stress | 20/20 | 31.18% [30.02, 32.34] | 16.69% [15.40, 17.99] | 2.66% [2.02, 3.30] | 0 |
| low_efficiency | 20/20 | 36.07% [34.69, 37.44] | 23.51% [21.91, 25.11] | 1.10% [0.65, 1.55] | 0 |

Savings include grid energy, the illustrative daily peak fee, and battery wear. CO2 is grid-import energy times the contemporaneous grid intensity, including battery charging. All on-time figures also require independent physical feasibility. The oracle bound applies to the stated model with perfect forecasts; rolling control has no global gap certificate.

See `benchmark.json` for every run, constraint validation, policy ablations, failure details, and solver bounds; `benchmark.csv` is a tidy policy-level export.
