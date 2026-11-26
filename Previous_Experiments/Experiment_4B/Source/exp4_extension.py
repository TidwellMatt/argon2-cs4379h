"""Experiment 4B: input sensitivity of one-pass Argon2 dependency graphs.
Place alongside argon2_impl.py. No changes to the original experiment.
All inputs are synthetic. C and D are graph-model scores, not measured runtimes.
"""
import argparse
import csv
import hashlib
import json
import random
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def validate(ref):
    if len(ref) < 8 or ref[:2] != [None, None]:
        raise ValueError('Expected two initial blocks and at least eight blocks')
    if any(not isinstance(r, int) or not 0 <= r < j - 1
           for j, r in enumerate(ref[2:], 2)):
        raise ValueError('Not a valid single-pass, single-lane dependency trace')


def retained(ref, keep, strategy):
    """Fixed policies; the hybrid uses future-reference counts (oracle model)."""
    n = len(ref)
    if not 2 <= keep <= n:
        raise ValueError('Invalid block budget')
    if keep == n:
        return set(range(n))
    # Include both initial blocks in the budget, not in addition to it.
    slots = keep - 2 if strategy == 'uniform' else (keep - 2) // 2
    stored = {0, 1}
    if slots:
        stored.update(2 + (i * (n - 2)) // slots for i in range(slots))
    if strategy == 'hybrid_fixed':
        counts = Counter(ref[2:])
        for j in sorted(range(2, n), key=lambda j: (-counts[j], j)):
            if len(stored) == keep:
                break
            stored.add(j)
    elif strategy != 'uniform':
        raise ValueError(strategy)
    assert len(stored) == keep
    return stored


def model(ref, stored):
    """Original Exp4 recurrence, including its n-unit normalization.

    Initial blocks count as one abstract unit each; these are not literal G calls.
    No accounting for metadata, temporary storage, address-generation work,
    cache reuse, or actual hardware execution. D is a serial sum of idealized
    recomputation depths, not measured time or a general latency bound.
    """
    n = len(ref)
    work = [1] * n
    depth = [1] * n
    extra_work = extra_depth = 0
    for j in range(2, n):
        missing = [a for a in (j - 1, ref[j]) if a not in stored]
        work[j] = 1 + sum(work[a] for a in missing)
        depth[j] = 1 + max((depth[a] for a in missing), default=0)
        r = ref[j]
        if r not in stored and r != j - 1:
            extra_work += work[r]
            extra_depth += depth[r]
    return (n + extra_work) / n, (n + extra_depth) / n


def trace_graph(impl, pw, salt, n, kind):
    trace = {}
    tag = impl.argon2_hash(pw, salt, time_cost=1, memory_kib=n,
                          parallelism=1, type_=kind, trace=trace)
    assert trace['p'] == trace['t'] == 1 and trace['lane_len'] == n
    ref = [None] * n
    for pass_n, lane, col, prev, ref_lane, r in trace['deps']:
        assert (pass_n, lane, ref_lane) == (0, 0, 0)
        assert prev == col - 1 and ref[col] is None
        ref[col] = r
    assert len(trace['deps']) == n - 2
    validate(ref)
    return ref, tag


def fingerprint(ref):
    return hashlib.sha256(json.dumps(ref, separators=(',', ':')).encode()).hexdigest()


def inputs(seed, trials, axis):
    rng = random.Random(seed + (0 if axis == 'salt' else 1))
    for i in range(trials):
        changing = bytes(rng.getrandbits(8) for _ in range(16))
        if axis == 'salt':
            yield i, b'synthetic-password', changing
        else:
            yield i, changing, b'synthetic-salt!!'


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in ('variant', 'axis', 'blocks', 'denominator', 'strategy'))].append(row)
    output = []
    for key, group in sorted(groups.items()):
        cs = [r['C'] for r in group]
        ds = [r['D'] for r in group]
        row = dict(zip(('variant', 'axis', 'blocks', 'denominator', 'strategy'), key))
        row.update(trials=len(group), distinct_graphs=len({r['graph_sha256'] for r in group}))
        for name, vals in [('C', cs), ('D', ds)]:
            row.update({name+'_min': min(vals), name+'_median': st.median(vals),
                        name+'_max': max(vals), name+'_stdev': st.stdev(vals) if len(vals)>1 else 0,
                        name+'_max_min_ratio': max(vals)/min(vals)})
        output.append(row)
    return output


def charts(out, summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    n = max(r['blocks'] for r in summary)
    for axis in ('salt', 'password'):
        for strategy in ('uniform', 'hybrid_fixed'):
            for metric in ('C', 'D'):
                fig, ax = plt.subplots(figsize=(8, 4.8))
                for variant in ('argon2d', 'argon2i', 'argon2id'):
                    s = sorted((r for r in summary if r['axis']==axis and r['blocks']==n
                                and r['variant']==variant and r['strategy']==strategy),
                               key=lambda r: r['denominator'])
                    x = [r['denominator'] for r in s]
                    line, = ax.plot(x, [r[metric+'_median'] for r in s], marker='o', label=variant)
                    ax.fill_between(x, [r[metric+'_min'] for r in s], [r[metric+'_max'] for r in s],
                                    color=line.get_color(), alpha=.12)
                ax.set_yscale('log')
                ax.set_xticks(x, [f'1/{k}' for k in x])
                ax.set(xlabel='Nominal retained fraction (fewer blocks to the right)',
                       ylabel=f'Modeled {metric} (log scale)',
                       title=f'{axis.title()} sensitivity | {n} blocks | {strategy}')
                ax.grid(alpha=.2); ax.legend(); fig.tight_layout()
                fig.savefig(out / f'{axis}_{strategy}_{metric}.png', dpi=180)
                plt.close(fig)


def self_test():
    # Toy graph: block 4 references discarded block 2, requiring one rebuild.
    ref = [None, None, 0, 0, 2, 0, 1, 0]
    validate(ref)
    assert model(ref, set(range(8))) == (1, 1)
    assert model(ref, {0, 1}) == (9/8, 9/8)
    for n in (8, 256, 1024, 4096):
        r = [None, None] + [0]*(n-2)
        for k in range(2, 8):
            for strategy in ('uniform', 'hybrid_fixed'):
                keep = max(2, n//k)
                s = retained(r, keep, strategy)
                assert len(s)==keep and {0,1} <= s
                assert model(r, s) == (1, 1)
    try:
        validate([None, None, 2, 0, 0, 0, 0, 0])
    except ValueError:
        pass
    else:
        raise AssertionError('Invalid trace accepted')
    print('PASS: toy model, exact budgets, full retention, invalid trace rejection')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--quick', action='store_true', help='Small integration check')
    ap.add_argument('--self-test', action='store_true', help='Standalone model tests only')
    ap.add_argument('--trials', type=int, default=None)
    ap.add_argument('--seed', type=int, default=4379)
    ap.add_argument('--output', type=Path, default=None)
    args = ap.parse_args()
    self_test()
    if args.self_test:
        return
    import argon2_impl as impl
    from experiments import attack_cost as original_model
    from argon2.low_level import Type, hash_secret_raw
    trials = args.trials if args.trials is not None else (3 if args.quick else 12)
    if trials < 2:
        ap.error('--trials must be at least 2')
    sizes = [256] if args.quick else [256, 1024, 4096]
    ks = range(2, 5) if args.quick else range(2, 8)
    out = args.output or HERE / 'results' / ('exp4b_quick' if args.quick else 'exp4b')
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, kind, libtype in [('argon2d', impl.ARGON2D, Type.D),
                                 ('argon2i', impl.ARGON2I, Type.I),
                                 ('argon2id', impl.ARGON2ID, Type.ID)]:
        for n in sizes:
            for axis in ('salt', 'password'):
                graphs = set()
                for trial, pw, salt in inputs(args.seed, trials, axis):
                    ref, tag = trace_graph(impl, pw, salt, n, kind)
                    assert tag == hash_secret_raw(pw, salt, 1, n, 1, 32, libtype), 'Tag mismatch'
                    digest = fingerprint(ref)
                    graphs.add(digest)
                    assert model(ref, set(range(n))) == (1, 1)
                    distance = st.median(j-r for j,r in enumerate(ref[2:],2))
                    max_refs = max(Counter(ref[2:]).values())
                    for k in ks:
                        keep = n//k
                        for strategy in ('uniform', 'hybrid_fixed'):
                            s = retained(ref, keep, strategy)
                            c,d = model(ref,s)
                            assert (c,d) == original_model(ref,s), "Original model disagreement"
                            assert c >= d >= 1
                            rows.append(dict(variant=name,axis=axis,blocks=n,trial=trial,
                                             seed=args.seed,denominator=k,strategy=strategy,
                                             retained_blocks=len(s),actual_fraction=len(s)/n,
                                             graph_sha256=digest,median_reference_distance=distance,
                                             max_reference_count=max_refs,C=c,D=d))
                if name == 'argon2i':
                    assert len(graphs)==1, 'Argon2i graph unexpectedly depends on inputs'
                print(f'{name}, {n} blocks, varying {axis}: {len(graphs)}/{trials} distinct graphs; all tags verified', flush=True)
    summary = summarize(rows)
    write_csv(out/'trials.csv', rows)
    write_csv(out/'summary.csv', summary)
    charts(out, summary)
    (out/'run.json').write_text(json.dumps(dict(seed=args.seed,trials=trials,sizes=sizes,
          denominators=list(ks),pass_count=1,lanes=1,rows=len(rows),
          tag_verification='all matched argon2-cffi',original_model_check='all rows matched experiments.attack_cost',model='abstract work/depth; not hardware measurement'),indent=2),encoding='utf-8')
    print(f'Done: {len(rows)} modeled observations; results in {out}')


if __name__ == '__main__':
    main()
