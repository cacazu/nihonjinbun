"""Guard chapter 4 against the independently captured fixed-edition text."""
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


class ChapterFourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load_document(BOOK / 'xiyouji-chapter-004-zh-ja.yaml')
        cls.manifest = json.loads((BOOK / 'verification/xiyouji-chapter-004-manifest-2449093.json').read_text())
        cls.segments = {s['id']: s for s in cls.doc['segments']}

    def test_complete_fixed_source_and_snapshot(self):
        m = self.manifest
        lines = {entry['line']: entry['text'] for entry in m['fixed_source_lines']}
        self.assertEqual(list(range(117, 173)), list(lines))
        self.assertEqual('2449093', m['source_revision'])
        self.assertEqual('2024-08-23T03:20:00Z', m['source_revision_timestamp'])
        self.assertIn('oldid=2449093', m['fixed_url'])
        self.assertEqual([
            {'fixed_line': 131, 'before': '喂', 'after': '餵'},
            {'fixed_line': 153, 'before': '斗', 'after': '鬥'},
        ], m['display_variants'])
        for variant in m['display_variants']:
            line = variant['fixed_line']
            self.assertEqual(1, lines[line].count(variant['before']))
            lines[line] = lines[line].replace(variant['before'], variant['after'])
        expected = [('heading', [117, 118], lines[117] + '\n' + lines[118])]
        i = 121
        while i <= 172:
            if not lines[i].strip():
                i += 1
                continue
            if i == 137:
                expected.append(('verse', list(range(137, 142)), '\n'.join(lines[n].lstrip() for n in range(137, 142))))
                i = 142
                continue
            expected.append(('verse' if i in (124, 128, 143, 151, 153, 170) else 'paragraph', [i], lines[i].lstrip()))
            i += 1
        self.assertEqual(34, len(expected))
        self.assertEqual(34, m['source_segment_count'])
        self.assertEqual(34, len(self.doc['segments']))
        self.assertEqual(34, len(m['units']))
        self.assertEqual(6726, sum(len(item[2]) for item in expected))
        self.assertEqual(6726, m['source_codepoint_count'])
        snapshot = '\n\n'.join(item[2] for item in expected) + '\n'
        self.assertEqual(snapshot, (ROOT / m['source_snapshot']).read_text())
        self.assertEqual(sha(snapshot), m['source_snapshot_sha256'])
        self.assertEqual(sha(snapshot), self.doc['sources'][0]['sha256'])
        self.assertEqual('fb121d43cabcb1b255818706e870e6d2a73568b995c84f557e64b04b16459922', sha(snapshot))
        for index, ((kind, source_lines, source), segment, unit) in enumerate(zip(expected, self.doc['segments'], m['units'])):
            expected_id = f'xy-ch04-{index + 1:03}'
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

    def test_all_seven_verse_passages_and_closing(self):
        verse_ids = ['xy-ch04-' + x for x in ('004', '007', '014', '016', '020', '022', '033')]
        self.assertEqual(verse_ids, [s['id'] for s in self.doc['segments'] if s['kind'] == 'verse'])
        self.assertEqual(verse_ids, [g['members'][0]['segment_id'] for g in self.doc['groups'] if g['kind'] == 'poem'])
        self.assertEqual(5, len(self.segments['xy-ch04-014']['source_text'].splitlines()))
        self.assertEqual(5, len(self.segments['xy-ch04-014']['translation_ja'].splitlines()))
        self.assertEqual('畢竟不知向後如何，且聽下回分解。', self.segments['xy-ch04-034']['source_text'])
        self.assertIn('次回', self.segments['xy-ch04-034']['translation_ja'])
        # The chapter has spoken memorials, not separately authored written petitions.
        self.assertFalse(any(g['id'].startswith('petition-') for g in self.doc['groups']))

    def test_dialogue_speaker_order(self):
        expected = {
            '002': ['孫悟空', '孫悟空', '太白金星', '孫悟空', '太白金星'],
            '003': ['太白金星'],
            '005': ['太白金星', '玉帝', '孫悟空', '仙卿たち', '玉帝', '仙卿たち', '武曲星君', '玉帝'],
            '009': ['孫悟空', '監官たち', '孫悟空', '監官たち', '孫悟空', '監官たち', '孫悟空', '監官たち', '孫悟空'],
            '010': ['孫悟空', '猿たち', '孫悟空', '猿たち', '孫悟空', '猿たち'],
            '011': ['報告者', '孫悟空', '孫悟空', '独角鬼王', '独角鬼王', '孫悟空', '独角鬼王', '孫悟空', '孫悟空'],
            '012': ['監丞と監副', '増長天王', '玉帝', '李天王と哪吒'],
            '013': ['巨霊神', '妖怪たち', '孫悟空', '妖怪たち', '孫悟空'],
            '015': ['巨霊神', '孫悟空', '巨霊神', '孫悟空', '巨霊神'],
            '017': ['孫悟空'],
            '018': ['巨霊神', '李天王', '哪吒'],
            '021': ['孫悟空', '哪吒', '孫悟空', '哪吒', '孫悟空', '哪吒', '孫悟空', '孫悟空'],
            '024': ['孫悟空'],
            '025': ['哪吒', '李天王', '哪吒', '李天王'],
            '026': ['孫悟空', '牛魔王', '蛟魔王', '鵬魔王', '獅狔王', '獼猴王', '禺狨王'],
            '027': ['李天王と哪吒', '玉帝', '哪吒', '玉帝'],
            '028': ['太白金星', '玉帝', '太白金星', '玉帝'],
            '029': ['太白金星', '妖怪たち', '孫悟空', '孫悟空'],
            '030': ['太白金星', '孫悟空', '太白金星'],
            '031': ['太白金星', '玉帝', '孫悟空'],
        }
        # Speaker identity is unchanged; displayed names follow the scene's status.
        for number, labels in expected.items():
            name = '弼馬温' if number == '009' else '斉天大聖' if int(number) >= 13 else '孫悟空'
            expected[number] = [name if label == '孫悟空' else label for label in labels]
        speakers = set(x for items in expected.values() for x in items)
        pattern = r'^(' + '|'.join(sorted(map(re.escape, speakers), key=len, reverse=True)) + ')「'
        for number, labels in expected.items():
            text = self.segments['xy-ch04-' + number]['translation_ja']
            self.assertEqual(labels, re.findall(pattern, text, re.M), number)
            self.assertIsNone(re.search(r'^「', text, re.M), number)

    def test_rare_names_quantities_and_quotation_reservation(self):
        ja = {key: value['translation_ja'] for key, value in self.segments.items()}
        for name in ('飛𦑭', '虎𩤲'):
            self.assertIn(name, self.segments['xy-ch04-007']['source_text'])
            self.assertIn(name, ja['xy-ch04-007'])
        self.assertIn('獅狔王', ja['xy-ch04-026'])
        self.assertNotIn('獅駝王', ja['xy-ch04-026'])
        self.assertIn('𤟹狨王', self.segments['xy-ch04-026']['source_text'])
        self.assertIn('回天奏道：『大聖立一竿旗，要做齊天大聖。眾武將', self.segments['xy-ch04-030']['source_text'])
        self.assertIn('太白金星本人の自称', self.segments['xy-ch04-030']['issues'][0]['message_ja'])
        for number in ('004', '007', '026', '030'):
            issue = self.segments['xy-ch04-' + number]['issues'][0]
            self.assertEqual(('uncertain_translation', 'open'), (issue['kind'], issue['status']))
        for number, phrases in {
            '004': ('三十三', '七十二'),
            '006': ('千匹',),
            '010': ('天上の一日', '下界の一年'),
            '021': ('刺繍の毬', '火の輪', '三つの頭', '六本の腕'),
            '023': ('三十合',),
            '026': ('平天大聖', '覆海大聖', '混天大聖', '移山大聖', '通風大聖', '駆神大聖'),
            '031': ('二瓶', '十輪', '安静司', '寧神司'),
        }.items():
            for phrase in phrases:
                self.assertIn(phrase, ja['xy-ch04-' + number])
        for phrase in ('乾坤圏', '風火輪'):
            self.assertNotIn(phrase, ja['xy-ch04-021'])

    def test_new_voice_profiles_have_three_examples(self):
        text = (BOOK / 'README.md').read_text()
        profiles = dict(re.findall(r'^### ([^\n]+)\n(.*?)(?=^### |^## |\Z)', text, re.M | re.S))
        expected = {
            '天界の仙卿たち', '武曲星君', '御馬監の監官たち', '花果山の報告者',
            '独角鬼王', '御馬監の監丞と監副', '増長天王', '巨霊神', '花果山の妖怪たち',
            '托塔李天王・李靖', '哪吒三太子', '牛魔王', '蛟魔王', '鵬魔王',
            '獅狔王', '獼猴王', '禺狨王（原文表記：𤟹狨王）',
        }
        self.assertTrue(expected <= profiles.keys())
        self.assertEqual(17, len(expected))
        for name in expected:
            self.assertEqual(['1', '2', '3'], re.findall(r'^([123])\. ', profiles[name], re.M), name)
            self.assertIn('根拠：第四回 xy-ch04-', profiles[name], name)
        self.assertIn('創作の口調見本', text)


if __name__ == '__main__':
    unittest.main()
