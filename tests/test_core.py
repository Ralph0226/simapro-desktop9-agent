import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_server import core

SOURCE = Path(__file__).resolve().parents[1] / 'examples'

class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for sample in SOURCE.glob('*.csv'):
            (self.root / sample.name).write_bytes(sample.read_bytes())
        self.env = patch.dict(os.environ, {'SIMAPRO_WORKSPACE':str(self.root)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_lci_demo_valid_with_warnings(self):
        report = core.validate_inventory('foreground_lci_demo.csv')
        self.assertTrue(report['ok'],report['errors'])
        self.assertEqual(report['rows'],4)
        self.assertGreater(len(report['warnings']),0)

    def test_summary_no_impact(self):
        report = core.inventory_summary('foreground_lci_demo.csv')
        self.assertTrue(report['ok'])
        self.assertIn('No impact', report['remark'])

    def test_scenarios(self):
        result = core.create_scenario_inventories('foreground_lci_demo.csv','P01','F03',[0.9,1.1])
        self.assertTrue(result['ok'])
        p = Path(result['created'][0]['file'])
        with p.open(encoding='utf-8-sig',newline='') as fp:
            row = next(r for r in csv.DictReader(fp) if r['flow_id']=='F03')
        self.assertAlmostEqual(float(row['amount']),0.45)
        with self.assertRaises(FileExistsError):
            core.create_scenario_inventories('foreground_lci_demo.csv','P01','F03',[0.9])

    def test_lcia_compare(self):
        report = core.compare_results('lcia_results_demo.csv','baseline')
        target = next(r for r in report['comparisons'] if r['scenario']=='low_energy' and r['indicator']=='Climate change')
        self.assertAlmostEqual(target['improvement_pct_if_lower_is_better'],16.66667)

    def test_reject_path_escape(self):
        with self.assertRaises(ValueError):
            core.safe_path('../outside.csv')

    def test_reject_duplicate_indicator(self):
        with (self.root/'bad.csv').open('w',encoding='utf-8',newline='') as f:
            writer=csv.writer(f); writer.writerow(core.RESULT_COLUMNS)
            writer.writerow(['baseline','GWP',1,'kg CO2-eq'])
            writer.writerow(['baseline','GWP',2,'MJ'])
        with self.assertRaises(ValueError):
            core.compare_results('bad.csv','baseline')

    def test_short_csv_row_is_rejected(self):
        (self.root/'short.csv').write_text(','.join(core.LCI_COLUMNS)+'\nP1,name\n',encoding='utf-8')
        with self.assertRaises(ValueError):
            core.validate_inventory('short.csv')

    def test_empty_process_name_is_rejected(self):
        p=self.root/'foreground_lci_demo.csv'
        p.write_text(p.read_text(encoding='utf-8-sig').replace('DEMO recovery process',''),encoding='utf-8')
        fields,rows=core._load_csv(p,core.LCI_COLUMNS)
        for row in rows:
            row['process_name']=''
        with p.open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
        self.assertFalse(core.validate_inventory(p.name)['ok'])

    def test_invalid_last_multiplier_creates_no_scenarios(self):
        with self.assertRaises(ValueError):
            core.create_scenario_inventories('foreground_lci_demo.csv','P01','F03',[0.9,float('nan')])
        self.assertFalse(list(self.root.glob('outputs/scenarios/*.csv')))

if __name__=='__main__':
    unittest.main()
