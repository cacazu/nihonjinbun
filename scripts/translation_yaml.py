"""Translation YAML 2.0 loading, schema and semantic validation."""
import argparse
import copy
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from xml.etree import ElementTree

import rfc8785
import yaml
from jsonschema import Draft202012Validator
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OPTIONAL_ARRAYS = ('notes', 'references', 'groups', 'assets', 'figures', 'aliases', 'terminology')


class JsonLoader(yaml.CSafeLoader):
    """Use JSON-compatible implicit scalars instead of YAML 1.1 booleans/dates."""
    yaml_implicit_resolvers = copy.deepcopy(yaml.CSafeLoader.yaml_implicit_resolvers)


for initial, rules in JsonLoader.yaml_implicit_resolvers.items():
    JsonLoader.yaml_implicit_resolvers[initial] = [
        (tag, pattern) for tag, pattern in rules
        if tag not in ('tag:yaml.org,2002:bool', 'tag:yaml.org,2002:timestamp',
                       'tag:yaml.org,2002:int', 'tag:yaml.org,2002:float')]
JsonLoader.add_implicit_resolver('tag:yaml.org,2002:bool', re.compile(r'^(?:true|false)$'), list('tf'))
JsonLoader.add_implicit_resolver('tag:yaml.org,2002:int', re.compile(r'^-?(?:0|[1-9][0-9]*)$'), list('-0123456789'))
JsonLoader.add_implicit_resolver('tag:yaml.org,2002:float',
                               re.compile(r'^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+(?:[eE][+-]?[0-9]+)?|[eE][+-]?[0-9]+)$'),
                               list('-0123456789'))


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key == '<<':
            raise ValueError('Mapping keys must be strings; merge keys are forbidden')
        if key in result:
            raise ValueError(f'Duplicate mapping key: {key}')
        result[key] = loader.construct_object(value_node)
    return result


JsonLoader.add_constructor('tag:yaml.org,2002:map', _mapping)


def load_document(path):
    raw = Path(path).read_bytes()
    if b'\r' in raw or raw.startswith(b'\xef\xbb\xbf'):
        raise ValueError('Use UTF-8 without BOM and LF line endings')
    text = raw.decode('utf-8')
    try:
        for token in yaml.scan(text, Loader=yaml.CSafeLoader):
            if isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken, yaml.tokens.TagToken)):
                raise ValueError('Anchors, aliases and explicit tags are forbidden')
        data = yaml.load(text, Loader=JsonLoader)
        json.dumps(data, allow_nan=False)
        return data
    except (yaml.YAMLError, TypeError, UnicodeError) as exc:
        raise ValueError(str(exc)) from exc


def content_hash(data):
    payload = {k: v for k, v in data.items() if k not in ('workflow', 'provenance')}
    for key in OPTIONAL_ARRAYS:
        payload.setdefault(key, [])
    return hashlib.sha256(rfc8785.dumps(payload)).hexdigest()


SCHEMA = json.loads((ROOT / 'schemas/translation-2.0.schema.json').read_text(encoding='utf-8'))
Draft202012Validator.check_schema(SCHEMA)
SCHEMA_VALIDATOR = Draft202012Validator(SCHEMA)


def image_dimensions(path, media_type):
    if media_type == 'image/svg+xml':
        element = ElementTree.parse(path).getroot()
        if element.tag.split('}')[-1] != 'svg':
            raise ValueError('SVG root required')
        view_box = element.get('viewBox', '').split()
        width = element.get('width', view_box[2] if len(view_box) == 4 else '')
        height = element.get('height', view_box[3] if len(view_box) == 4 else '')
        return tuple(int(float(re.sub(r'px$', '', value))) for value in (width, height))
    with Image.open(path) as im:
        expected = {'image/png': 'PNG', 'image/jpeg': 'JPEG', 'image/gif': 'GIF', 'image/webp': 'WEBP'}[media_type]
        if im.format != expected:
            raise ValueError(f'Expected {expected}, found {im.format}')
        size = im.size
        im.verify()
        return size


def validate_document(data, repo_root=None):
    errors = [f"{'/'.join(map(str, e.absolute_path))}: {e.message}"
              for e in SCHEMA_VALIDATOR.iter_errors(data)]
    if errors:
        return errors

    def fail(message):
        errors.append(message)

    def scalar_contract(value, context=''):
        if isinstance(value, dict):
            for key, child in value.items():
                where = context + '/' + key
                if key == 'provenance': continue
                if key in ('message_ja', 'description_ja', 'evidence_ja', 'reviewed_by') and isinstance(child, str) and not child.strip():
                    fail(f'{where}: explanation cannot be blank')
                if key in ('url', 'license_url', 'evidence_url') and isinstance(child, str):
                    try:
                        parsed = urlsplit(child)
                        invalid = parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password
                    except ValueError:
                        invalid = True
                    if invalid:
                        fail(f'{where}: invalid public HTTP URL')
                if key in ('source_language', 'language') and isinstance(child, str):
                    check_language(child, where)
                if key in ('languages', 'source_languages', 'original_languages'):
                    for tag in child: check_language(tag, where)
                scalar_contract(child, where)
        elif isinstance(value, list):
            for i, child in enumerate(value): scalar_contract(child, context + '/' + str(i))

    def check_language(tag, context):
        # RFC 5646 langtag grammar, including extensions/private use; common grandfathered forms.
        grammar = (r'(?:[a-z]{2,3}(?:-[a-z]{3}){0,3}|[a-z]{4}|[a-z]{5,8})'
                   r'(?:-[a-z]{4})?(?:-(?:[a-z]{2}|[0-9]{3}))?'
                   r'(?:-(?:[a-z0-9]{5,8}|[0-9][a-z0-9]{3}))*'
                   r'(?:-[0-9a-wy-z](?:-[a-z0-9]{2,8})+)*'
                   r'(?:-x(?:-[a-z0-9]{1,8})+)?')
        grandfathered = {'en-gb-oed', 'i-ami', 'i-bnn', 'i-default', 'i-enochian', 'i-hak',
                         'i-klingon', 'i-lux', 'i-mingo', 'i-navajo', 'i-pwn', 'i-tao', 'i-tay',
                         'i-tsu', 'sgn-be-fr', 'sgn-be-nl', 'sgn-ch-de', 'art-lojban', 'cel-gaulish',
                         'no-bok', 'no-nyn', 'zh-guoyu', 'zh-hakka', 'zh-min', 'zh-min-nan', 'zh-xiang'}
        if tag.lower() not in grandfathered and not re.fullmatch(grammar + r'|x(?:-[a-z0-9]{1,8})+', tag, re.I):
            fail(f'{context}: invalid language tag {tag}')

    scalar_contract(data)

    collections = {k: data.get(k, []) for k in ('sources', 'sections', 'segments', 'notes',
                                               'references', 'groups', 'assets', 'figures', 'terminology')}
    collections['contributors'] = data['metadata']['contributors']
    indexes = {}
    for kind, items in collections.items():
        indexes[kind] = {x['id']: x for x in items}
        if len(indexes[kind]) != len(items):
            fail(f'{kind}: duplicate ID')

    def exists(collection, ident, context):
        if ident not in indexes[collection]:
            fail(f'{context}: unknown {collection} ID {ident}')
            return False
        return True

    def span(value, text, context):
        if not isinstance(text, str) or not 0 <= value['start'] < value['end'] <= len(text):
            fail(f'{context}: invalid code-point span')
        elif text[value['start']:value['end']] != value['exact']:
            fail(f'{context}: span exact text differs')

    def spans(value, segment, context):
        for key, field in (('source_span', 'source_text'), ('translation_span', 'translation_ja')):
            if key in value:
                span(value[key], segment[field], context + '/' + key)

    def location(value, context):
        exists('sources', value['source_id'], context)
        for start, end in (('pdf_page', 'pdf_page_end'), ('line_start', 'line_end')):
            if end in value and (start not in value or value[end] < value[start]):
                fail(f'{context}: invalid {start} range')
        needed = {'page': ('printed_page', 'pdf_page', 'url'),
                  'block': ('anchor', 'xpath'), 'line': ('line_start',), 'region': ('crop',)}
        if value['precision'] in needed and not any(k in value for k in needed[value['precision']]):
            fail(f'{context}: missing locator for {value["precision"]}')
        if 'asset_id' in value:
            exists('assets', value['asset_id'], context)
        if 'crop' in value:
            crop = value['crop']
            if not any(k in value for k in ('asset_id', 'url')):
                fail(f'{context}: crop needs original image')
            if crop['unit'] == 'fraction':
                limits = (1, 1)
            else:
                asset = indexes['assets'].get(value.get('asset_id'), {})
                limits = (asset.get('width'), asset.get('height'))
                if None in limits:
                    fail(f'{context}: pixel crop needs verified image dimensions')
            if None not in limits and (crop['x'] + crop['width'] > limits[0]
                                       or crop['y'] + crop['height'] > limits[1]):
                fail(f'{context}: crop outside image')

    def locations(values, context):
        for value in values:
            location(value, context)

    def rights(value, context):
        if value['status'] == 'licensed' and not any(value.get(k) for k in ('license_id', 'license_url')):
            fail(f'{context}: licensed rights need a license')
        if value['status'] == 'public_domain' and value.get('license_id', '').startswith('CC-BY'):
            fail(f'{context}: public-domain status conflicts with license')

    def cycles(collection, parent_key, get_parent=None):
        completed = set()
        for ident in indexes[collection]:
            active = set()
            current = ident
            while current is not None and current not in completed:
                if current in active:
                    fail(f'{collection}: cycle at {current}')
                    break
                active.add(current)
                item = indexes[collection].get(current)
                if item is None:
                    fail(f'{collection}: missing parent {current}')
                    break
                current = get_parent(item) if get_parent else item.get(parent_key)
            completed.update(active)

    rights(data['metadata']['translation_rights'], 'translation_rights')
    if 'cover_asset_id' in data['metadata']:
        exists('assets', data['metadata']['cover_asset_id'], 'cover')
    for source in data['sources']:
        rights(source['work_rights'], source['id'])
        rights(source['transcription_rights'], source['id'])
        for ident in source.get('contributor_ids', []):
            exists('contributors', ident, source['id'])
        for record in source.get('page_inventory', []):
            location(record['location'], source['id'])
            for field, collection in (('segment_ids', 'segments'), ('figure_ids', 'figures')):
                for ident in record.get(field, []): exists(collection, ident, source['id'])
    cycles('sources', 'derived_from_source_id')

    excluded = set()
    included = set()
    for side in ('included', 'excluded', 'known_gaps'):
        for item in data['scope'][side]:
            if 'source_id' in item: exists('sources', item['source_id'], side)
            for field, collection in (('section_ids', 'sections'), ('segment_ids', 'segments'),
                                      ('reference_ids', 'references'), ('figure_ids', 'figures')):
                for ident in item.get(field, []): exists(collection, ident, side)
            target = excluded if side == 'excluded' else included if side == 'included' else None
            if target is not None:
                target.update(item.get('segment_ids', []))
                target.update(s['id'] for s in data['segments']
                              if s['section_id'] in item.get('section_ids', []))
            for partial in item.get('source_ranges', []):
                if exists('segments', partial['segment_id'], side):
                    span(partial['span'], indexes['segments'][partial['segment_id']]['source_text'], side)
    if excluded & included: fail('scope: included and excluded segments overlap')

    seen_sections = set()
    for section in data['sections']:
        if section['parent_id'] is not None and section['parent_id'] not in seen_sections:
            fail(f'{section["id"]}: parent must precede child')
        seen_sections.add(section['id'])
        if section.get('origin') == 'editorial' and not section.get('label_ja'):
            fail(f'{section["id"]}: editorial section needs a label')
        for ident in section['heading_segment_ids']:
            if exists('segments', ident, section['id']) and indexes['segments'][ident]['kind'] != 'heading':
                fail(f'{section["id"]}: heading reference is not a heading')
        locations(section.get('source_locations', []), section['id'])
    cycles('sections', 'parent_id')

    ready = data['workflow']['stage'] == 'ready'
    for segment in data['segments']:
        ident = segment['id']
        exists('sections', segment['section_id'], ident)
        locations(segment['source_locations'], ident)
        if segment['translation_status'] == 'pending':
            if segment['translation_ja'] is not None: fail(f'{ident}: pending translation must be null')
        elif segment['kind'] != 'separator' and not segment['translation_ja']:
            fail(f'{ident}: translated text cannot be empty')
        if segment['origin'] == 'translator':
            if segment['source_text'] is not None: fail(f'{ident}: translator prose cannot have source text')
        else:
            if not segment['source_languages'] or not segment['source_locations']:
                fail(f'{ident}: source prose needs language and location')
            if segment['source_text'] is None and not any(
                    x['kind'] in ('unreadable', 'source_untranscribed', 'missing_source')
                    for x in segment.get('issues', [])):
                fail(f'{ident}: absent source must be explained')
        required = segment.get('translation_required', True)
        if not required and (ident not in excluded or segment['translation_ja'] is not None
                             or segment['translation_status'] != 'pending'):
            fail(f'{ident}: excluded translation needs explicit scope and null pending text')
        if segment['translation_status'] == 'partial' and not segment.get('issues'):
            fail(f'{ident}: partial translation needs issue')
        if ready and required and (segment['translation_status'] in ('pending', 'draft')
                                    or segment['kind'] == 'unclassified'):
            fail(f'{ident}: unfinished translation cannot be ready')
        for value in segment.get('source_alignment', []):
            exists('sources', value['source_id'], ident)
            spans(value, segment, ident)
        for value in segment.get('source_variants', []):
            locations(value.get('source_locations', []), ident)
        for value in segment.get('attributions', []):
            spans(value, segment, ident)
            if 'contributor_id' in value: exists('contributors', value['contributor_id'], ident)
            if value['voice'] == 'unknown' and not value.get('evidence_ja'):
                fail(f'{ident}: unknown voice needs explanation')
        for side in ('source_span', 'translation_span'):
            ranges = [a[side] for a in segment.get('attributions', []) if side in a]
            for i, a in enumerate(ranges):
                for b in ranges[i + 1:]:
                    if a['start'] < b['start'] < a['end'] < b['end'] or b['start'] < a['start'] < b['end'] < a['end']:
                        fail(f'{ident}: attribution ranges cross')
        for value in segment.get('issues', []): spans(value, segment, ident)
        for value in segment.get('annotations', []):
            span(value['span'], segment['source_text' if value['side'] == 'source' else 'translation_ja'], ident)
            extra = {'ruby': 'reading', 'indent': 'columns', 'language': 'language'}.get(value['kind'])
            if extra and extra not in value: fail(f'{ident}: annotation needs {extra}')
            if any(k in value for k in ('reading', 'columns', 'language') if k != extra):
                fail(f'{ident}: annotation has incompatible detail')

    for note in data.get('notes', []):
        if note['origin'] == 'unknown' and not note.get('description_ja'):
            fail(f'{note["id"]}: unknown note origin needs explanation')
        if 'contributor_id' in note: exists('contributors', note['contributor_id'], note['id'])
        locations(note.get('source_locations', []), note['id'])
        for part in note['body']:
            if exists('segments', part['segment_id'], note['id']):
                spans(part, indexes['segments'][part['segment_id']], note['id'])

    target_collections = {'note': 'notes', 'segment': 'segments', 'figure': 'figures'}
    for reference in data.get('references', []):
        ident, start, target = reference['id'], reference['from'], reference['to']
        if exists('segments', start['segment_id'], ident): spans(start, indexes['segments'][start['segment_id']], ident)
        locations(reference.get('evidence', []), ident)
        if reference['status'] == 'unresolved':
            if target is not None or not reference.get('description_ja'): fail(f'{ident}: unresolved reference needs null target and explanation')
        elif target is None:
            fail(f'{ident}: verified reference needs target')
        if target:
            if target['type'] == 'source_location': location(target['location'], ident)
            else: exists(target_collections[target['type']], target['id'], ident)
            if reference['kind'] in ('note', 'figure') and target['type'] != reference['kind']:
                fail(f'{ident}: reference target type mismatch')

    positions = {s['id']: i for i, s in enumerate(data['segments'])}
    for group in data.get('groups', []):
        members = [x['segment_id'] for x in group['members']]
        for member in group['members']:
            if exists('segments', member['segment_id'], group['id']):
                spans(member, indexes['segments'][member['segment_id']], group['id'])
        order = [positions.get(ident, -1) for ident in members]
        if order != sorted(set(order)): fail(f'{group["id"]}: group members must be unique and in reading order')
        parent = indexes['groups'].get(group.get('parent_id'))
        if parent and not set(members) <= {x['segment_id'] for x in parent['members']}:
            fail(f'{group["id"]}: child group not contained in parent')
        if group['kind'] == 'table':
            cells = [(m.get('row'), m.get('column')) for m in group['members']]
            if any(None in cell for cell in cells) or len(set(cells)) != len(cells): fail(f'{group["id"]}: invalid table grid')
            if any(indexes['segments'].get(i, {}).get('kind') != 'table_cell' for i in members): fail(f'{group["id"]}: table requires cells')
        for variant in group.get('source_variants', []): locations(variant.get('source_locations', []), group['id'])
    cycles('groups', 'parent_id')
    groups = data.get('groups', [])
    for i, a in enumerate(groups):
        ids_a = {m['segment_id'] for m in a['members']}
        for b in groups[i + 1:]:
            ids_b = {m['segment_id'] for m in b['members']}
            if not ids_a & ids_b: continue
            ancestors = set()
            for child in (a, b):
                parent = child.get('parent_id')
                visited = set()
                while parent and parent not in visited:
                    visited.add(parent); ancestors.add((child['id'], parent))
                    parent = indexes['groups'].get(parent, {}).get('parent_id')
            if (a['id'], b['id']) not in ancestors and (b['id'], a['id']) not in ancestors:
                fail(f'{a["id"]}/{b["id"]}: unrelated groups share segments')

    for asset in data.get('assets', []):
        ident = asset['id']
        path = PurePosixPath(asset['path'])
        if (not asset['path'].startswith(f'assets/{data["work_id"]}/') or '..' in path.parts
                or '\\' in asset['path'] or ':' in asset['path'] or path.is_absolute()):
            fail(f'{ident}: unsafe asset path')
            continue
        rights(asset['rights'], ident)
        locations(asset['source_locations'], ident)
        for step in asset.get('processing', []):
            if 'crop' in step:
                if step['kind'] != 'crop': fail(f'{ident}: crop coordinates require crop processing')
                crop = step['crop']
                bounds = (1, 1) if crop['unit'] == 'fraction' else (
                    step.get('coordinate_image_width'), step.get('coordinate_image_height'))
                for axis, size, limit in (('x', 'width', bounds[0]), ('y', 'height', bounds[1])):
                    if limit is not None and crop[axis] + crop[size] > limit:
                        fail(f'{ident}: crop recipe outside coordinate image')
        if asset['status'] == 'available':
            if any(k not in asset for k in ('sha256', 'bytes', 'width', 'height')):
                fail(f'{ident}: available asset needs hash, byte count and dimensions')
            elif repo_root is not None:
                actual = Path(repo_root) / path
                try:
                    raw = actual.read_bytes()
                    if hashlib.sha256(raw).hexdigest() != asset['sha256'] or len(raw) != asset['bytes']:
                        fail(f'{ident}: image bytes/hash differ')
                    if image_dimensions(actual, asset['media_type']) != (asset['width'], asset['height']):
                        fail(f'{ident}: image dimensions differ')
                except (OSError, ValueError, ElementTree.ParseError) as exc:
                    fail(f'{ident}: unreadable image: {exc}')
    cycles('assets', 'derived_from_asset_id')
    for figure in data.get('figures', []):
        ident, placement = figure['id'], figure['placement']
        exists('assets', figure['asset_id'], ident)
        exists(target_collections.get(placement['anchor_type'], 'sections'), placement['anchor_id'], ident)
        allowed = ('start', 'end') if placement['anchor_type'] == 'section' else ('before', 'after')
        if placement['position'] not in allowed: fail(f'{ident}: invalid placement position')
        for field in ('caption_segment_ids', 'text_segment_ids'):
            for segment_id in figure.get(field, []): exists('segments', segment_id, ident)
        if figure.get('caption_segment_ids') and figure['caption_ja'] is not None:
            fail(f'{ident}: caption text duplicated')
        if ready and figure['required'] and (indexes['assets'].get(figure['asset_id'], {}).get('status') != 'available' or not figure['alt_ja']):
            fail(f'{ident}: required figure is incomplete')
    cycles('figures', None, lambda f: f['placement']['anchor_id'] if f['placement']['anchor_type'] == 'figure' else None)

    seen_aliases = set()
    for alias in data.get('aliases', []):
        collection = target_collections.get(alias['type'], 'sections')
        if alias['old_id'] in indexes[collection] or (alias['type'], alias['old_id']) in seen_aliases:
            fail(f'{alias["old_id"]}: alias collides with live ID or another alias')
        seen_aliases.add((alias['type'], alias['old_id']))
        if exists(collection, alias['new_id'], alias['old_id']) and alias['type'] == 'segment':
            spans(alias, indexes[collection][alias['new_id']], alias['old_id'])

    review = data['workflow'].get('full_review', {})
    if review.get('status') == 'complete':
        if any(k not in review for k in ('completed_at', 'reviewed_by', 'content_sha256')):
            fail('full_review: completion needs time, reviewer and content hash')
        elif review['content_sha256'] != content_hash(data):
            fail('full_review: stale content hash')
        if 'completed_at' in review:
            try: datetime.fromisoformat(review['completed_at'].replace('Z', '+00:00'))
            except ValueError: fail('full_review: invalid UTC date/time')
    if ready and review.get('status') != 'complete': fail('ready: full review is incomplete')
    if ready:
        gap_segments = {i for g in data['scope']['known_gaps'] for i in g.get('segment_ids', [])}
        gap_references = {i for g in data['scope']['known_gaps'] for i in g.get('reference_ids', [])}
        for s in data['segments']:
            if (s['translation_status'] == 'partial' or (s['origin'] == 'source' and s['source_text'] is None)) and s['id'] not in gap_segments:
                fail(f'{s["id"]}: ready qualification must appear in scoped known gaps')
        for r in data.get('references', []):
            if r['status'] == 'unresolved' and r['id'] not in gap_references:
                fail(f'{r["id"]}: unresolved reference must appear in scoped known gaps')
    return errors


def validate_catalog(repo_root):
    root = Path(repo_root)
    catalog = load_document(root / 'catalog.yaml')
    errors, listed, work_ids = [], set(), set()
    for item in catalog.get('works', []):
        path = item.get('file', '')
        if not re.fullmatch(r'translations/[A-Za-z0-9_/-]+\.yaml', path):
            errors.append(f'catalog: invalid path {path}'); continue
        if path in listed or item.get('work_id') in work_ids: errors.append(f'catalog: duplicate work {path}')
        listed.add(path); work_ids.add(item.get('work_id'))
        try:
            raw = (root / path).read_bytes()
            data = load_document(root / path)
            if item.get('sha256') != hashlib.sha256(raw).hexdigest(): errors.append(f'{path}: catalog hash differs')
            if item.get('work_id') != data['work_id'] or item.get('title') != data['metadata']['title_ja']:
                errors.append(f'{path}: catalog metadata differs')
            errors.extend(f'{path}: {message}' for message in validate_document(data, root))
        except (ValueError, OSError, KeyError) as exc:
            errors.append(f'{path}: {exc}')
    actual = {p.relative_to(root).as_posix() for p in (root / 'translations').rglob('*.yaml')}
    if actual != listed: errors.append('catalog: work file coverage differs')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='*', type=Path)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--hash', action='store_true', help='Print full-review content digest')
    args = parser.parse_args()
    errors = []
    if args.files:
        for path in args.files:
            try:
                data = load_document(path)
                errors.extend(f'{path}: {e}' for e in validate_document(data, args.root))
                if args.hash: print(f'{path}: {content_hash(data)}')
            except (ValueError, OSError) as exc: errors.append(f'{path}: {exc}')
    else:
        errors = validate_catalog(args.root)
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'Valid: {len(args.files) if args.files else len(load_document(args.root / "catalog.yaml")["works"])} work(s)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
