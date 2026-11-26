# AI assistance and verification log

- Request: build a research prototype from the user's proposal to separate live defender CPU testing from reusable GPU attacker profiles. Design/code/README/test scaffolding generated with ChatGPT; user review required before submission.
- Primary experimental sources: user-supplied `exp8_full.zip` and `exp8_confirm_20.zip`; original benchmark source from `Argon2_Experiment_8.zip`. Source digests are recorded in the profile and `validation/*_provenance.json`. No fabricated GPU values were used. Rebuilt profile from raw CSV and logs, checked exact configuration membership, complete unique rounds, known-input verification record, actual device labels and per-run median after discarding the initial status sample.
- Known-answer check: the original Experiment 8 published Hashcat Argon2id vector passes locally using argon2-cffi. This is a test of the library integration, not new cryptographic analysis. See original Experiment 8 audit for vector provenance.
- Local verification: five automated unit tests passed (profile counts, multi-profile missing data and worst observation, invalid data rejection, policy, resource constraints); deterministic historical replay completed; two actual local CPU smoke runs returned a recommendation and generated output; Windows launcher and user's full live optimization not yet run here. Python dependencies tested: argon2-cffi 25.1.0, psutil 7.2.2.
- Decisions: default Argon2id policy floor 64 MiB/3 passes with RFC high-memory exception; optional relaxed research mode; default 100 ms/256 MiB/four workers; max-observed GPU objective, independently repeated local confirmation, common coverage for multiple profiles, conservative observed constraint envelope, exploratory bootstrap only. These choices are prototype policies, not validated guarantees.
- Validation caveat: replay is same-data algorithm validation; matching oracle is by construction, counts are not elapsed-time improvement; CPU-only comparison is illustrative, not a tested competitor. Source-code novelty review incomplete. No new GPU experiments or external hardware validation performed in this development step. Optional collection and online community database remain out of scope.
- Human verification needed: run Windows self-test and optimizer on actual target system, compare output against expected constraints and logs, verify citations and novelty, review source code, and disclose AI use per course rubric.

## Desktop packaging extension
- AI claim: desktop front end preserves the existing optimizer and bundled profile; verification: original optimizer/profile files unchanged, five original unit tests pass, GUI input conversion and invalid-worker rejection checked, child worker known-answer test and one-candidate live optimization passed in Linux.
- AI claim: Windows build script packages a single-file executable with bundled Python runtime and GPU profile; verification pending on Windows. No native Windows executable was built in the Linux preparation environment. Final GUI display and executable distribution need independent Windows verification. Do not report them as completed tests.

## v2.0 multi-objective desktop extension
- User request: five mode tabs and dark theme. Implemented objective-specific selection, empirical GPU ceiling for responsiveness/resource efficiency, confirmed ranking and seven-metric Pareto frontier. Default policy and stored GPU profile remain unchanged.
- Decisions: balanced objective = median latency in seconds times maximum observed GPU H/s; resource objective = median CPU milliseconds with memory/RSS tie-breakers; comprehensive reports defense-first reference and frontier rather than claiming a universal optimum. GPU ceiling default 1000 is illustrative and editable. Only defense mode uses early stopping.
- Verification: 8 unit tests passed (5 existing plus 3 new, including mocked end-to-end selection for all 5 modes, frontier dominance, GUI argument validation). Known-answer check passed. Actual Linux CPU balanced-mode smoke run completed with 2 candidates and generated ranking/report. Virtual X display verified tabs, theme switching and busy locking; inspected actual GUI screenshot. Mock data are tests only and not experimental evidence. The original historical replay remains defense-mode only.
- Pending: native Windows build and real Windows runs for each mode, timing/quality comparisons on other hardware, human review. The new modes are exhaustive over eligible candidates only subject to screening/confirmation, not provably globally optimal under measurement noise.


## Dark-default preference
User requested dark theme on startup. Changed only the initial Tk BooleanVar and desktop documentation; Windows EXE must be rebuilt. No benchmark or profile changes.

## Version 3 additions (2026-11-26)

| AI output / claim | Category | Verified? | How checked |
|---|---|---|---|
| Shared results directory persists and follows user naming conventions | Code that runs but is wrong | Local yes | Compared Results.zip paths, unit-tested exact naming and settings persistence; opened GUI and switched tabs. |
| New GPU collector selects 193 exact Argon2id configs | Misstated result | Yes | Compared grid keys against actual bundled profile. |
| Pause/resume preserves completed rounds, exports only verified complete configs | Code that runs but is wrong | Simulated only | Mocked benchmark calls, paused after first checkpoint, resumed and checked four unique calls and imported profile. Hardware/backend changes rejected. |
| GPU parser accepts matching device only | Code that runs but is wrong | Local yes | Unit tests for device mismatch; parsed original RTX 4090 status log. |
| CUDA/OpenCL backend selection flags | Nonexistent API | Source checked | Hashcat 8 usage source https://fossies.org/dox/hashcat-8.0.0/usage_8c_source.html ; actual execution pending. |
| GPU thermal pause and runtime estimate | Overclaim | Partial | Mocked thermal pause; estimate from 386 original Argon2id GPU runs totaling 2.12 hours excluding verification. Actual temperature safety and Windows runtime unverified. |
| Windows standalone EXE and new GPU collection | Overclaim | Pending | Linux build environment; team must rebuild and check first live reference GPU run. |

The 14 unit tests passed locally; GUI virtual-display smoke checks passed. No claim that synthetic mock GPU results are measured hardware data. No change to the existing optimizer's selection algorithm or stored RTX 4090 profile.

## Version 4 packaging extension

- User reported v3 shared directory, naming, warning and saved preferences working on Windows. This is user-reported validation; live GPU generation has not been confirmed.
- AI claim: Hashcat is redistributable under MIT subject to upstream/third-party notices. Checked official download and license sources https://hashcat.net/hashcat/ and https://github.com/hashcat/hashcat/blob/master/docs/license.txt . The build retains the entire upstream release and license.
- AI claim: PyInstaller builds Windows executables on Windows, not directly on Linux. Checked https://pyinstaller.org/en/stable/ . No compiled Windows executable is claimed here.
- Implementation: packaged engine lookup/cache, stable extraction path, fallback for source-only edition, binary identity check on resume, pinned official release acquisition and archive/binary SHA-256 provenance. GitHub Actions recipe uses Windows x64. Build-time package self-test checks actual packaged Argon2 known answer, profile and engine version, not GPU throughput.
- Verification: 18 unit tests and CPU known-answer check passed on Linux, using synthetic fixture archive for packing/extraction tests. Unsafe archive member, missing license and changed binary rejected; pause/resume simulation from v3 still passes. The actual upstream binary download failed in preparation environment, and Windows runner execution and live GPU tests remain pending. HTTPS acquisition does not itself establish publisher signature validity.
- No change to the optimizer's objectives or original data. The user must independently verify the built release and actual GPU reference run before submission.


## v4.1: actual Windows build failure
| Claim | Category | Verified? | How checked |
|---|---|---|---|
| py7zr can extract the official Hashcat archive | Code that runs but is wrong / unsupported format | No; corrected | User's Windows traceback reports BCJ2 UnsupportedCompressionMethodError; py7zr documentation confirms BCJ2 unsupported (https://py7zr.readthedocs.io/en/latest/user_guide.html). |
| External extraction can fall back cleanly without retaining partial output | Code | Local simulated test passed | Mock first extractor failure and second success, require clean destination and complete layout. Windows build and real archive extraction still pending. |


## v4.2: Windows GPU enumeration fix
| Claim | Category | Verified? | How checked |
|---|---|---|---|
| Metal ignore option is accepted on Windows | Nonexistent platform-specific option | No; corrected | User screenshot reports unsupported option. Hashcat v8.0.0 source restricts Metal handling to Apple builds: https://github.com/hashcat/hashcat/blob/v8.0.0/src/user_options.c . Only append option on Darwin. Both GUI and collection use the same device query helper; failed query surfaces actual stderr/stdout instead of misleading device ID error. |
| Fix works on Windows GPU | Code / overclaim | Pending live test | Local platform-flag and failed-query regression tests; actual executable rebuild and GPU test required. User reported v4.1 executable loaded and bundled engine launched. |

## v4.3: false thermal abort and platform-aware GPU controls
- **Code that runs but is wrong:** v4.2 `thermal()` matched the ordinary Hashcat startup notice announcing an 85°C watchdog trigger, as well as a genuine thermal event. The user's live Windows test exposed repeated false pauses at low temperatures. Checked the v8.0.0 source `src/main.c` (https://github.com/hashcat/hashcat/blob/v8.0.0/src/main.c) for the actual `Temperature limit on GPU #N reached, aborting` event, and replayed the replacement against 2,052 watchdog-banner-containing sweep/confirmation logs (zero false thermal detections). The threshold and hardware watchdog remain active. Actual temperatures are also checked in matching status records, including the first and terminal samples.
- **Misstated result:** missing temperature telemetry is not an overheating report. Now separate pause exit codes and GUI labels distinguish user pause, real temperature limit, unavailable temperature telemetry, subprocess timeout, and reference benchmark/verification failure. Timeout output is retained. Failed measurements are not interpreted as attack resistance; timeout/telemetry/thermal pauses leave the current measurement uncommitted. High GPU utilization by itself is not an abort condition.
- Platform selection uses `platform.system()` rather than allowing an OS mismatch; CUDA/HIP/OpenCL offered on Windows/Linux, Metal/OpenCL on macOS. Hashcat v8 source documents Apple-only Metal option (https://github.com/hashcat/hashcat/blob/v8.0.0/src/user_options.c). Windows bundled executable remains Windows-only; other platforms require compatible Python/Tk and native Hashcat, and backend/device discovery and thermal telemetry must be tested on real hardware. No bypass of monitoring for devices without telemetry.
- Verification: 25 unit tests passed on Linux with synthetic/mocked GPU execution, including thermal messages, telemetry and platform flag generation; historical log replay as above. Native Windows executable rebuild, live GPU profile generation, Linux GPU and macOS Metal/HIP compatibility are not verified. Optimizer ranking logic and bundled RTX 4090 data unchanged. Merge this entry into the group's central audit and independently verify on actual hardware.

### v4.4 — multi-platform OpenCL identity parsing
- Claim: the laptop GPU benchmark ran correctly but the platform header for Intel overwrote the selected NVIDIA device name/vendor. Category: code that runs but is wrong. Verified by comparing the uploaded Hashcat information, JSON device status, and desktop traceback, then reproducing against the original parser and checking the corrected parser. Actual laptop rebuild/retest pending.
- Fix: terminate the device record at each platform header, record only the selected ID, reject duplicate fields instead of silently overwriting them, and retain strict runtime device identity verification. Added a regression using the actual laptop device metadata and status records (without paths or inputs). No change to benchmark protocol, optimization logic or temperature thresholds.
- Previous failed laptop job contains a misidentified manifest and zero committed checkpoints; start a fresh job rather than mixing identities.
