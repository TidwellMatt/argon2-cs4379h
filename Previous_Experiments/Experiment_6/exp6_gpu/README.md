# Experiment 6 — GPU measurements and stage-cost model

## Scope
This is a synthetic benchmark, not a password recovery program. It accepts no password lists, hashes, or account information. There are two paths:

1. **gpu_baseline.py** (easy): the existing Experiment 5E benchmark-only wrapper for Hashcat 7+ mode 34000, using the built-in standard Argon2 benchmark. It does not match all Experiment 5E parameters or measure hybrid performance.
2. **gpu_stages.py** (advanced): actual GPU timings of 18 distinct standard Argon2 stages selected from your uploaded Experiment 5E screen. It compares 24 configurations (including six mixed/double Argon2 finalists and direct stage controls). It uses a separately installed argon2-gpu-bench executable; no compiled GPU backend is supplied. The six hybrid results are **serial stage-cost estimates only**, not end-to-end measured hybrid GPU rates.

The fixed plan in gpu_plan.json was extracted from the actual calibrated stages in exp5e_screen.zip/configs.json and ranking.csv. It includes the three original baselines, three leading CPU-eligible standalone configurations per variant, three leading eligible mixed cascades, three leading eligible double cascades, and direct stage controls. CPU latency and eight-worker throughput are screening results, not independent confirmation. Controls not present in the CPU data have unknown CPU eligibility; do not claim they satisfy the latency limit.

## Quick route (Windows PowerShell)
Extract the package and open PowerShell in exp6_gpu. Download and extract Hashcat from https://hashcat.net/hashcat/ (version 7 or newer). From the package directory:

```powershell
python gpu_baseline.py --hashcat "C:\path\to\hashcat.exe" --out results/gpu_baseline
```

Replace the path. Do not run alongside CPU experiments. Check devices.txt, benchmark.txt and telemetry before using the result. Verify that the GPU is the RTX 4090 and record the parameters printed by Hashcat. Do not compare the rate numerically to a CPU configuration unless parameters match.

## Parameter-matched route (advanced)
Upstream project: https://gitlab.com/omos/argon2-gpu ; documented CLI/build examples: https://github.com/WebDollar/argon2-gpu/blob/master/README.md . This is an older CMake C++ project, not a pip dependency. It requires a compatible C++ compiler, CMake, and CUDA or OpenCL development libraries. Build and compatibility on current Windows/NVIDIA drivers are NOT verified. The repository's documented build procedure is to clone recursively, configure CMake in Release mode, and compile. For OpenCL the upstream data/kernels folder must be available in the working directory. You may need to use a compatible Linux environment with GPU access if the Windows build fails. Do not spend the entire deadline on setup: use the quick route if blocked.

Once you have built argon2-gpu-bench and argon2-gpu-test, run:

```powershell
python gpu_stages.py --self-test
python gpu_stages.py --bench "C:\path\to\argon2-gpu-bench.exe" --test "C:\path\to\argon2-gpu-test.exe" --cwd "C:\path\to\argon2-gpu" --backend opencl --smoke --out results/gpu_stage_smoke
```

Confirm the selected device in upstream logs and NVIDIA telemetry. If the upstream test fails, stop and investigate; do not treat timings as verified. `--backend cuda` is an alternative only if you compiled CUDA support. If the GPU is not device zero, use the actual upstream GPU index. The scripts invoke only the synthetic benchmark; they do not configure a recovery task.

Then repeat without `--smoke` and change the output directory to `results/gpu_stages`. Full runs use fixed synthetic batch sizes of 4, 16, 32 and 64 and three independent invocations per stage and batch, with five samples per invocation. Some runs may fail due to GPU allocation limits or backend incompatibility; failures are retained and excluded from complete estimates. No memory-saving attack is attempted. GPU measurements must be verified against the raw logs and device telemetry. In particular, OpenCL may expose CPU devices; the device index alone is not proof of GPU use. `--test` is optional in the wrapper but required for the team's verified results. An upstream test returning success must still be inspected for coverage and real GPU execution.

## Interpretation
`gpu_stage_summary.csv` contains median and range of directly measured standard-stage timings, derived throughput and completeness. `gpu_comparison.csv` explicitly marks each result as measured standalone or serial stage model ONLY. The model adds the measured per-derivation time of each separate stage at the same batch size, then takes the reciprocal. It assumes stages run sequentially and omits intermediate data movement, pipeline overlap, possible fused kernels and alternate memory strategies. It is neither a guaranteed upper nor lower bound on end-to-end throughput. It cannot distinguish forward and reverse order with the same stage parameters. GPU backend measurements may not include all the host-side costs included in the CPU measurement. Do not claim improved security, actual hybrid GPU throughput, or general GPU/ASIC resistance based on this model. No PBKDF2/scrypt/cipher hybrid is GPU tested here.

## Evidence and remaining work
The project rubric calls for a contribution to knowledge, a quantitative testable hypothesis, and reproducibility. It does not explicitly demand a positive result. Experiment 5E contains 2,958 configurations (168 standalone, 2,790 hybrid); 2,735 hybrids and 155 standalone passed the latency ceiling. No candidate flag was true. This is a negative screening result, not proof that no hybrid can ever win. Independently confirm leading configurations and controls, verify novelty against the literature, and report CPU/GPU limits. Do not present a negative result as instructor-approved; ask the instructor to confirm the scope if possible.

## Validation of this package
Local Python syntax and self-test passed. Actual GPU execution, external CLI compatibility, GPU correctness checks, and the full run remain unverified in this environment. The old Hashcat wrapper is unchanged. No GPU performance results are included or fabricated. Upload the whole results directory after a successful test.
