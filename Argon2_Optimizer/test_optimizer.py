import unittest, copy, argparse, tempfile
from pathlib import Path
from profile_data import load_profiles,candidates,validate
from optimizer import ROOT,policy,feasible,safe_summary,rank,BASE,HIGH
class Checks(unittest.TestCase):
    def setUp(self):self.p=load_profiles([ROOT/'profiles/rtx4090.json'])[0]
    def test_profile(self):
        self.assertEqual(len(self.p['entries']),579);self.assertEqual(len(candidates([self.p])),193)
        self.assertEqual(sum(len(e['hps_rounds'])==20 for e in self.p['entries'].values()),15)
    def test_missing_and_worst(self):
        q=copy.deepcopy(self.p);q['profile_id']='test';q['entries']={BASE:q['entries'][BASE]};q['entries'][BASE]['hps_rounds']=[9999.0]
        cs=candidates([self.p,q]);self.assertEqual(len(cs),1);self.assertEqual(cs[0]['gpu_max_observed'],9999.0)
    def test_bad_profile(self):
        q=copy.deepcopy(self.p);q['entries'][BASE]['hps_rounds']=[0];self.assertRaises(ValueError,validate,q)
    def test_policy(self):
        a=argparse.Namespace(min_memory=64,max_memory=2048,min_passes=3)
        cs={c['config']:c for c in candidates([self.p])}
        self.assertTrue(policy(cs[BASE],a));self.assertTrue(policy(cs[HIGH],a));self.assertFalse(policy(cs['id_m32_t6_p4'],a));self.assertFalse(policy(cs['id_m64_t1_p4'],a))
    def test_constraints(self):
        a=argparse.Namespace(latency_ms=100,max_cpu_ms=150,max_p95_ms=200,max_rss_mib=512,min_throughput=10)
        row=dict(latency_ms=80,cpu_ms=100,concurrent_p95_ms=150,rss_peak_mib=300,concurrent_hps=12)
        self.assertTrue(feasible(safe_summary([row]),a));r=dict(row,concurrent_hps=9);self.assertFalse(feasible(safe_summary([row,r]),a))
if __name__=='__main__':unittest.main()
