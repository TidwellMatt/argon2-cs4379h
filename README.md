# Argon2 from scratch: CS 4379H Group Project (Fall 2026)

A readable, pure-Python implementation of the Argon2 password-hashing function
(Argon2d, Argon2i, Argon2id, version 1.3), verified against the official
RFC 9106 test vectors and the reference C implementation, plus four
experiments that reproduce the main claims of the Argon2 paper.

**Paper:** A. Biryukov, D. Dinu, D. Khovratovich, "Argon2: New Generation of
Memory-Hard Functions for Password Hashing and Other Applications," IEEE
EuroS&P 2016. DOI [10.1109/EuroSP.2016.31](https://doi.org/10.1109/EuroSP.2016.31)

**Team:** Caleb Tyler, Matthew Tidwell, Brendan O'Mara
**Course:** CS 4379H Cryptography, Texas State University, Dr. Heena Rathore

> This is a teaching implementation. It is far slower than the C
> library and must not be used to protect real passwords. Use
> [argon2-cffi](https://pypi.org/project/argon2-cffi/) for that.

---

## Repository layout

| File | What it is |
|---|---|
| `argon2_impl.py` | The Argon2 implementation (H0, H', G, indexing, memory filling) |
| `test_argon2.py` | Test suite: RFC vectors, H0, intermediate blocks, 60 random cases vs argon2-cffi |
| `experiments.py` | Regenerates every CSV and chart in `results/` with one command |
| `demo.py` | Live demo for the presentation: correctness, brute-force race, memory use, side channel, tradeoff attack, password storage, charts |
| `results/*.csv` | Raw experiment data |
| `results/figures/*.png` | Charts used in the slides |
| `CODE_GUIDE.md` | Function-by-function map to the paper and RFC 9106 sections |
| `AI_AUDIT.md` | Log of every AI output we relied on and how we checked it |
| `requirements.txt` | Python dependencies |

---

## Clone, install, run

Requires **Python 3.9 or newer** and git. Tested on Windows 11 and macOS.

### 1. Clone

```bash
git clone https://github.com/TidwellMatt/argon2-cs4379h.git
cd argon2-cs4379h
```

### 2. Create a virtual environment and install dependencies

**Windows (PowerShell):**
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If PowerShell blocks the activate script, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use
`.venv\Scripts\activate.bat` from Command Prompt.

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

There is nothing to compile: "build" is just the `pip install` step.

### 3. Run

| Command | What it does | Time |
|---|---|---|
| `python test_argon2.py` | Runs all tests, prints PASS per test | ~5 s |
| `python -m pytest -q` | Same tests through pytest | ~5 s |
| `python demo.py` | Live demo menu (7 sections, pick one or run all) | ~15 s total |
| `python demo.py all` | Every demo section in order, Enter between steps | ~15 s + talking |
| `python demo.py 2` | Only section 2 (any number 1-7) | seconds |
| `python demo.py all --no-pause --no-charts` | Non-interactive run, for checking | ~12 s |
| `python experiments.py` | Regenerates `results/*.csv` and `results/figures/*.png` | ~30 s |
| `python experiments.py --quick` | Smaller sizes, for a fast check | ~10 s |
| `python argon2_impl.py` | One-line smoke test | <1 s |

(On macOS use `python3` if `python` is not found.)

---

## What works

- **Correctness.** Our output is byte-for-byte identical to the standard:
  - all three RFC 9106 test vectors (Argon2d, Argon2i, Argon2id) pass;
  - the H0 digest and the memory contents after passes 0, 1, 2 match the
    values printed in RFC 9106 Section 5.1;
  - 60 seeded random parameter sets (all three types, 1 to 4 lanes, 1 to 4
    passes, tag lengths 4 to 128 bytes) match argon2-cffi exactly.
- **Experiment 1: cost scaling** (`exp1_*.csv`, `exp1_*.png`). Hashing time and
  peak memory both grow linearly with m (a 256 MiB setting used 256 MiB of
  RAM); time grows linearly with the number of passes t; more lanes p cut the
  time while there are free CPU cores.
- **Experiment 2: per-guess cost** (`exp2_per_guess.*`). At OWASP-recommended
  settings, one PBKDF2 guess needs well under 1 KiB of memory and one bcrypt
  guess about 4 KiB, while one Argon2id guess needs 19 MiB. In 24 GiB of GPU
  memory that is roughly 6.3 million bcrypt guesses in parallel versus about
  1,300 Argon2id guesses (memory-only arithmetic, not a GPU measurement).
- **Experiment 3: exact work** (`exp3_g_calls.csv`). Our implementation makes
  exactly t·m − 2 calls to the compression function G for Argon2d, plus 2 per
  address block for Argon2i/Argon2id, as the specification implies.
- **Experiment 4: tradeoff attack** (`exp4_tradeoff.*`). We simulate an attacker
  who keeps only a fraction α of the memory of 1-pass Argon2d (16,384 blocks)
  and recomputes the rest, and measure the computation penalty C(α) and
  latency penalty D(α) defined in Section II of the paper.

  | α | 1/2 | 1/3 | 1/4 | 1/5 | 1/6 | 1/7 |
  |---|---|---|---|---|---|---|
  | Our best attacker, C(α) | 1.44 | 4.19 | 31.9 | 1,412 | 2.1·10⁵ | 3.2·10⁸ |
  | Paper Table I (ranking attack), C(α) | 1.5 | 4 | 20.2 | 344 | 4,660 | 2¹⁸ |

  Our simpler attacker matches the paper at α = 1/2 and 1/3. Below that it
  pays a larger penalty than the paper's ranking attack, which is expected:
  the paper's attacker is smarter, so the paper's numbers are the tighter
  (lower) cost for an attacker. Both show the same trend: saving memory gets
  very expensive very quickly, which is the paper's main security claim.

## What doesn't work / limitations

- **Speed.** Pure Python is roughly 25 to 150 times slower than the C library
  (see `python demo.py 1` timings). Fine for learning and for small test sizes, not for
  production.
- **No real parallelism in our implementation.** Lanes are computed one after
  another. The lane-scaling result in Experiment 1 uses argon2-cffi, which
  does use threads.
- **No encoded-string format.** `argon2_impl.py` returns raw tag bytes; it does
  not produce or parse `$argon2id$v=19$...` strings. The demo uses argon2-cffi's
  `PasswordHasher` to show that part.
- **Not the paper's exact ranking attack.** Experiment 4 uses a simpler
  "hybrid" attacker (some evenly spaced blocks, the rest the most-referenced
  blocks), so it does not reproduce Table I below α = 1/3. Only 1-pass Argon2d
  is attacked; we did not attack Argon2i.
- **Timing numbers depend on the machine.** Experiments 1 and 2 measure wall
  time, so your numbers will differ from ours; the shapes (linear in m and t)
  should not. Experiments 3 and 4 are deterministic and reproduce exactly.
- **Peak-memory measurement is OS-specific.** We use psutil on Windows,
  `ru_maxrss` (bytes) on macOS, and `VmHWM` on Linux.

---

## Reproducing our results

All data in `results/` was produced by `python experiments.py` with the code in
this repository. Experiments 3 and 4 use fixed inputs and give identical
numbers on every run. Experiments 1 and 2 measure time, so expect different
absolute numbers but the same trends. The test suite uses a fixed random seed
(4379), so it checks the same 60 cases every run.

---

## References

Both references below were checked by hand: the DOI links resolve to the
paper named, and RFC 9106 itself cites both papers with the same DOIs.

**Prior work that Argon2 builds on**

C. Percival, "Stronger Key Derivation via Sequential Memory-Hard Functions,"
presented at BSDCan 2009, Ottawa, May 2009.
<https://www.tarsnap.com/scrypt/scrypt.pdf>
Introduces memory-hard functions and scrypt; Argon2's paper cites scrypt as
the earlier memory-hard password hash it improves on.

**Later work that builds on Argon2**

J. Alwen and J. Blocki, "Efficiently Computing Data-Independent Memory-Hard
Functions," in *Advances in Cryptology: CRYPTO 2016*, LNCS vol. 9815,
pp. 241-271, Springer, 2016. DOI
[10.1007/978-3-662-53008-5_9](https://doi.org/10.1007/978-3-662-53008-5_9).
Preprint: <https://eprint.iacr.org/2016/115>
Gives an attack showing Argon2i (the data-independent variant) can be computed
with less memory-time cost than intended. This line of work is one reason
RFC 9106 recommends Argon2id rather than Argon2i.

**Specification used for byte-level details**

A. Biryukov, D. Dinu, D. Khovratovich, S. Josefsson, "Argon2 Memory-Hard
Function for Password Hashing and Proof-of-Work Applications," RFC 9106,
September 2021. <https://www.rfc-editor.org/rfc/rfc9106>

---

## AI use

Our professor approved AI assistance on this project. Every AI output we relied
on (code, claims, citations) is logged in [`AI_AUDIT.md`](AI_AUDIT.md) with how
we checked it, including the mistakes we caught.


## Follow-up research: hardware-aware Argon2id optimizer

Caleb Tyler's follow-up contribution is in [Argon2_Optimizer](Argon2_Optimizer/README.md). It combines local CPU benchmarking with a stored RTX 4090 GPU profile and configurable optimization objectives. See the [desktop instructions](Argon2_Optimizer/DESKTOP_README.md), [previous experiments](Previous_Experiments/README.md), [optimizer validation](Optimizer_Validation/README.md), and the consolidated [AI audit](AI_AUDIT.md). The prior stacking experiments include negative results. The tool's recommendations are conditional on the measured attacker hardware, parameter grid and defender constraints, not universal security guarantees.

### Windows desktop download

- [Argon2 Optimizer v4.4.0 — Windows pre-release](https://github.com/EG156/argon2-cs4379h/releases/tag/v4.4.0)
- [Download Argon2Optimizer.exe](https://github.com/EG156/argon2-cs4379h/releases/download/v4.4.0/Argon2Optimizer.exe)

The executable is distributed from Caleb's fork. It is an unsigned research prototype tested on two Windows systems. Normal optimization requires neither Python nor a separate Hashcat installation; GPU profile collection requires compatible GPU drivers and runtime support. Some security products may flag the bundled Hashcat engine or unsigned package; do not disable antivirus protection. See the [third-party notices](Argon2_Optimizer/third_party_notices/) and [build instructions](Argon2_Optimizer/DESKTOP_README.md). macOS and Linux builds have not been independently verified.
