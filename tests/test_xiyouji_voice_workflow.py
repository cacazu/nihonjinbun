"""Guard the documented reading order and the first two chapters' voice revision."""
import re
import subprocess
import sys
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from translation_yaml import load_document, validate_document

BASELINE = '862d03d597ea79812d911fd9ea73267b03292468'
BOOK = ROOT / 'translations/wu-chengen'

class VoiceWorkflowTests(unittest.TestCase):
    def test_entry_points_and_three_examples_per_profile(self):
        readme = (ROOT / 'README.md').read_text()
        agents = (ROOT / 'AGENTS.md').read_text()
        skill = (ROOT / '.agents/skills/translation-dialogue/SKILL.md').read_text()
        book = (BOOK / 'README.md').read_text()
        for text in (readme, agents):
            self.assertIn('.agents/skills/translation-dialogue/SKILL.md', text)
        self.assertIn('各作品フォルダの README.md', skill)
        self.assertIn('創作例', book)
        profiles = re.findall(r'^### ([^\n]+)\n(.*?)(?=^### |^## |\Z)', book, re.M | re.S)
        names = {name for name, _ in profiles}
        # Later chapters may add profiles; retain all 11 original profiles.
        original_names = {
            '孫悟空（石猿・美猴王と同一人物）', '須菩提祖師',
            '花果山の猿たち（さらわれた猿たちを含む）', '長腕の猿',
            '木こり', '童子', '兄弟子たち・弟子たち', '玉帝',
            '千里眼と順風耳', '混世魔王', '小妖怪',
        }
        self.assertTrue(original_names <= names)
        self.assertEqual(len(profiles), len(names), 'Duplicate voice profiles')
        for name, body in profiles:
            self.assertEqual(['1', '2', '3'], re.findall(r'^([123])\. ', body, re.M), name)
            self.assertIn('根拠：', body, name)

    def test_originals_ids_and_order_preserved(self):
        # This baseline predates chapter 3 and only guards the voice-only revision.
        for chapter in (1, 2):
            path = BOOK / f'xiyouji-chapter-{chapter:03}-zh-ja.yaml'
            rel = path.relative_to(ROOT).as_posix()
            old = yaml.safe_load(subprocess.check_output(['git', 'show', f'{BASELINE}:{rel}'], cwd=ROOT))
            current = load_document(path)
            for key in ('sources', 'scope', 'sections'):
                self.assertEqual(old[key], current[key], (path.name, key))
            old_segments, new_segments = old['segments'], current['segments']
            self.assertEqual([s['id'] for s in old_segments], [s['id'] for s in new_segments])
            for before, after in zip(old_segments, new_segments):
                # Only Japanese wording changes; all source metadata and identifiers stay intact.
                self.assertEqual({k:v for k,v in before.items() if k != 'translation_ja'},
                                 {k:v for k,v in after.items() if k != 'translation_ja'}, before['id'])
            self.assertEqual([], validate_document(current, ROOT))
            self.assertEqual('in_progress', current['workflow']['full_review']['status'])

    def test_speaker_boundaries_and_attribution(self):
        d = load_document(BOOK / 'xiyouji-chapter-002-zh-ja.yaml')
        segments = {s['id']: s['translation_ja'] for s in d['segments']}
        combined = '\n'.join(segments.values())
        self.assertNotIn('兄\n弟子', combined)
        self.assertNotIn('さらわれた\n猿', combined)
        self.assertIn('孫悟空「お師匠さま、私たちはここで話をしておりました。', segments['xy-ch02-024'])
        self.assertIn('弟子たち「隠してはおけません。', segments['xy-ch02-024'])
        self.assertNotIn('孫悟空（心中）', segments['xy-ch02-013'])
        self.assertIn('俺', segments['xy-ch02-029'])
        self.assertIn('私', segments['xy-ch02-022'])

if __name__ == '__main__':
    unittest.main()
