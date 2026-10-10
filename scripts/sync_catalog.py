"""Derive catalog identity, title and file digest from translation YAML 2.0."""
import argparse
import hashlib
from pathlib import Path

import yaml

from translation_yaml import ROOT, load_document


class CatalogDumper(yaml.CSafeDumper):
    def ignore_aliases(self, data): return True


def _string(dumper, value):
    return dumper.represent_scalar('tag:yaml.org,2002:str', value, style='|' if '\n' in value else '"')


CatalogDumper.add_representer(str, _string)


def sync_catalog(root):
    root = Path(root)
    path = root / 'catalog.yaml'
    catalog = load_document(path) if path.exists() else {'schema_version': '2.0', 'works': []}
    old = {w['file']: w for w in catalog.get('works', [])}
    files = {p.relative_to(root).as_posix(): p for p in (root / 'translations').rglob('*.yaml')}
    order = [name for name in old if name in files] + sorted(set(files) - set(old))
    works, ids = [], set()
    for name in order:
        data = load_document(files[name])
        if data.get('schema_version') != '2.0': raise ValueError(f'{name}: translation YAML 2.0 required')
        if data['work_id'] in ids: raise ValueError(f'Duplicate work ID: {data["work_id"]}')
        ids.add(data['work_id'])
        works.append({**old.get(name, {}), 'work_id': data['work_id'], 'file': name,
                      'title': data['metadata']['title_ja'],
                      'sha256': hashlib.sha256(files[name].read_bytes()).hexdigest()})
    catalog.update(schema_version='2.0', works=works)
    raw = yaml.dump(catalog, Dumper=CatalogDumper, allow_unicode=True, sort_keys=False,
                    width=100000).encode('utf-8')
    if not path.exists() or path.read_bytes() != raw: path.write_bytes(raw)
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    print(f'Catalog: {len(sync_catalog(args.root)["works"])} work(s)')


if __name__ == '__main__': main()
