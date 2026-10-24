"""Story-first names, chronological reveals, and source preservation through chapter 20."""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from translation_yaml import load_document, JsonLoader
import yaml

BASELINE = 'a69dc9214bcf4b21d89738f2fd98758cde26d52c'
BOOK = ROOT / 'translations/wu-chengen'


def plain(text):
    return re.sub(r'（[ぁ-ゖァ-ヺー・ 　]+）', '', text)


class ReadableNamesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {n: load_document(BOOK / f'xiyouji-chapter-{n:03}-zh-ja.yaml')
                    for n in range(1, 21)}
        cls.text = {s['id']: plain(s['translation_ja'])
                    for d in cls.docs.values() for s in d['segments']}

    def test_all_originals_ids_order_and_sources_preserved(self):
        for n, doc in self.docs.items():
            rel = f'translations/wu-chengen/xiyouji-chapter-{n:03}-zh-ja.yaml'
            old = yaml.load(subprocess.check_output(['git', 'show', f'{BASELINE}:{rel}'], cwd=ROOT), Loader=JsonLoader)
            self.assertEqual(old['sources'], doc['sources'])
            self.assertEqual(old['sections'], doc['sections'])
            self.assertEqual([s['id'] for s in old['segments']], [s['id'] for s in doc['segments']])
            for a, b in zip(old['segments'], doc['segments']):
                for key in ('source_text', 'source_languages', 'source_locations', 'origin', 'kind'):
                    self.assertEqual(a.get(key), b.get(key), (a['id'], key))
            self.assertEqual('in_progress', doc['workflow']['full_review']['status'])

    def test_wukong_stays_recognizable_after_meeting_sanzang(self):
        self.assertIn('悟空「お師匠さまが来た！', self.text['xy-ch14-003'])
        for n in range(14, 21):
            body = '\n'.join(s['translation_ja'] for s in self.docs[n]['segments'] if s['kind'] not in ('heading', 'note_body'))
            self.assertNotRegex(body, r'(?:^|[\n。])(?:行者|孫行者|孫悟空)(?:（[^）]*）)?「')
            self.assertNotRegex(body, r'(?:^|[\n。])行者[はがのをと]')
        self.assertIn('あだ名をつけて行者と呼ぼう', self.text['xy-ch14-008'])
        self.assertIn('悟空は孫行者とも呼ばれるようになった', self.text['xy-ch14-008'])
        self.assertIn('行者とも呼ばれるようになった', self.text['xy-ch14-026'])
        self.assertIn('名は悟空、行者とも呼ばれている', self.text['xy-ch17-011'])
        self.assertIn('修行者らしく見える', self.text['xy-ch14-018'])
        self.assertIn('恵岸行者', self.text['xy-ch15-014'])
        self.assertIn('道端では悟空が笑い転げ、うれしくて', self.text['xy-ch15-029'])
        self.assertNotIn('は悟空は', self.text['xy-ch17-013'])
        self.assertNotIn('は観音菩薩は', self.text['xy-ch17-043'])

    def test_names_are_not_assigned_before_their_reveal(self):
        self.assertIn('美猴王は答えた', self.text['xy-ch01-049'])
        self.assertIn('孫悟空は笑った', self.text['xy-ch01-049'])
        self.assertIn('弼馬温「俺の弼馬温', self.text['xy-ch04-009'])
        self.assertIn('斉天大聖', self.text['xy-ch07-003'])
        self.assertIn('熊手の妖怪「', self.text['xy-ch08-034'])
        self.assertNotIn('福陵山', self.text['xy-ch08-034'])
        self.assertIn('法名を猪悟能とつけた', self.text['xy-ch08-038'])
        self.assertIn('空からの声「', self.text['xy-ch14-006'])
        self.assertIn('空からの声「', self.text['xy-ch15-006'])
        self.assertIn('声の主「', self.text['xy-ch09-014'])
        self.assertIn('私は南極星君', self.text['xy-ch09-014'])
        self.assertIn('空からの声「', self.text['xy-ch10-024'])
        self.assertIn('鬼卒たち「橋梁使者が', self.text['xy-ch11-018'])
        self.assertIn('男「長老、怖がることはありません', self.text['xy-ch13-027'])
        self.assertIn('山の下の声', self.text['xy-ch13-041'])
        self.assertNotIn('悟空', self.text['xy-ch13-041'])

    def test_one_person_does_not_become_two_through_aliases(self):
        self.assertNotIn('徐茂公', self.text['xy-ch11-024'])
        self.assertNotIn('李世勣', self.text['xy-ch11-024'])
        self.assertIn('尉遅恭を河南', self.text['xy-ch11-038'])
        self.assertIn('幼いころ江流児と呼ばれた玄奘', self.text['xy-ch12-031'])
        self.assertIn('金蝉の生まれ変わり、玄奘', self.text['xy-ch12-049'])
        self.assertIn('玉英の体に宿った李翠蓮', self.text['xy-ch12-003'])
        for sid in ('xy-ch12-003', 'xy-ch12-005', 'xy-ch12-006'):
            self.assertIn('李翠蓮「', self.text[sid])
            self.assertNotIn('玉英宮主「', self.text[sid])
        self.assertIn('太宗「妹よ', self.text['xy-ch12-003'])
        self.assertIn('三蔵は、難の中で悟空と八戒', self.text['xy-ch20-027'])
        self.assertIn('父親代わりのお師匠さまと、兄貴の悟空', self.text['xy-ch19-016'])

    def test_glosses_do_not_reveal_future_names(self):
        for o in self.docs[8]['lexicon']['first_occurrences']:
            if o['segment_id'] < 'xy-ch08-031':
                self.assertNotIn('沙悟浄', o.get('gloss_ja', ''))
            if o['segment_id'] < 'xy-ch08-038':
                self.assertNotIn('猪悟能', o.get('gloss_ja', ''))
        for o in self.docs[9]['lexicon']['first_occurrences']:
            if o['segment_id'] < 'xy-ch09-017':
                self.assertNotIn('玄奘', o.get('gloss_ja', ''))
        for o in self.docs[13]['lexicon']['first_occurrences']:
            if o['segment_id'] < 'xy-ch13-021':
                self.assertNotIn('太白金星', o.get('gloss_ja', ''))

    def test_chapter_first_wukong_annotation_follows_revised_body(self):
        for n in range(14, 21):
            doc = self.docs[n]
            item = next(o for o in doc['lexicon']['first_occurrences'] if o['form_id'] == 'xy-wukong-short-form')
            for s in doc['segments']:
                if s['kind'] in ('heading', 'note_body'):
                    continue
                match = re.search(r'(?<!孫)悟空', s['translation_ja'])
                if match:
                    self.assertEqual(s['id'], item['segment_id'])
                    self.assertEqual(match.start(), item['translation_span']['start'])
                    self.assertEqual('悟空（ごくう）', item['rendered_text'])
                    break


if __name__ == '__main__':
    unittest.main()
