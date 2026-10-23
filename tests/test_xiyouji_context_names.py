"""Scene boundaries, quote preservation, and source immutability for chapters 1–4."""
import re
import subprocess
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '57dcd51727202083a53e6f383789cf118d1974e2'


def quotations(text):
    # Compare across the entire chapter: a speech can continue in the next segment.
    result, start, depth = [], 0, 0
    for i, char in enumerate(text):
        if char == '「':
            if depth == 0:
                start = i
            depth += 1
        elif char == '」':
            depth -= 1
            if depth == 0:
                result.append(text[start:i + 1])
    assert depth == 0
    return result


class ContextNamesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs, cls.old = {}, {}
        for chapter in range(1, 5):
            rel = f'translations/wu-chengen/xiyouji-chapter-{chapter:03}-zh-ja.yaml'
            cls.docs[chapter] = yaml.safe_load((ROOT / rel).read_text())
            cls.old[chapter] = yaml.safe_load(subprocess.check_output(
                ['git', 'show', f'{BASELINE}:{rel}'], cwd=ROOT))
        cls.text = {s['id']: s['translation_ja'] for doc in cls.docs.values() for s in doc['segments']}

    def test_all_source_fields_order_and_quotes_preserved(self):
        for chapter, doc in self.docs.items():
            old = self.old[chapter]
            for key in ('sources', 'scope', 'sections'):
                self.assertEqual(old[key], doc[key])
            self.assertEqual(len(old['segments']), len(doc['segments']))
            for a, b in zip(old['segments'], doc['segments']):
                self.assertEqual({k:v for k,v in a.items() if k != 'translation_ja'},
                                 {k:v for k,v in b.items() if k != 'translation_ja'}, a['id'])
            self.assertEqual(quotations('\n'.join(s['translation_ja'] for s in old['segments'])),
                             quotations('\n'.join(s['translation_ja'] for s in doc['segments'])))

    def test_kingship_and_naming_within_first_chapter(self):
        self.assertIn('石猿は王位に就き', self.text['xy-ch01-019'])
        self.assertIn('美猴王は尋ねた。\n美猴王「', self.text['xy-ch01-024'])
        naming = self.text['xy-ch01-049']
        self.assertIn('美猴王は答えた。\n美猴王「', naming)
        self.assertIn('孫悟空は笑った。\n孫悟空「', naming)
        self.assertNotIn('猿王', naming)

    def test_office_resignation_and_great_sage(self):
        self.assertIn('臣下たちが恩に謝するよう促しても、弼馬温は', self.text['xy-ch04-005'])
        self.assertIn('弼馬温は御馬監で', self.text['xy-ch04-006'])
        resignation = self.text['xy-ch04-009']
        self.assertEqual(5, len(re.findall(r'^弼馬温「', resignation, re.M)))
        self.assertIn('孫悟空が仙人の名簿に載り、弼馬温の官にある', resignation)
        self.assertIn('孫悟空「', self.text['xy-ch04-010'])
        declaration = self.text['xy-ch04-011']
        self.assertNotIn('斉天大聖「', declaration)
        self.assertIn('これからは俺を斉天大聖とだけ呼べ', declaration)
        for number in ('013', '015', '017', '021', '024', '026', '029', '030', '031'):
            self.assertIn('斉天大聖「', self.text['xy-ch04-' + number])
            self.assertNotIn('孫悟空「', self.text['xy-ch04-' + number])
        self.assertIn('獼猴王「', self.text['xy-ch04-026'])

    def test_other_characters_and_places(self):
        for segment, text in [('xy-ch02-002', '須菩提祖師'), ('xy-ch03-009', '敖広は尋ねた'),
                              ('xy-ch03-028', '太白金星（太白長庚星）'), ('xy-ch04-011', '独角鬼王は衣を'),
                              ('xy-ch04-018', '李天王は諫めを'), ('xy-ch04-023', '哪吒と斉天大聖'),
                              ('xy-ch04-032', '斉天大聖府')]:
            self.assertIn(text, self.text[segment])

    def test_verse_exceptions_and_documented_policy(self):
        before = {s['id']: s['translation_ja'] for s in self.old[4]['segments']}
        for s in self.docs[4]['segments']:
            if s['kind'] == 'verse':
                self.assertEqual(before[s['id']], s['translation_ja'])
        skill = (ROOT / '.agents/skills/translation-dialogue/SKILL.md').read_text()
        book = (ROOT / 'translations/wu-chengen/README.md').read_text()
        self.assertIn('同じ場面の地の文と発言者ラベルは同じ呼称', skill)
        for term in ('xy-ch01-049', 'xy-ch04-005', 'xy-ch04-009', 'xy-ch04-011', 'xy-ch04-031', '韻文'):
            self.assertIn(term, book)


if __name__ == '__main__':
    unittest.main()
