"""Independently guard chapter 3 against the captured fixed-edition source."""
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / 'translations/wu-chengen'
sys.path.insert(0, str(ROOT / 'scripts'))
from translation_yaml import load_document, validate_document


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class ChapterThreeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load_document(BOOK / 'xiyouji-chapter-003-zh-ja.yaml')
        cls.manifest = json.loads((BOOK / 'verification/xiyouji-chapter-003-manifest-2610943.json').read_text())
        cls.segments = {s['id']: s for s in cls.doc['segments']}

    def test_complete_fixed_source_and_snapshot(self):
        m = self.manifest
        lines = {entry['line']: entry['text'] for entry in m['fixed_source_lines']}
        self.assertEqual(list(range(117, 170)), list(lines))
        self.assertEqual('2610943', m['source_revision'])
        self.assertIn('oldid=2610943', m['fixed_url'])
        # Traditional display differs in these two characters only. Do not silently
        # normalize other original characters, including astral-plane rare forms.
        self.assertEqual([
            {'fixed_line': 141, 'before': '来', 'after': '來'},
            {'fixed_line': 144, 'before': '驼', 'after': '駝'},
        ], m['display_variants'])
        for variant in m['display_variants']:
            line = variant['fixed_line']
            self.assertEqual(1, lines[line].count(variant['before']))
            lines[line] = lines[line].replace(variant['before'], variant['after'])
        expected = [('heading', [117, 118], lines[117] + '\n' + lines[118])]
        i = 121
        while i <= 169:
            if not lines[i].strip():
                i += 1
                continue
            if i == 124:
                expected.append(('verse', list(range(124, 129)), '\n'.join(lines[n].lstrip() for n in range(124, 129))))
                i = 129
                continue
            expected.append(('verse' if i == 167 else 'paragraph', [i], lines[i].lstrip()))
            i += 1
        self.assertEqual(32, len(expected))
        self.assertEqual(32, m['source_segment_count'])
        self.assertEqual(32, len(self.doc['segments']))
        self.assertEqual(32, len(m['units']))
        self.assertEqual(7072, sum(len(item[2]) for item in expected))
        self.assertEqual(7072, m['source_codepoint_count'])
        snapshot = '\n\n'.join(item[2] for item in expected) + '\n'
        self.assertEqual(snapshot, (ROOT / m['source_snapshot']).read_text())
        self.assertEqual(sha(snapshot), m['source_snapshot_sha256'])
        self.assertEqual(sha(snapshot), self.doc['sources'][0]['sha256'])
        for index, ((kind, source_lines, source), segment, unit) in enumerate(zip(expected, self.doc['segments'], m['units'])):
            expected_id = f'xy-ch03-{index + 1:03}'
            self.assertEqual(expected_id, segment['id'])
            self.assertEqual(expected_id, unit['id'])
            self.assertEqual(kind, segment['kind'])
            self.assertEqual(kind, unit['kind'])
            self.assertEqual(source_lines, unit['fixed_source_lines'])
            self.assertEqual(source, segment['source_text'], expected_id)
            self.assertEqual(len(source), unit['source_codepoints'])
            self.assertEqual(sha(source), unit['source_sha256'])
            self.assertEqual(index, unit['source_sequence'])
            self.assertEqual(index, segment['source_locations'][0]['source_sequence'])
            self.assertEqual('source', segment['origin'])
            self.assertEqual(['zh-Hant'], segment['source_languages'])
            self.assertTrue(segment['translation_ja'].strip(), expected_id)
            self.assertNotIn(segment['translation_status'], ('pending', 'partial'))

    def test_schema_rights_and_honest_review_state(self):
        self.assertEqual([], validate_document(self.doc, ROOT))
        self.assertEqual('reviewing', self.doc['workflow']['stage'])
        self.assertEqual('in_progress', self.doc['workflow']['full_review']['status'])
        self.assertNotIn('completed_at', self.doc['workflow']['full_review'])
        self.assertEqual('public_domain', self.doc['sources'][0]['work_rights']['status'])
        self.assertEqual('CC-BY-SA-4.0', self.doc['sources'][0]['transcription_rights']['license_id'])
        self.assertEqual('CC-BY-SA-4.0', self.doc['metadata']['translation_rights']['license_id'])
        self.assertIn('専門家による独立校訂は未実施', '\n'.join(self.doc['metadata']['reader_notes_ja']))

    def test_poems_petitions_closing_and_unresolved_word(self):
        self.assertEqual(['xy-ch03-004', 'xy-ch03-031'], [s['id'] for s in self.doc['segments'] if s['kind'] == 'verse'])
        self.assertEqual(5, len(self.segments['xy-ch03-004']['source_text'].splitlines()))
        self.assertEqual(5, len(self.segments['xy-ch03-004']['translation_ja'].splitlines()))
        petitions = {g['id']: g for g in self.doc['groups']}
        self.assertEqual('xy-ch03-023', petitions['petition-aoguang']['members'][0]['segment_id'])
        self.assertEqual('xy-ch03-026', petitions['petition-dizang']['members'][0]['segment_id'])
        self.assertEqual('敖広', self.segments['xy-ch03-023']['attributions'][0]['name_ja'])
        self.assertEqual('地蔵王菩薩', self.segments['xy-ch03-026']['attributions'][0]['name_ja'])
        self.assertEqual('畢竟不知授個甚麼官爵，且聽下回分解。', self.segments['xy-ch03-032']['source_text'])
        issue = self.segments['xy-ch03-005']['issues'][0]
        self.assertEqual(('uncertain_translation', 'open'), (issue['kind'], issue['status']))
        self.assertIn('「毛」', self.segments['xy-ch03-005']['translation_ja'])
        self.assertIn('xy-ch03-005', self.doc['scope']['known_gaps'][0]['segment_ids'])

    def test_new_speakers_and_quantities(self):
        ja = {key: value['translation_ja'] for key, value in self.segments.items()}
        for speaker in ('夜叉', '敖広'):
            self.assertIn(speaker + '「', ja['xy-ch03-009'])
        for speaker in ('妃と竜女', '妃'):
            self.assertIn(speaker + '「', ja['xy-ch03-010'])
        for speaker in ('敖欽', '敖閏', '敖順'):
            self.assertIn(speaker + '「', ja['xy-ch03-013'])
        self.assertIn('十王「', ja['xy-ch03-018'])
        self.assertNotIn('閻羅王「', ja['xy-ch03-018'])
        self.assertIn('四健将と猿たち「', ja['xy-ch03-020'])
        self.assertIn('千里眼と順風耳「', ja['xy-ch03-028'])
        self.assertIn('太白金星「', ja['xy-ch03-029'])
        self.assertNotIn('四健将「', ja['xy-ch03-029'])  # 領諾 is indirect narration.
        self.assertNotIn('孫悟空（心中）', ja['xy-ch03-002'])
        self.assertIn('孫悟空（心中）', ja['xy-ch03-003'])
        for segment_id, phrases in {
            'xy-ch03-007': ('四万七千', '七十二'),
            'xy-ch03-009': ('三千六百斤', '七千二百斤'),
            'xy-ch03-011': ('一万三千五百斤',),
            'xy-ch03-019': ('千三百五十', '三百四十二'),
        }.items():
            for phrase in phrases:
                self.assertIn(phrase, ja[segment_id])
        for segment_id in ('xy-ch03-013', 'xy-ch03-023'):
            self.assertIn('邪魔したな、世話になった', ja[segment_id])

    def test_new_voice_profiles_have_three_examples(self):
        book = (BOOK / 'README.md').read_text()
        profiles = dict(re.findall(r'^### ([^\n]+)\n(.*?)(?=^### |^## |\Z)', book, re.M | re.S))
        expected = {
            '四匹の老猿（のちの四健将）', '海を巡る夜叉', '東海竜王・敖広',
            '竜王の妃と竜女', '南海竜王・敖欽', '西海竜王・敖閏', '北海竜王・敖順',
            '魂を取り立てる二人の使者', '冥界の鬼卒たち', '冥界の十王',
            '丘弘済真人', '葛仙翁天師', '太白金星（太白長庚星）', '地蔵王菩薩（奏状の書き手）',
        }
        self.assertTrue(expected <= profiles.keys())
        for name in expected:
            self.assertEqual(['1', '2', '3'], re.findall(r'^([123])\. ', profiles[name], re.M), name)
            self.assertIn('根拠：第三回 xy-ch03-', profiles[name], name)


if __name__ == '__main__':
    unittest.main()
