"""Frozen paragraph-gloss fingerprints; approved naming revisions refresh only affected chapters."""
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_reading_site as reader
from translation_yaml import load_document, validate_document
from test_reading_site import Elements


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def without_annotations(data):
    data = copy.deepcopy(data)
    segments = {s['id']: s for s in data['segments']}
    for item in reversed(data['lexicon']['first_occurrences']):
        segment = segments[item['segment_id']]
        start = item['translation_span']['start']
        end = start + len(item['rendered_text'])
        segment['translation_ja'] = (segment['translation_ja'][:start] +
                                     item['translation_span']['exact'] + segment['translation_ja'][end:])
        del item['rendered_text']
        item.pop('gloss_ja', None)
    def strip_spans(value):
        if isinstance(value, dict):
            value.pop('translation_span', None)
            for child in value.values():
                strip_spans(child)
        elif isinstance(value, list):
            for child in value:
                strip_spans(child)
    strip_spans(data)
    return data


class ParagraphGlossTests(unittest.TestCase):
    def test_published_chapters_preserve_content_explanations_and_references(self):
        expected = json.loads((ROOT / 'tests/fixtures/paragraph_glosses_before.json').read_text())
        for number, name in enumerate(reader.CHAPTERS, 1):
            with self.subTest(chapter=number):
                data = load_document(ROOT / 'translations/wu-chengen' / name)
                self.assertEqual([], validate_document(data, ROOT))
                # The original regression fingerprints cover chapters 1–10;
                # paragraph rendering below is checked for every published chapter.
                if str(number) in expected:
                    before = expected[str(number)]
                    self.assertEqual(before['content_without_annotations'], fingerprint(without_annotations(data)))
                    glosses = [[o['segment_id'], o['form_id'], o['gloss_ja']]
                               for o in data['lexicon']['first_occurrences'] if 'gloss_ja' in o]
                    self.assertEqual(before['gloss_count'], len(glosses))
                    self.assertEqual(before['glosses'], fingerprint(glosses))
                page = Elements(reader.render_chapter(data, number))
                for segment in data['segments']:
                    items = [o for o in data['lexicon']['first_occurrences'] if o['segment_id'] == segment['id']]
                    section, = page.by_id(segment['id'])
                    blocks = [node for node in page.nodes if node['attrs'].get('class') == 'paragraph-glosses'
                              and any(parent is section for parent in node['parents'])]
                    adopted = [o for o in items if 'gloss_ja' in o]
                    self.assertEqual(len(blocks), int(bool(adopted)))
                    if adopted:
                        block, = blocks
                        children = [node for node in page.nodes if node['parents'] and node['parents'][-1] is block]
                        self.assertEqual([node['text'] for node in children],
                                         [o['translation_span']['exact'] + '：' + o['gloss_ja'] for o in adopted])
                        text, = [node for node in page.nodes if node['attrs'].get('class') == 'story-text translation'
                                 and any(parent is section for parent in node['parents'])]
                        self.assertEqual(text['text'], segment['translation_ja'])
                        self.assertLess(page.nodes.index(text), page.nodes.index(block))
                    for item in items:
                        suffix = item['rendered_text'][len(item['translation_span']['exact']):]
                        self.assertNotIn('。', suffix)
                        self.assertNotIn('）（', suffix)
                        self.assertNotIn('推定', suffix)

    def test_glosses_escape_html_and_sort_by_body_position(self):
        segment = {'id': 's', 'kind': 'verse', 'translation_ja': '甲（こう）\n乙（おつ）'}
        items = [{'translation_span': {'start': 6, 'exact': '乙'}, 'gloss_ja': '<script>bad()</script>'},
                 {'translation_span': {'start': 0, 'exact': '甲<&'}, 'gloss_ja': '引用" & 意味'}]
        rendered = reader.render_segment(segment, [], {}, items)
        self.assertNotIn('<script>', rendered)
        page = Elements(rendered)
        block, = [n for n in page.nodes if n['attrs'].get('class') == 'paragraph-glosses']
        self.assertEqual(block['text'], '甲<&：引用" & 意味乙：<script>bad()</script>')
        self.assertEqual(page.by_id('s')[0]['text'], segment['translation_ja'] + block['text'])


if __name__ == '__main__':
    unittest.main()
