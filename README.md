# AFM_Combinatorial_Libraries

Automated measurement of combinatorial thin-film libraries on an Asylum Research Jupiter AFM.
A library is a sample where composition or thickness changes along the surface. This code
drives the microscope over a grid of sites on the sample, measures at every site, analyses
each measurement, and writes one table with the results.

Two kinds of measurement are supported:

- **loop**: SS-PFM hysteresis loops (DART-PFM mode). Output: coercive voltages, imprint,
  loop height, and other loop parameters.
- **scan**: AC-mode topography frames. Output: roughness, grain size, and other surface
  descriptors.

The microscope is controlled through the MCP server `mcp-server-jupiter` (separate repository,
runs on the microscope PC). This repository contains the workflow, not the instrument driver.

## How it works

1. You write a **recipe** (YAML file): the list of sites (stage positions), what to measure at
   every site, and the imaging mode. Notebook `07` makes loop recipes, notebook `10` makes
   topography recipes.
2. You run the recipe with notebook `06`. A LangGraph graph visits the sites one by one:
   move the stage, place the tip or the scan frame, measure, read the instrument state,
   analyse the file, save a record.
3. At the end the run folder contains `results.csv` (one row per measurement) and
   `summary.json` (everything in one file).

The graph never changes the imaging mode. Before a run you load the mode by hand
(AC Air Topography or DART SS PFM), tune, set the setpoint, and engage. The graph checks
at the start that the loaded mode is the one the recipe asks for.

## Repository layout

```
recipes/            recipe YAML files (one per campaign)
runs/               one folder per run: recipe.json, session.json, records/, loops/ or frames/,
                    summary.json, results.csv
notebooks/          06 run a recipe, 07 make a loop recipe, 10 make a topography recipe,
                    10_tests offline checks
src/afm_lib/
  config.py         MCP server address, imaging modes (MODES), parameter bounds, tolerances,
                    run folder helpers
  schemas/          data contracts (pydantic): recipe, instrument state, loop/scan plans,
                    loop parameters, image metrics, sample frame
  states/           LangGraph state definitions
  graphs/           grid_search (visits sites), measure_site (one site), loop_analysis_graph,
                    image_analysis_graph
  nodes/            one file per graph node
  instrument/       MCP client (session.py)
  readers/          SciFiReaders service that reads .ibw files
  utils/            recipe builder, loop and image analysis, summary writer, geometry
```

## Recipe

```yaml
name: pzh_02_AlBN_13%_topo
context: AlBN 13% B, 200C, 56 min, 250nm
mode: AC Air Topography          # or "DART SS PFM"
sample_frame:                    # optional, see "Sample coordinates"
  origin_stage_m: [-0.0327, -0.0316]
  direction: [0.0113, -0.0314]
  axis: x
  mirror: false
sites:
  - {label: r0c00, x_stage_m: -0.0327, y_stage_m: -0.0316}
  - ...
per_site:
  - kind: scan                   # one topography frame per site
    scan_settings: {x_scan_center_m: 0.0, y_scan_center_m: 0.0,
                    scan_size_m: 1.0e-6, pixels: 256, scan_rate_hz: 1.0}
  # - kind: loop                 # or hysteresis loops at points inside the frame
  #   points_m: [[-1.0e-6, -1.0e-6], [1.0e-6, -1.0e-6]]
  #   loop_settings: {v_dc_max_v: 30.0, frequency_hz: 0.3, var0_phase: 0.0,
  #                   var1_pulsetime_s: 0.05, n_cycles: 3}
```

Rules:

- `points_m` (loops) and the scan centre (scans) are **offsets from the current scan-frame
  centre**. `(0, 0)` means the frame centre. A scan with a non-zero offset moves the frame,
  scans, and moves the frame back, so offsets do not add up.
- More than one frame per site: add more `kind: scan` steps.
- `mode` must be one of the names in `config.MODES`.

## Sample coordinates

Stage coordinates depend on how the sample is mounted. To compare measurements of different
modalities on the same sample, a recipe can declare a **sample frame**: the stage position of
a physical corner of the sample (origin), and a second stage position along one sample edge
(direction), with `axis` saying whether that edge is the sample x or y axis, and `mirror` if the
stage image of the sample is mirrored. The instrument still works in stage coordinates; the
summary writer adds `x_sample_m, y_sample_m` to every row of `results.csv`. Two runs that use
the same sample frame can be joined on these columns.

## Results

`results.csv`, one row per measurement:

- identity: `site_index, site_label, step_index, point_index`
- position: `x_stage_m, y_stage_m, x_sample_m, y_sample_m, x_probe_m, y_probe_m, feedback_on`
- loops (one row per branch `off_field` / `on_field`): `v_c_rising, v_c_falling, imprint_v,
  loop_width_v, loop_height_m, remnant_*, sat_*, response_offset_m, loop_area_per_cycle,
  direction, branch_rms_noise, quadrature_residual, phase_offset_deg`
- scans (one row per frame): `x_frame_m, y_frame_m, scan_size_m, pixels, scan_rate_hz,
  f_drive_hz, v_ac_v, setpoint_v, rq_m, ra_m, pv_m, skewness, kurtosis, n_levels,
  level_spacing_m, corr_length_m, psd_slope, psd_knee_m, grain_count, grain_radius_median_m,
  grain_radius_iqr_m, grain_radius_mean_m, grain_radius_std_m, grain_height_std_m,
  grain_coverage, amp_rel_std, phase_std_deg`

Raw data per measurement: `loops/<site>_step<k>_pt<n>/*.npy` (loop branches) or
`frames/<site>_step<k>_pt<n>/*.npy` (raw channels and the flattened height). `records/*.json`
holds the full instrument state at the time of every measurement.

Image analysis is deterministic (no LLM): plane and line flattening, roughness statistics,
height-level detection, autocorrelation length, PSD, watershed grain segmentation.
`feedback_on = False` in a row means the tip was not in contact; treat that measurement as
invalid.

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -e .
pip install scifireaders_mcp   # file reader used by readfile_node
```

Requirements: Python 3.11, the MCP server running on the microscope PC
(`http://127.0.0.1:8000/mcp`, see `config.py`), and the notebook running on the same PC
(it reads the `.ibw` files the instrument writes).

## Typical session

1. Load the imaging mode in the Asylum software, tune, set the setpoint, engage.
2. `07` (loops) or `10` (topography): read the sample corner and edge, read P0 and P1 of the
   grid, build the sites, check the preview, write the recipe.
3. `06`: load the recipe, run the graph. Watch the console: `[preflight]`, `[calibrate]`,
   `[next_site]`, `[run_scan]` / `[run_loop]`, `[record]`.
4. Open `runs/<timestamp>_<name>/results.csv`.

Smoke recipes for testing: `recipes/smoke_2site.yaml` (loops), `recipes/smoke_2site_ac.yaml`
(topography), two sites 1 mm apart.

## Current state (September 2026)

Working and tested on the instrument:

- loop grid (used for PLZT and AlScN libraries, up to 88 sites x 8 points)
- topography grid (smoke test with two sites; frames, records, results.csv, sample columns)
- sample frame with origin, direction, axis and mirror

Known limitations:

- The graph does not tune or engage. Retuning between sites is not implemented.
- The scan tool does not refuse to scan with the tip withdrawn; check `feedback_on`.
- Flattening in the image analysis is done along array rows after `readfile_node` rotates the
  image; the fast-scan direction should be verified.
- A command sent to the instrument within ~2 s after a frame ends is lost; the server waits
  for this. Do not remove that delay.
