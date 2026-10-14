import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from mcp_server import desktop9,gui9

SAMPLES=Path(__file__).resolve().parents[1]/'examples'
class Desktop9Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for name in ('desktop9_simple_lci_DEMO.csv','licensed_catalog_FORMAT_EXAMPLE.csv',
                     'native_template_FORMAT_ONLY_NOT_AUTHENTIC.csv','results_export_FORMAT_EXAMPLE.csv'):
            (self.root/name).write_bytes((SAMPLES/name).read_bytes())
        self.env=patch.dict(os.environ,{'SIMAPRO_WORKSPACE':str(self.root)})
        self.env.start();self.addCleanup(self.env.stop)

    def test_mapping_suggestion_does_not_autoapprove(self):
        r=desktop9.list_dataset_candidates('desktop9_simple_lci_DEMO.csv','licensed_catalog_FORMAT_EXAMPLE.csv')
        self.assertTrue(r['ok']);self.assertEqual(r['candidates'],4)
        with (self.root/'outputs/dataset_mapping_review.csv').open(encoding='utf-8-sig') as f:
            self.assertTrue(all(row['approved']=='' for row in csv.DictReader(f)))

    def approve_mapping(self):
        desktop9.list_dataset_candidates('desktop9_simple_lci_DEMO.csv','licensed_catalog_FORMAT_EXAMPLE.csv')
        p=self.root/'outputs/dataset_mapping_review.csv'
        with p.open(encoding='utf-8-sig') as f: r=list(csv.DictReader(f));fields=list(r[0])
        found=set()
        for item in r:
            key=(item['process_id'],item['flow_id'])
            if key not in found and item['matched_geography']=='CN':
                item['approved']='yes';found.add(key)
        with p.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(r)
        return 'outputs/dataset_mapping_review.csv'

    def test_unapproved_rejected(self):
        r=desktop9.list_dataset_candidates('desktop9_simple_lci_DEMO.csv','licensed_catalog_FORMAT_EXAMPLE.csv')
        v=desktop9.build_native_import_candidate('desktop9_simple_lci_DEMO.csv',
            'outputs/dataset_mapping_review.csv','native_template_FORMAT_ONLY_NOT_AUTHENTIC.csv')
        self.assertFalse(v['ok']);self.assertIn('mapping approval',v['where'])

    def test_build_native_candidate(self):
        m=self.approve_mapping()
        info=desktop9.inspect_native_template('native_template_FORMAT_ONLY_NOT_AUTHENTIC.csv')
        self.assertTrue(info['ok'])
        r=desktop9.build_native_import_candidate('desktop9_simple_lci_DEMO.csv',m,
               'native_template_FORMAT_ONLY_NOT_AUTHENTIC.csv',process_suffix='baseline')
        self.assertTrue(r['ok']);self.assertEqual(r['process_count'],2)
        p=Path(r['file']);result=desktop9.parse_native('outputs/simapro9_import_CANDIDATE.csv')
        self.assertEqual(result['processes'],2)
        self.assertIn('DEMO sorted feed [baseline]',p.read_text(encoding='utf-8'))
        with self.assertRaises(FileExistsError):
            desktop9.build_native_import_candidate('desktop9_simple_lci_DEMO.csv',m,
               'native_template_FORMAT_ONLY_NOT_AUTHENTIC.csv',process_suffix='baseline')

    def test_unsupported_waste_rejected(self):
        m=self.approve_mapping()
        base=(self.root/'desktop9_simple_lci_DEMO.csv')
        with base.open('a',encoding='utf-8') as f:
            f.write('P01,DEMO materials recovery,F11,DEMO waste,waste_output,0.1,kg,,,CN,DEMO ONLY,waste\n')
        with self.assertRaises(ValueError):
            desktop9.build_native_import_candidate('desktop9_simple_lci_DEMO.csv',m,
               'native_template_FORMAT_ONLY_NOT_AUTHENTIC.csv')

    def test_normalize_and_compare(self):
        r=desktop9.normalize_lcia_export('results_export_FORMAT_EXAMPLE.csv','outputs/baseline.csv','baseline',
            'ReCiPe 2016 (H)','ecoinvent 3.5','cut-off','1 kg recovered material','Impact category','Total','Unit',result_stage='characterization')
        self.assertEqual(r['rows'],2)
        p=self.root/'outputs/baseline.csv'
        with p.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
        for row in list(rows):
            clone=dict(row);clone['scenario']='low_electricity';clone['value']=str(float(row['value'])*.9);rows.append(clone)
        combined=self.root/'combined.csv'
        with combined.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=desktop9.RESULT_IMPORT_FIELDS);w.writeheader();w.writerows(rows)
        comparison=desktop9.compare_verified_results('combined.csv','baseline')
        self.assertEqual(len(comparison['compared']),2)
        self.assertAlmostEqual(comparison['compared'][0]['relative_change_pct'],-10)
        rows[-1]['functional_unit']='1 tonne'
        with combined.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=desktop9.RESULT_IMPORT_FIELDS);w.writeheader();w.writerows(rows)
        with self.assertRaisesRegex(ValueError,'INCOMPARABLE'):
            desktop9.compare_verified_results('combined.csv','baseline')

    def test_local_catalog_from_export(self):
        r=desktop9.catalog_from_native_export('native_template_FORMAT_ONLY_NOT_AUTHENTIC.csv',
                   'outputs/native_catalog.csv','DUMMY_LIBRARY','DUMMY_VERSION','DUMMY_MODEL','UNIT TEST ONLY')
        self.assertTrue(r['ok'])
        self.assertEqual(r['indexed_reference_products'],1)
        with (self.root/'outputs/native_catalog.csv').open(encoding='utf-8-sig') as f:
            row=next(csv.DictReader(f))
            self.assertEqual(row['reference_unit'],'kg')

    def test_scenario_batch_candidates(self):
        mapping=self.approve_mapping()
        r=desktop9.prepare_batch_scenarios('desktop9_simple_lci_DEMO.csv',mapping,
            'native_template_FORMAT_ONLY_NOT_AUTHENTIC.csv','P01','F04',[0.9,1.1],
            'outputs/sensitivity_trial')
        self.assertTrue(r['ok'])
        self.assertEqual(len(r['scenarios']),2)
        self.assertNotEqual(r['scenarios'][0]['import_candidate'],r['scenarios'][1]['import_candidate'])
        text=Path(r['scenarios'][0]['import_candidate']).read_text(encoding='utf-8')
        self.assertIn('DEMO recovered material [S01]',text)
        self.assertTrue(Path(r['scenarios'][0]['manifest']).is_file())

    def test_merge_normalized_results(self):
        a=self.root/'x1.csv';b=self.root/'x2.csv'
        r=dict(indicator='GWP',value='5',unit='kg CO2 eq',method='m',database='db',
               system_model='cutoff',functional_unit='1kg',source_file='native-export.csv',result_stage='characterization')
        for f,scenario in [(a,'baseline'),(b,'alternative')]:
            with f.open('w',encoding='utf-8-sig',newline='') as fp:
                writer=csv.DictWriter(fp,fieldnames=desktop9.RESULT_IMPORT_FIELDS)
                writer.writeheader();writer.writerow(dict(r,scenario=scenario))
        combined=desktop9.combine_normalized_lcia(['x1.csv','x2.csv'],'outputs/merged.csv')
        self.assertTrue(combined['ok']);self.assertEqual(combined['rows'],2)
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            desktop9.combine_normalized_lcia(['x1.csv','x1.csv'],'outputs/other.csv')

    def test_gui_disabled_default(self):
        with patch.dict(os.environ,{'SIMAPRO_GUI_ENABLED':'0'}):
            with self.assertRaisesRegex(RuntimeError,'disabled'):
                gui9.gui_step('screenshot',approval_token='I_APPROVE_GUI_STEP')

    def test_stale_approved_mapping_rejected(self):
        mapping=self.approve_mapping()
        p=self.root/'desktop9_simple_lci_DEMO.csv'
        p.write_text(p.read_text(encoding='utf-8-sig').replace('Electricity medium voltage','Natural gas'),encoding='utf-8')
        self.assertFalse(desktop9.mapping_qa(p.name,mapping)['ok'])

    def test_duplicate_product_names_rejected(self):
        mapping=self.approve_mapping()
        p=self.root/'desktop9_simple_lci_DEMO.csv'
        p.write_text(p.read_text(encoding='utf-8-sig').replace('DEMO sorted feed','DEMO recovered material'),encoding='utf-8')
        with self.assertRaises(ValueError):
            desktop9.build_native_import_candidate(p.name,mapping,'native_template_FORMAT_ONLY_NOT_AUTHENTIC.csv')

    def test_template_process_metadata_not_inherited(self):
        mapping=self.approve_mapping()
        p=self.root/'native_template_FORMAT_ONLY_NOT_AUTHENTIC.csv'
        p.write_text(p.read_text(encoding='utf-8-sig').replace('Geography\n','Technology\nOLD SECRET TECHNOLOGY\n\nGeography\n'),encoding='utf-8')
        built=desktop9.build_native_import_candidate('desktop9_simple_lci_DEMO.csv',mapping,p.name)
        self.assertNotIn('OLD SECRET TECHNOLOGY',Path(built['file']).read_text(encoding='utf-8-sig'))

    def test_template_unknown_section_rejected(self):
        p=self.root/'native_template_FORMAT_ONLY_NOT_AUTHENTIC.csv'
        p.write_text(p.read_text(encoding='utf-8-sig').replace('\nEnd','\nUnknown allocation field\n100\n\nEnd'),encoding='utf-8')
        with self.assertRaises(ValueError):
            desktop9.parse_native(p.name)

    def test_template_reserved_word_as_comment_preserved(self):
        p=self.root/'native_template_FORMAT_ONLY_NOT_AUTHENTIC.csv'
        p.write_text(p.read_text(encoding='utf-8-sig').replace('NOT AN AUTHENTIC SIMAPRO EXPORT; FORMAT ONLY DEMONSTRATION','Products'),encoding='utf-8')
        parsed=desktop9.parse_native(p.name)
        self.assertEqual(parsed['sections'][0]['Comment'],['Products'])

    def test_existing_manifest_is_not_overwritten(self):
        mapping=self.approve_mapping()
        manifest=self.root/'outputs/simapro9_import_CANDIDATE.manifest.json'
        manifest.write_text('KEEP',encoding='utf-8')
        with self.assertRaises(FileExistsError):
            desktop9.build_native_import_candidate('desktop9_simple_lci_DEMO.csv',mapping,'native_template_FORMAT_ONLY_NOT_AUTHENTIC.csv')
        self.assertEqual(manifest.read_text(),'KEEP')

    def test_empty_result_provenance_is_rejected(self):
        rows=[dict(scenario=sc,indicator='GWP',value='5',unit='kg CO2 eq',method='',database='',
                   system_model='',functional_unit='',source_file='raw.csv',result_stage='characterization')
              for sc in ('baseline','alternative')]
        with (self.root/'bad_results.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=desktop9.RESULT_IMPORT_FIELDS);w.writeheader();w.writerows(rows)
        with self.assertRaises(ValueError):
            desktop9.compare_verified_results('bad_results.csv','baseline')

    def test_mixed_result_stage_is_rejected(self):
        rows=[dict(scenario=sc,indicator='GWP',value='5',unit='kg CO2 eq',method='m',database='db',
                   system_model='cutoff',functional_unit='1 kg',source_file='raw.csv',result_stage=stage)
              for sc,stage in (('baseline','characterization'),('alternative','normalization'))]
        with (self.root/'bad_results.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=desktop9.RESULT_IMPORT_FIELDS);w.writeheader();w.writerows(rows)
        with self.assertRaises(ValueError):
            desktop9.compare_verified_results('bad_results.csv','baseline')

    def test_failed_batch_does_not_leave_partial_files(self):
        mapping=self.approve_mapping()
        p=self.root/'desktop9_simple_lci_DEMO.csv'
        with p.open('a',encoding='utf-8') as f:
            f.write('P01,DEMO materials recovery,F11,DEMO waste,waste_output,0.1,kg,,,CN,DEMO ONLY,waste\n')
        with self.assertRaises(ValueError):
            desktop9.prepare_batch_scenarios(p.name,mapping,'native_template_FORMAT_ONLY_NOT_AUTHENTIC.csv',
                                            'P01','F04',[0.9,1.1],'outputs/bad_batch')
        self.assertFalse((self.root/'outputs/bad_batch').exists())

    def test_native_encoding_must_be_explicit(self):
        p=self.root/'native_template_FORMAT_ONLY_NOT_AUTHENTIC.csv'
        p.write_bytes(p.read_text(encoding='utf-8-sig').replace('DEMO PROCESS','中文过程').encode('gbk'))
        with self.assertRaises(UnicodeError):
            desktop9.parse_native(p.name)
        parsed=desktop9.parse_native(p.name,'gbk')
        self.assertEqual(parsed['sections'][0]['Process name'],['中文过程'])

if __name__=='__main__':unittest.main()
