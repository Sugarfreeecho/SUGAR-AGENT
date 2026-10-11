import hashlib
import io
import json
import sys
import tempfile
import threading
import unittest
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments import Experiments
from server import ReplayServer, report_zip


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        versions = json.loads((ROOT / 'versions/manifest.json').read_text(encoding='utf8'))['versions']
        self.versions = {v['version']: v for v in versions}
        self.engine = Experiments(ROOT, self.versions)

    def test_default_bytes_and_all_off_are_guarded_and_reversible(self):
        config = self.versions['20261007']
        for kind in ('js', 'css'):
            path = ROOT / 'versions/20261007/site' / config[kind].lstrip('/')
            before = path.read_bytes()
            baseline, receipt = self.engine.asset('20261007', kind)
            self.assertEqual(before, baseline)
            self.assertEqual(receipt['served_sha256'], config[kind + '_sha256'])
            off, changed = self.engine.asset('20261007', kind, self.engine.ids)
            self.assertNotEqual(off, before)
            self.assertTrue(changed['operations'])
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(self.engine.asset('20261007', kind)[0], before)
        all_off = self.engine.config('20261007', self.engine.ids)
        self.assertIn('attachSessionEventStream group lookup', [op['name'] for op in all_off['covered_operations']])
        self.assertIn('preview click binding', [op['name'] for op in all_off['covered_operations']])
        self.assertTrue(all(op['feature'] in ('auto_follow','smooth_follow') for op in all_off['source_operations']))
        self.assertEqual(all_off['plugin_version'], '20261004')
        self.assertEqual(self.engine.config('20261007')['plugin_version'], '20261007')
        self.assertNotEqual(all_off['fingerprint'], self.engine.config('20261007')['fingerprint'])
        self.assertEqual(self.engine.disabled('20261007','size_motion,collapsed_layout,size_motion'), ('collapsed_layout','size_motion'))
        with self.assertRaises(ValueError): self.engine.disabled('20261004','size_motion')
        with self.assertRaises(ValueError): self.engine.disabled('20261007','unknown')

    def test_single_switches_only_install_their_own_operations(self):
        for feature in self.engine.features:
            with self.subTest(feature=feature['id']):
                cfg = self.engine.config('20261007', (feature['id'],))
                self.assertEqual([op['feature'] for op in cfg['source_operations']], [feature['id']] * len(feature['source']))
                restored = feature.get('restore_assets', {})
                self.assertEqual(len(cfg['js']['operations']), len(feature['module']) + int('js' in restored))
                self.assertEqual(len(cfg['css']['operations']), int(bool(feature['css'])) + int('css' in restored))
                self.assertEqual(cfg['plugin_version'], '20261004' if feature['id'] in ('review_updates','frontend_bundle') else '20261007')

    def test_complete_baseline_and_crossed_assets_are_exact_archived_bytes(self):
        baseline = self.engine.config('20261007', ('frontend_bundle',))
        self.assertEqual(baseline['asset_versions'], dict.fromkeys(('js','css','html','plugin'), '20261004'))
        self.assertEqual(baseline['source_operations'], [])
        self.assertEqual(baseline['follow_mode'], 'smooth')
        for disabled, kind in [(('frontend_bundle',),'js'),(('frontend_bundle',),'css'),(('js_bundle',),'js'),(('css_bundle',),'css')]:
            actual, receipt = self.engine.asset('20261007', kind, disabled)
            original = self.engine.asset('20261004',kind)[0]
            self.assertEqual(actual,original)
            self.assertEqual(receipt['source_version'],'20261004')
        self.assertEqual(self.engine.asset('20261007','css',('js_bundle',))[0],self.engine.asset('20261007','css')[0])
        self.assertEqual(self.engine.config('20261007',('css_bundle',))['asset_versions']['js'],'20261007')

    def test_whole_modules_cover_partial_patches_and_keep_follow_controls(self):
        off=('session_modules','stream_pipeline','history_module','context_refresh','process_reuse','review_updates','history_anchor','sidebar_rendering','auto_follow')
        cfg=self.engine.config('20261007',off)
        covered={op['feature'] for op in cfg['covered_operations']}
        self.assertTrue({'context_refresh','process_reuse','review_updates','history_anchor','sidebar_rendering'} <= covered)
        self.assertEqual(cfg['follow_mode'],'off')
        self.assertTrue(any(op['feature']=='auto_follow' for op in cfg['source_operations']))
        whole=[op['file'] for op in cfg['source_operations'] if op.get('whole_module')]
        self.assertEqual(len(whole),len(set(whole)))
        # The two controls use the same archived listener deletion only once.
        js,receipt=self.engine.asset('20261007','js',('css_bundle','overflow_switch'))
        self.assertEqual(len(receipt['operations']),2)

    def test_served_assets_html_and_plugin_version_agree(self):
        with tempfile.TemporaryDirectory() as temp:
            server = ReplayServer(0,Path(temp))
            thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            def get(path, referer=None):
                headers = {'Referer':server.url+referer} if referer else {}
                with urllib.request.urlopen(urllib.request.Request(server.url+path,headers=headers)) as response: return response.read()
            try:
                off='overflow_switch,review_updates,size_motion'
                page='/view/20261007/?exp_off='+off
                html=get(page).decode()
                canonical='size_motion,overflow_switch,review_updates'
                self.assertIn('/v/20261007/assets/main-B_mPBPj8.js?exp_off='+canonical,html)
                for kind in ('js','css'):
                    expected, receipt=server.experiments.asset('20261007',kind,('size_motion','overflow_switch','review_updates'))
                    actual=get('/v/20261007'+self.versions['20261007'][kind]+'?exp_off='+off)
                    self.assertEqual(actual,expected)
                    self.assertEqual(hashlib.sha256(actual).hexdigest(),receipt['served_sha256'])
                extensions=json.loads(get('/api/extensions',page))['ui_contributions'][0]['renderer']
                for kind in ('module','style'):
                    url=extensions[kind]
                    self.assertTrue(url.startswith('/plugin-assets/change-review/'))
                    self.assertIn('replay_version=20261007',url)
                    actual=get(url)  # explicit query works even without a Referer
                    suffix='js' if kind=='module' else 'css'
                    expected=(ROOT/'versions/20261004/plugins/change-review/web'/('change-review.'+suffix)).read_bytes()
                    self.assertEqual(actual,expected)
                self.assertEqual(hashlib.sha256(get('/v/20261004'+self.versions['20261004']['js'])).hexdigest(),self.versions['20261004']['js_sha256'])
                old_page=get('/view/20261007/?exp_off=frontend_bundle').decode()
                self.assertIn('v5.20261004',old_page)
                self.assertNotIn('id="session-list-head"',old_page)
                self.assertIn('/v/20261007/assets/main-B_mPBPj8.js?exp_off=frontend_bundle',old_page)
                self.assertEqual(get('/v/20261007'+self.versions['20261007']['js']+'?exp_off=frontend_bundle'),self.engine.asset('20261004','js')[0])
            finally:
                server.shutdown();server.server_close();thread.join()

    def test_report_identifies_configuration(self):
        cfg=self.engine.config('20261007',('collapsed_layout',))
        cfg['ready']=True
        record={'record_id':'sample','version':'20261007','experiments':cfg,'assets':{'served_js_sha256':cfg['js']['served_sha256'],'served_css_sha256':cfg['css']['served_sha256']}}
        with zipfile.ZipFile(io.BytesIO(report_zip([record]))) as z:
            table=z.read('summary.csv').decode('utf-8-sig')
            self.assertIn('experiment_fingerprint',table)
            self.assertIn(cfg['fingerprint'],table)
            self.assertIn('collapsed_layout',table)
            self.assertEqual(json.loads(z.read('records/sample.json'))['experiments']['disabled'],['collapsed_layout'])


if __name__ == '__main__': unittest.main()
