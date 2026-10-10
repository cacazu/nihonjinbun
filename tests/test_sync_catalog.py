import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sync_catalog import sync_catalog
from translation_yaml import load_document


class CatalogTests(unittest.TestCase):
    def test_discovers_new_book_and_preserves_global_and_existing_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'translations/author').mkdir(parents=True)
            (root / 'catalog.yaml').write_bytes(('schema_version: "2.0"\nrights: "出典別の利用条件"\nworks:\n'
                '  - work_id: old\n    file: translations/author/old.yaml\n    title: 旧題\n'
                '    coverage_note: "部分訳"\n').encode('utf-8'))
            for ident, title in [('old', '改題'), ('new', '新刊')]:
                (root / f'translations/author/{ident}.yaml').write_bytes(yaml.safe_dump(
                    {'schema_version': '2.0', 'work_id': ident, 'metadata': {'title_ja': title}},
                    allow_unicode=True).encode('utf-8'))
            sync_catalog(root)
            catalog = load_document(root / 'catalog.yaml')
            self.assertEqual('出典別の利用条件', catalog['rights'])
            self.assertEqual(['old', 'new'], [w['work_id'] for w in catalog['works']])
            self.assertEqual('部分訳', catalog['works'][0]['coverage_note'])
            self.assertEqual('改題', catalog['works'][0]['title'])
            for item in catalog['works']:
                self.assertEqual(hashlib.sha256((root / item['file']).read_bytes()).hexdigest(), item['sha256'])
            raw = (root / 'catalog.yaml').read_bytes()
            sync_catalog(root)
            self.assertEqual(raw, (root / 'catalog.yaml').read_bytes())


if __name__ == '__main__': unittest.main()
