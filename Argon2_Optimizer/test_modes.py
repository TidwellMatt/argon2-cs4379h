import argparse, csv, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import optimizer as o
import desktop as d

def candidate(name, gpu, mem=64):
    return dict(config=name, memory_mib=mem,t=3,p=4,gpu_max_observed=gpu,gpu_median_worst=gpu,gpu_min_rounds=2)

def cpu(lat, cost):
    return dict(latency_ms=lat,cpu_ms=cost,concurrent_hps=20,concurrent_p95_ms=lat,rss_peak_mib=128)

class Modes(unittest.TestCase):
    def test_selection_and_outputs(self):
        cs=[candidate('A',300),candidate('B',350),candidate('C',600)]
        measurements={'A':cpu(95,100),'B':cpu(50,60),'C':cpu(25,80)}
        for mode, expected, count, cap in [('defense','A',1,None),('balanced','C',3,None),('responsive','B',2,400),('efficient','B',2,400),('comprehensive','A',3,None)]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td:
                a=argparse.Namespace(profile=None,out=td,mode=mode,exhaustive=False,max_gpu_hps=cap,max_memory=256,min_memory=64,min_passes=3,latency_ms=100,max_cpu_ms=None,max_p95_ms=None,max_rss_mib=None,min_throughput=None,workers=1,screen_rounds=1,confirm_rounds=3,max_tests=0,research_relaxed=False)
                with patch.object(o,'candidates',return_value=cs),patch.object(o,'measure',side_effect=lambda c,*_:measurements[c['config']]):o.optimize(a)
                r=json.loads((Path(td)/'recommendation.json').read_text());self.assertEqual(r['mode'],mode);self.assertEqual(r['tested_candidates'],count);self.assertEqual(r['recommendation']['configuration']['config'],expected)
                with (Path(td)/'confirmed_ranking.csv').open() as f: rows=list(csv.DictReader(f))
                self.assertEqual(rows[0]['config'],expected);self.assertEqual(len(rows),count)
    def test_frontier(self):
        a={'configuration':candidate('A',300),'cpu_median':cpu(50,60)}
        b={'configuration':candidate('B',350),'cpu_median':cpu(60,70)}
        c={'configuration':candidate('C',400),'cpu_median':cpu(25,50)}
        self.assertEqual(o.frontier([a,b,c]),{'A','C'})
    def test_gui_args(self):
        v=dict(zip(d.SPEC,d.DEFAULTS))
        self.assertIn('balanced',d.make_args(v,[],Path('.'),'balanced'))
        self.assertIn('--max-gpu-hps',d.make_args(v,[],Path('.'),'efficient','400'))
        with self.assertRaises(ValueError):d.make_args(v,[],Path('.'),'responsive','')
        with self.assertRaises(ValueError):d.make_args(v,[],Path('.'),'responsive','nan')
if __name__=='__main__':unittest.main()
