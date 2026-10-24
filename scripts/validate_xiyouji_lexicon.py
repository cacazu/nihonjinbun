"""Validate vocabulary and sources in the work-wide Xiyouji lexicon."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker
from translation_yaml import ROOT, load_document

SCHEMA = json.loads((ROOT / 'schemas/xiyouji-lexicon.schema.json').read_text(encoding='utf-8'))
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def validate_lexicon(data):
    errors = [f"{'/'.join(map(str, e.absolute_path))}: {e.message}"
              for e in VALIDATOR.iter_errors(data)]
    if errors:
        return errors

    def unique(items, label):
        ids = [item['id'] for item in items]
        if len(set(ids)) != len(ids):
            errors.append(f'{label}: duplicate ID')

    unique(data['sources'], 'sources')
    unique(data['entries'], 'entries')
    unique([f for e in data['entries'] for f in e['forms']], 'forms')
    sources = {s['id'] for s in data['sources']}
    for source in data['sources']:
        try:
            url = urlsplit(source['url'])
            valid = url.scheme in ('http', 'https') and url.hostname and not (url.username or url.password)
        except ValueError:
            valid = False
        if not valid:
            errors.append(f"{source['id']}: invalid public HTTP URL")

    def evidence(value, label):
        for source_id in value['source_ids']:
            if source_id not in sources:
                errors.append(f'{label}: unknown source ID {source_id}')

    for entry in data['entries']:
        evidence(entry['definition_evidence'], entry['id'])
        preferred = [f for f in entry['forms'] if f['relation'] == 'preferred']
        if len(preferred) != 1 or preferred[0]['text'] != entry['headword']:
            errors.append(f"{entry['id']}: exactly one preferred form must match headword")
        for form in entry['forms']:
            label = form['id']
            evidence(form['reading'], label)
            if not form['reading']['kana'].strip():
                errors.append(f'{label}: kana cannot be blank')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', nargs='?', type=Path, default=ROOT / 'lexicons/xiyouji.yaml')
    args = parser.parse_args()
    try:
        errors = validate_lexicon(load_document(args.path))
    except (ValueError, OSError) as exc:
        errors = [str(exc)]
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f'{args.path}: valid')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
