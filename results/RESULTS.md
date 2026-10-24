# Reproducible experiment results

Paired percentages compare rolling control with immediate EDF on identical inputs. Student-t 95% confidence intervals describe synthetic seed variability, not uncertainty about real deployments. Failed comparisons are counted and listed; they are not silently assigned savings.

Carbon price: $80/tonne. Seeds: 0-19. All data is synthetic.

| Scenario | Valid paired runs | Cost saving, mean [95% CI] | CO2 saving, mean [95% CI] | Rolling objective regret vs oracle | Failed runs |
|---|---:|---:|---:|---:|---:|
| balanced | 20/20 | 39.80% [38.43, 41.17] | 26.57% [25.23, 27.90] | 1.56% [1.09, 2.02] | 0 |
| cloudy | 20/20 | 17.78% [17.46, 18.09] | 4.19% [3.91, 4.47] | 0.42% [0.33, 0.50] | 0 |
| price_spike | 20/20 | 71.98% [71.33, 72.62] | 26.61% [25.26, 27.96] | 1.48% [1.04, 1.92] | 0 |
| tight | 20/20 | 39.68% [38.54, 40.82] | 23.81% [22.56, 25.05] | 1.67% [1.17, 2.16] | 0 |
| forecast_shock | 20/20 | 15.62% [14.82, 16.42] | 9.31% [8.70, 9.91] | 2.64% [2.44, 2.84] | 0 |
| grid_stress | 20/20 | 31.15% [29.88, 32.42] | 16.60% [15.39, 17.81] | 2.79% [2.14, 3.44] | 0 |
| low_efficiency | 20/20 | 36.26% [34.88, 37.65] | 23.52% [22.23, 24.80] | 1.67% [1.28, 2.06] | 0 |

Savings include grid energy, the illustrative daily peak fee, and battery wear. CO2 is grid-import energy times the contemporaneous grid intensity, including battery charging. All on-time figures also require independent physical feasibility. The oracle bound applies to the stated model with perfect forecasts; rolling control has no global gap certificate.

See `benchmark.json` for every run, constraint validation, policy ablations, failure details, and solver bounds; `benchmark.csv` is a tidy policy-level export.
