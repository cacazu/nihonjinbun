import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from translation_yaml import load_document, validate_document

PIN = 'ce1b9bc9904d3d973fc0b6bc03d01a6b0e896c07'
PREFIX = 'recovery/talleyrand/2026-10-10/source-volume-4'


def witness(file):
    return json.loads(subprocess.check_output(['git', 'show', f'{PIN}:{PREFIX}/{file}'], cwd=ROOT))


class VolumeFourSourceTests(unittest.TestCase):
    def test_original_contents_pages_link_to_the_matching_chapter_and_appendix(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-4-fr-ja.yaml')
        segments = {s['id']: s for s in doc['segments']}
        for sid, target, page in [('v04-u002419', 'v04-u000020', '3'),
                                  ('v04-u002420', 'v04-u001788', '481')]:
            links = [r for r in doc['references'] if r['from']['segment_id'] == sid
                     and r['kind'] == 'cross_reference' and r['status'] == 'verified'
                     and r['to'] == {'type': 'segment', 'id': target}]
            self.assertEqual(len(links), 1, sid)
            self.assertEqual(links[0]['from']['source_span']['exact'], page)
            self.assertTrue(links[0]['from']['translation_span']['exact'].endswith('ページ'))
            self.assertTrue(any(p.get('printed_page') == page
                                for p in segments[target]['source_locations']), target)
            self.assertFalse(any(i['status'] == 'open' for i in segments[sid].get('issues', [])))

    def test_protocol_lists_keep_their_points_and_note_membership(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-4-fr-ja.yaml')
        segments = {s['id']: s for s in doc['segments']}
        original = {u['id']: u for u in witness('units.json')}
        cases = [('78', range(2017, 2021)), ('312', range(2306, 2309))]
        for label, numbers in cases:
            ids = [f'v04-u{n:06d}' for n in numbers]
            with self.subTest(note_label=label):
                for number, sid in enumerate(ids, 1):
                    self.assertTrue(original[sid]['text'].startswith(f'{number}o '))
                    self.assertEqual(segments[sid]['source_text'], original[sid]['text'])
                    self.assertEqual(segments[sid]['kind'], 'list_item')
                    self.assertTrue(segments[sid]['translation_ja'].startswith(f'{"一二三四"[number - 1]}、'))
                self.assertTrue(any(g['kind'] == 'list' and g['members'] == [{'segment_id': sid} for sid in ids]
                                    for g in doc['groups']))
                self.assertTrue(any(n['label'] == label and all({'segment_id': sid} in n['body'] for sid in ids)
                                    for n in doc['notes']))

    def test_belgian_two_conditions_remain_one_numbered_list(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-4-fr-ja.yaml')
        ids = ['v04-u001247', 'v04-u001248']
        segments = {s['id']: s for s in doc['segments']}
        original = {u['id']: u for u in witness('units.json')}
        for number, sid in enumerate(ids, 1):
            self.assertTrue(original[sid]['text'].startswith(f'{number}o '))
            self.assertEqual(segments[sid]['kind'], 'list_item')
            self.assertTrue(segments[sid]['translation_ja'].startswith(f'{"一二"[number - 1]}、'))
        self.assertTrue(any(g['kind'] == 'list' and g['members'] == [{'segment_id': sid} for sid in ids]
                            for g in doc['groups']))

    def test_three_numbered_points_keep_each_list_together(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-4-fr-ja.yaml')
        segments = {s['id']: s for s in doc['segments']}
        original = {u['id']: u for u in witness('units.json')}
        cases = [
            (['v04-u001096', 'v04-u001097', 'v04-u001098'], ['第一に、', '第二に、', '第三に、']),
            (['v04-u001493', 'v04-u001494', 'v04-u001495'], ['一、', '二、', '三、']),
            (['v04-u001856', 'v04-u001857', 'v04-u001858'], ['一、', '二、', '三、']),
        ]
        for ids, labels in cases:
            with self.subTest(first_id=ids[0]):
                for number, sid in enumerate(ids, 1):
                    self.assertTrue(original[sid]['text'].startswith(f'»{number}o '))
                    self.assertEqual(segments[sid]['kind'], 'list_item')
                    self.assertTrue(segments[sid]['translation_ja'].startswith(labels[number - 1]))
                self.assertTrue(any(g['kind'] == 'list' and g['members'] == [{'segment_id': sid} for sid in ids]
                                    for g in doc['groups']))

    def test_quoted_couplet_preserves_verse_lines_and_first_line_indent(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-4-fr-ja.yaml')
        s = next(s for s in doc['segments'] if s['id'] == 'v04-u001092')
        original = next(u for u in witness('units.json') if u['id'] == s['id'])
        self.assertIn('<br/>', original['source_html'])
        self.assertIn('class="i4"', original['source_html'])
        self.assertEqual(s['source_text'], original['text'])
        self.assertEqual(s['kind'], 'verse')
        self.assertEqual(s['translation_ja'].count('\n'), 1)
        self.assertEqual(s['translation_ja'].split('\n')[0], '……そして認められるには、')
        self.assertTrue(any(g['kind'] == 'poem' and g['members'] == [{'segment_id': s['id']}]
                            for g in doc['groups']))
        self.assertTrue(any(a['side'] == 'source' and a['kind'] == 'indent' and a['columns'] == 4
                            and a['span']['exact'] == '... et pour être approuvés,'
                            for a in s.get('annotations', [])))
        self.assertTrue(any(a['side'] == 'translation' and a['kind'] == 'indent' and a['columns'] == 4
                            and a['span']['exact'] == s['translation_ja'].split('\n')[0]
                            for a in s.get('annotations', [])))

    def test_languages_follow_the_document_witnesses(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-4-fr-ja.yaml')
        self.assertEqual(doc['metadata']['original_languages'], ['fr', 'en'])
        segments = {segment['id']: segment for segment in doc['segments']}
        pairs = witness('documents-inventory.json')['paired_english_body_and_french_note_documents']
        english = {sid for pair in pairs for sid in pair['english_body_unit_ids']}
        english.add('v04-u000309')  # The first heading is English; the second is French.
        english.add('v04-u001898')  # Talleyrand's English salutation in a French letter.
        self.assertEqual(len(english), 15)
        for sid in english:
            self.assertEqual(segments[sid]['source_languages'], ['en'], sid)
        for pair in pairs:
            for sid in [pair['french_note_heading']['unit_id'], *pair['french_rendering_unit_ids']]:
                self.assertEqual(segments[sid]['source_languages'], ['fr'], sid)
        for sid in ['v04-u000067', 'v04-u000126', 'v04-u000560', 'v04-u001852', 'v04-u001860']:
            self.assertEqual(segments[sid]['source_languages'], ['fr'], sid)
        mixed_rows = {row['unit_id'] for row in witness('table-structures.json')['tables'][0]['rows']}
        for sid, segment in segments.items():
            if segment['origin'] == 'translator':
                self.assertIsNone(segment['source_text'], sid)
                self.assertEqual(segment['source_languages'], [], sid)
                continue
            if sid not in english and sid not in mixed_rows:
                self.assertEqual(segment['source_languages'], ['fr'], sid)

    def test_verified_printed_variants_keep_the_electronic_text_and_explain_readings(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-4-fr-ja.yaml')
        original = {unit['id']: unit['text'] for unit in witness('units.json')}
        segments = {segment['id']: segment for segment in doc['segments']}
        notes = {note['id']: note for note in doc['notes']}
        self.assertTrue(any(source['id'] == 'uc-v04-1891' and source['role'] == 'comparison'
                            for source in doc['sources']))
        for sid, reading in [('v04-u000128', 'nº 12'), ('v04-u000574', 'plusieurs membres'),
                             ('v04-u001109', '20 septembre 1831'), ('v04-u001145', 'Lord Holland')]:
            self.assertEqual(segments[sid]['source_text'], original[sid])
            variants = segments[sid].get('source_variants', [])
            self.assertTrue(any(reading in variant['text'] and
                                any(location['source_id'] == 'uc-v04-1891'
                                    for location in variant['source_locations'])
                                for variant in variants), sid)
            refs = [ref for ref in doc['references'] if ref['origin'] == 'translator'
                    and ref['from']['segment_id'] == sid and ref['to']['type'] == 'note']
            self.assertTrue(refs, sid)
            for ref in refs:
                self.assertEqual(notes[ref['to']['id']]['origin'], 'translator')
        self.assertIn('九月二十日', segments['v04-u001109']['translation_ja'])
        self.assertIn('ホランド卿', segments['v04-u001145']['translation_ja'])

    def test_duplicate_electronic_callout_keeps_source_and_one_printed_reference(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-4-fr-ja.yaml')
        segment = next(s for s in doc['segments'] if s['id'] == 'v04-u001644')
        original = next(u for u in witness('units.json') if u['id'] == segment['id'])
        self.assertEqual(segment['source_text'], original['text'])
        self.assertEqual(segment['source_text'].count('[359]'), 2)
        self.assertIsNotNone(segment['translation_ja'])
        self.assertEqual(segment['translation_ja'].count('[359]'), 1)
        self.assertTrue(any(v['text'].count('[359]') == 1 and
                            any(loc['source_id'] == 'uc-v04-1891' and loc['printed_page'] == '446'
                                for loc in v['source_locations'])
                            for v in segment.get('source_variants', [])))
        refs = [r for r in doc['references'] if r['from']['segment_id'] == segment['id']]
        original_refs = [r for r in refs if r['origin'] == 'source']
        self.assertEqual(len(original_refs), 1)
        self.assertEqual(original_refs[0]['to']['id'], 'v04-note-359')
        self.assertEqual(original_refs[0]['from']['translation_span']['exact'], '[359]')
        self.assertTrue(any(r['origin'] == 'translator' for r in refs))

    def test_note_fifteen_and_sixteen_record_the_inspected_printed_readings(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-4-fr-ja.yaml')
        segments = {s['id']: s for s in doc['segments']}
        original = {u['id']: u['text'] for u in witness('units.json')}
        for sid, printed in [('v04-u001926', '10 octobre 1811.'),
                             ('v04-u001927', 'reprochait en France')]:
            segment = segments[sid]
            self.assertEqual(segment['source_text'], original[sid])
            self.assertTrue(any(printed in v['text'] and
                                any(loc['source_id'] == 'uc-v04-1891' and loc['printed_page'] == '15'
                                    for loc in v['source_locations'])
                                for v in segment.get('source_variants', [])), sid)
            self.assertTrue(any(r['from']['segment_id'] == sid and r['origin'] == 'translator'
                                for r in doc['references']), sid)
        self.assertNotIn('$1', segments['v04-u001926']['translation_ja'])
        self.assertIn('一八一一年十月十日', segments['v04-u001926']['translation_ja'])

    def test_every_original_unit_is_retained_in_source_order(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-4-fr-ja.yaml')
        self.assertEqual([], validate_document(doc, ROOT))
        expected = witness('units.json')
        self.assertEqual(len(expected), 2421)
        actual = {}
        for segment in doc['segments']:
            for alignment in segment.get('source_alignment', []):
                span = alignment.get('source_span')
                text = segment['source_text'][span['start']:span['end']] if span else segment['source_text']
                ident = alignment['original_unit_id']
                actual[ident] = actual.get(ident, '') + text
        self.assertEqual(list(actual.items()), [(u['id'], u['text']) for u in expected])

    def test_original_notes_and_available_images_are_not_omitted(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-4-fr-ja.yaml')
        notes = {note['id']: note for note in doc['notes']}
        expected = witness('notes-inventory.json')
        self.assertEqual(len(expected), 410)
        for note in expected:
            actual = notes[f'v04-note-{note["label"]}']
            segments = {segment['id']: segment for segment in doc['segments']}
            source_ids = [alignment['original_unit_id'] for part in actual['body']
                          for alignment in segments[part['segment_id']].get('source_alignment', [])]
            self.assertEqual(list(dict.fromkeys(source_ids)), note['unit_ids'])
        for asset in doc['assets']:
            self.assertEqual(hashlib.sha256((ROOT / asset['path']).read_bytes()).hexdigest(), asset['sha256'])
        expected_assets = {item['sha256'] for figure in witness('illustrations-manifest.json')
                           for item in figure['assets']}
        self.assertTrue(expected_assets <= {asset['sha256'] for asset in doc['assets']})
        self.assertEqual(len(doc['assets']), 5)

    def test_figure_letters_and_unreadable_small_text_have_source_positions(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-4-fr-ja.yaml')
        segments = {s['id']: s for s in doc['segments']}
        assets = {a['id']: a for a in doc['assets']}
        publisher = next(f for f in doc['figures'] if f['id'] == 'v04-image-01')
        letters = [segments[sid] for sid in publisher.get('text_segment_ids', [])]
        self.assertEqual([s['source_text'] for s in letters], ['C·L'])
        self.assertTrue(all(s['kind'] == 'figure_text' and s['translation_ja'] for s in letters))
        self.assertEqual(letters[0]['source_locations'][0]['precision'], 'region')
        portrait = next(f for f in doc['figures'] if f['id'] == 'v04-image-02')
        self.assertEqual(portrait['caption_segment_ids'], ['v04-u000019'])
        image = assets[portrait['asset_id']]
        parent = assets[image['derived_from_asset_id']]
        self.assertEqual(image['processing'][0]['kind'], 'crop')
        crop = image['processing'][0]['crop']
        self.assertLessEqual(crop['x'] + crop['width'], parent['width'])
        self.assertLessEqual(crop['y'] + crop['height'], parent['height'])
        self.assertTrue(any(i['kind'] == 'unreadable' and i['status'] == 'open'
                            for i in segments['v04-u000019'].get('issues', [])))
        self.assertTrue(any('v04-u000019' in g.get('segment_ids', [])
                            for g in doc['scope']['known_gaps']))

    def test_navigation_retains_the_part_chapter_and_enclosure_hierarchy(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-4-fr-ja.yaml')
        sections = {s['id']: s for s in doc['sections']}
        segments = {s['id']: s for s in doc['segments']}
        part = sections['v04-section-part-10']
        self.assertEqual(part['kind'], 'part')
        self.assertEqual(part['heading_segment_ids'], ['v04-u000013'])
        chapter = sections['v04-section-revolution-1830']
        self.assertEqual(chapter['kind'], 'chapter')
        self.assertEqual(chapter['parent_id'], part['id'])
        self.assertEqual(chapter['heading_segment_ids'], ['v04-u000020', 'v04-u000021'])
        appendix = sections['v04-section-part-10-appendix']
        self.assertEqual(appendix['parent_id'], part['id'])
        self.assertEqual(appendix['heading_segment_ids'], ['v04-u001788'])
        for unit in witness('units.json'):
            number = int(unit['id'].split('-u')[1])
            if unit['type'] != 'heading' or not 53 <= number <= 1906 or number in (870, 1787, 1788):
                continue
            section = sections[f'v04-section-document-{number:06}']
            expected_parent = chapter['id'] if number < 1788 else appendix['id']
            if number == 1813:
                expected_parent = 'v04-section-document-001809'
            self.assertEqual(section['parent_id'], expected_parent, unit['id'])
            self.assertEqual(segments[unit['id']]['section_id'], section['id'])
        self.assertEqual(segments['v04-u001812']['section_id'], 'v04-section-document-001809')
        self.assertEqual(segments['v04-u001822']['section_id'], 'v04-section-document-001813')
        speech = next(g for g in doc['groups'] if g['id'] == 'v04-heading-speech-000869')
        self.assertEqual([m['segment_id'] for m in speech['members']], ['v04-u000869', 'v04-u000870'])
        self.assertEqual(segments['v04-u000870']['section_id'], segments['v04-u000869']['section_id'])

    def test_signed_note_frames_do_not_absorb_anonymous_continuations_or_press_columns(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-4-fr-ja.yaml')
        segments = {s['id']: s for s in doc['segments']}
        notes = {n['id']: n for n in doc['notes']}
        self.assertTrue(any(p['id'] == 'person-bacourt' for p in doc['metadata']['contributors']))
        for label in (35, 42, 48, 62, 63, 269, 296, 328, 371, 375, 378):
            n = notes[f'v04-note-{label}']
            for part in n['body']:
                s = segments[part['segment_id']]
                if '(Note de M. de Bacourt.)' in s['source_text'] or s['id'] == 'v04-u002281':
                    self.assertTrue(any(a['voice'] == 'editor' and a.get('contributor_id') == 'person-bacourt'
                                        for a in s.get('attributions', [])), s['id'])
        for sid in ('v04-u001998', 'v04-u002000', 'v04-u002285', 'v04-u002286-c2'):
            self.assertFalse(any(a.get('contributor_id') == 'person-bacourt'
                                 for a in segments[sid].get('attributions', [])), sid)
        for label in (62, 63, 296):
            self.assertEqual(notes[f'v04-note-{label}']['origin'], 'unknown')
        for label in (35, 42, 48, 269, 328, 371, 375, 378):
            self.assertEqual(notes[f'v04-note-{label}']['origin'], 'editor')
        for number in (1856, 1857, 1858):
            s = segments[f'v04-u{number:06}']
            self.assertTrue(any(a.get('name_original') == 'ambassadeur de France'
                                for a in s['attributions']), s['id'])
            self.assertFalse(any(a.get('name_original') == 'Sir R. Gordon'
                                 for a in s['attributions']), s['id'])

    def test_gordon_heading_callouts_stay_with_the_people_they_explain(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-4-fr-ja.yaml')
        s = next(s for s in doc['segments'] if s['id'] == 'v04-u001852')
        self.assertIn('ゴードン[397]からパーマストン卿[398]への', s['translation_ja'])
        for r in doc['references']:
            if r['from']['segment_id'] == s['id'] and r['kind'] == 'note':
                p = r['from']['translation_span']
                self.assertEqual(s['translation_ja'][p['start']:p['end']], p['exact'])

    def test_parallel_press_table_preserves_both_columns_in_note_296(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-4-fr-ja.yaml')
        segments = {s['id']: s for s in doc['segments']}
        table = next((g for g in doc['groups'] if g['id'] == 'v04-table-01'), None)
        self.assertIsNotNone(table)
        rows = witness('table-structures.json')['tables'][0]['rows']
        self.assertEqual(len(table['members']), 12)
        body = next(n['body'] for n in doc['notes'] if n['id'] == 'v04-note-296')
        self.assertEqual([p['segment_id'] for p in body],
                         ['v04-u002281', *[m['segment_id'] for m in table['members']], 'v04-u002288'])
        for row_number, row in enumerate(rows, 1):
            for column, cell in enumerate(row['cells'], 1):
                member = next(m for m in table['members'] if m['row'] == row_number and m['column'] == column)
                segment = segments[member['segment_id']]
                self.assertEqual(segment['kind'], 'table_cell')
                self.assertEqual(segment['source_text'].rstrip(), cell['text'])
                self.assertEqual(segment['source_locations'][0]['xpath'], cell['source_xpath'])
                expected_language = ['en', 'fr'] if row_number == 5 and column == 1 else [cell['language']]
                self.assertEqual(segment['source_languages'], expected_language)
        mixed = segments['v04-u002286']
        self.assertTrue(any(a['side'] == 'source' and a['kind'] == 'language' and a['language'] == 'fr'
                            and a['span']['exact'] == "l'emploi d'officiers français dans l'armée belge"
                            for a in mixed['annotations']))

    def test_split_title_fragments_have_one_heading_and_reachable_original_ids(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-4-fr-ja.yaml')
        segments = {segment['id']: segment for segment in doc['segments']}
        aliases = {alias['old_id']: alias for alias in doc['aliases']}
        original = {unit['id']: unit for unit in witness('units.json')}
        for numbers in [(1, 2, 3), (4, 5, 6, 7), (16, 17, 18)]:
            ids = [f'v04-u{number:06}' for number in numbers]
            heading = segments[ids[0]]
            self.assertEqual(heading['source_text'], ' '.join(original[sid]['text'] for sid in ids))
            self.assertEqual([alignment['original_unit_id'] for alignment in heading['source_alignment']], ids)
            for sid in ids[1:]:
                self.assertNotIn(sid, segments)
                self.assertEqual(aliases[sid]['new_id'], ids[0])


if __name__ == '__main__':
    unittest.main()
