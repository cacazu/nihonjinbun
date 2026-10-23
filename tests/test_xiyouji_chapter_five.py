"""Check chapter five against its fixed-revision source and editorial contract."""
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
    return hashlib.sha256(text.encode()).hexdigest()

class ChapterFiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load_document(BOOK / 'xiyouji-chapter-005-zh-ja.yaml')
        cls.manifest = json.loads((BOOK / 'verification/xiyouji-chapter-005-manifest-1455554.json').read_text())
        cls.segments = cls.doc['segments']

    def test_fixed_source_complete(self):
        m = self.manifest
        self.assertEqual('1455554', m['source_revision'])
        self.assertEqual('2018-05-12T06:59:00Z', m['source_revision_timestamp'])
        lines = {e['line']: e['text'] for e in m['fixed_source_lines']}
        self.assertEqual(list(range(116, 187)), list(lines))
        expected = [('heading', [116,117], lines[116]+'\n'+lines[117])]
        i=121
        while i<=186:
            if not lines[i].strip():
                i+=1
                continue
            nums=list(range(135,140)) if i==135 else [167,168] if i==167 else [i]
            expected.append(('verse' if i in (126,135,144,163,167,175,184) else 'paragraph', nums, '\n'.join(lines[n].lstrip() for n in nums)))
            i=nums[-1]+1
        self.assertEqual(40,len(expected))
        self.assertEqual(40,len(self.segments))
        self.assertEqual(40,len(m['units']))
        self.assertEqual(6356,sum(len(s[2]) for s in expected))
        self.assertEqual(6356,m['source_codepoint_count'])
        self.assertEqual([],m['display_variants'])
        snapshot='\n\n'.join(s[2] for s in expected)+'\n'
        self.assertEqual(snapshot,(ROOT/m['source_snapshot']).read_text())
        self.assertEqual('46033bf7ea88880503c001446bcc5270689cb2af81a74b0811b0387b2fc918bf',sha(snapshot))
        self.assertEqual(sha(snapshot),self.doc['sources'][0]['sha256'])
        for i,((kind,nums,source),segment,unit) in enumerate(zip(expected,self.segments,m['units'])):
            self.assertEqual(f'xy-ch05-{i+1:03}',segment['id'])
            self.assertEqual(segment['id'],unit['id'])
            self.assertEqual(kind,segment['kind'])
            self.assertEqual(nums,unit['fixed_source_lines'])
            self.assertEqual(source,segment['source_text'])
            self.assertEqual(sha(source),unit['source_sha256'])
            self.assertEqual(len(source),unit['source_codepoints'])
            self.assertEqual(i,segment['source_locations'][0]['source_sequence'])
            self.assertTrue(segment['translation_ja'].strip())

    def test_verses_and_closing(self):
        numbers=[5,12,15,27,29,34,39]
        ids=[f'xy-ch05-{n:03}' for n in numbers]
        self.assertEqual(ids,[s['id'] for s in self.segments if s['kind']=='verse'])
        self.assertEqual(ids,[g['members'][0]['segment_id'] for g in self.doc['groups']])
        self.assertEqual(5,len(self.segments[11]['source_text'].splitlines()))
        self.assertEqual(5,len(self.segments[11]['translation_ja'].splitlines()))
        self.assertEqual(2,len(self.segments[28]['source_text'].splitlines()))
        self.assertEqual('畢竟天曉後如何處治，且聽下回分解。',self.segments[-1]['source_text'])
        self.assertIn('次回',self.segments[-1]['translation_ja'])

    def test_schema_and_review_honesty(self):
        self.assertEqual([],validate_document(self.doc,ROOT))
        self.assertEqual('in_progress',self.doc['workflow']['full_review']['status'])
        self.assertNotIn('completed_at',self.doc['workflow']['full_review'])
        self.assertEqual('CC-BY-SA-4.0',self.doc['metadata']['translation_rights']['license_id'])
        self.assertIn('専門家による独立校訂は未実施','\n'.join(self.doc['metadata']['reader_notes_ja']))

    def test_context_names_and_speaker_labels(self):
        for s in self.segments:
            self.assertIsNone(re.search(r'^「',s['translation_ja'],re.M),s['id'])
            self.assertIsNone(re.search(r'^(孫悟空|美猴王|猴王|大聖|悟空)「',s['translation_ja'],re.M),s['id'])
        self.assertIn('九曜星官「命知らずの弼馬温',self.segments[31]['translation_ja'])
        self.assertIn('酒造りの者たちと仙官たち「',self.segments[23]['translation_ja'])
        self.assertIn('崩・芭の二将「',self.segments[20]['translation_ja'])
        self.assertIn('仙使「',self.segments[7]['translation_ja'])

    def test_quantities_and_unresolved_details(self):
        expected={6:['三千六百','千二百','三千年','六千年','九千年','淡い黄色'],8:['赤い衣','青い衣','白い衣','黒い衣','紫の衣','黄色い衣','緑の衣','二寸'],10:['西天の仏老','南極観音','崇恩聖帝','北極玄霊','黄極黄角大仙','九塁'],18:['五つの瓢箪'],20:['半年','天上の一日','下界では一年'],22:['左右の脇','両手'],23:['一昼夜','二籠','三籠'],25:['十万','十八'],32:['一丈二尺','十悪'],35:['辰の刻'],36:['五人の天王'],37:['一万','三千'],38:['一匹も捕まえていなかった']}
        for num,phrases in expected.items():
            for phrase in phrases:self.assertIn(phrase,self.segments[num-1]['translation_ja'])
        for num in (10,18,23,34):self.assertEqual('open',self.segments[num-1]['issues'][0]['status'])
        self.assertIn('楮白槍',self.segments[33]['translation_ja'])
        self.assertIn('四明鏟',self.segments[33]['translation_ja'])
        self.assertIn('𤛮',self.segments[37]['source_text'])

    def test_new_voice_profiles(self):
        text=(BOOK/'README.md').read_text()
        profiles=dict(re.findall(r'^### ([^\n]+)\n(.*?)(?=^### |^## |\Z)',text,re.M|re.S))
        names=['許旌陽真人','蟠桃園の土地神','七衣仙女','蟠桃園の仙使','赤脚大仙','王母','太上老君','酒造りの者たちと仙官たち','四大天師','斉天大聖府の仙吏','糾察霊官','崩・芭の二将','九曜星官']
        for name in names:
            self.assertIn(name,profiles)
            self.assertEqual(['1','2','3'],re.findall(r'^([123])\. ',profiles[name],re.M))
            self.assertIn('根拠：第五回 xy-ch05-',profiles[name])
        self.assertIn('創作の口調見本',text)

if __name__=='__main__':unittest.main()
