#!/usr/bin/env python3
"""Build the explicitly published reading library from canonical YAML 2.0."""
import argparse
import hashlib
import html
import io
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image

from translation_yaml import ROOT, load_document, validate_document

PUBLISHED_CHAPTER_COUNT = 100
CHAPTERS = tuple(f"xiyouji-chapter-{n:03d}-zh-ja.yaml" for n in range(1, PUBLISHED_CHAPTER_COUNT + 1))
TANAKA_WORKS = ("shinto-taii", "kodo-no-shimei-sekai-no-shorai", "kokoku-dento-no-seishin", "nihon-seishin-kokutai", "shinto-shi-koyo", "nihon-shoki-gaisetsu", "shinto-hongi", "kokumin-dotoku-yoryo-kogi", "shinto-koen", "jinja-hongi")
NUMERALS = (
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
    "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
    "二十一", "二十二", "二十三", "二十四", "二十五", "二十六", "二十七", "二十八", "二十九", "三十",
    "三十一", "三十二", "三十三", "三十四", "三十五", "三十六", "三十七", "三十八", "三十九", "四十",
    "四十一", "四十二", "四十三", "四十四", "四十五", "四十六", "四十七", "四十八", "四十九", "五十",
    "五十一", "五十二", "五十三", "五十四", "五十五", "五十六", "五十七", "五十八", "五十九", "六十",
    "六十一", "六十二", "六十三", "六十四", "六十五", "六十六", "六十七", "六十八", "六十九", "七十",
    "七十一", "七十二", "七十三", "七十四", "七十五", "七十六", "七十七", "七十八", "七十九", "八十",
    "八十一", "八十二", "八十三", "八十四", "八十五", "八十六", "八十七", "八十八", "八十九", "九十",
    "九十一", "九十二", "九十三", "九十四", "九十五", "九十六", "九十七", "九十八", "九十九", "百",
)
DISCLAIMER = "日本語訳：ChatGPT（AIによる新訳）。専門家による独立校訂は未実施。"


def esc(value):
    return html.escape(str(value), quote=True)


def external_link(url, label):
    """Only public http(s) links are allowed, even when called outside validation."""
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme in ("https", "http") and parsed.hostname and not parsed.username and not parsed.password
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(f"Unsupported source URL: {url!r}")
    return f'<a href="{esc(url)}" rel="noreferrer">{esc(label)}</a>'


def page_shell(title, content, stylesheet="../assets/reading.css", *, allow_images=False):
    image_policy = " img-src 'self';" if allow_images else ""
    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self';{image_policy} base-uri 'none'; form-action 'none'; connect-src 'none'">
<title>{esc(title)}</title>
<link rel="stylesheet" href="{esc(stylesheet)}">
</head>
<body class="chapter-page">
<main id="main">{content}</main>
</body>
</html>
'''


def chapter_navigation(number):
    links = []
    if number > 1:
        links.append(f'<a rel="prev" href="chapter-{number-1:03d}.html">前の話</a>')
    if number < len(CHAPTERS):
        links.append(f'<a rel="next" href="chapter-{number+1:03d}.html">次の話</a>')
    links.append('<a href="index.html">目次に戻る</a>')
    return f'<nav class="chapter-nav" aria-label="各回の移動">{"".join(links)}</nav>'


def render_text(text, refs, field, note_numbers):
    """Keep all Unicode code points and line breaks; insert links at verified spans."""
    lang = "ja" if field == "translation_span" else "zh"
    spans = sorted((ref["from"][field]["start"], ref["from"][field]["end"], ref)
                   for ref in refs if field in ref["from"])
    result, offset = [], 0
    for start, end, ref in spans:
        span = ref["from"][field]
        if start < offset or not 0 <= start < end <= len(text) or text[start:end] != span["exact"]:
            raise ValueError(f'Overlapping or invalid text span: {ref["id"]}')
        target = ref["to"]["id"]
        number = note_numbers[target]
        result.append(esc(text[offset:start]))
        result.append(f'<a class="note-ref" id="{esc(ref["id"])}-{lang}" href="#{esc(target)}" data-note="{number}" title="訳注 {number}" aria-describedby="note-label-{esc(target)}">{esc(text[start:end])}</a>')
        offset = end
    result.append(esc(text[offset:]))
    return "".join(result)


def render_segment(segment, refs, note_numbers, occurrences=()):
    tag = "h1" if segment["kind"] == "heading" else "div"
    japanese = render_text(segment["translation_ja"], refs, "translation_span", note_numbers)
    glosses = "".join(f'<div>{esc(item["translation_span"]["exact"])}：{esc(item["gloss_ja"])}</div>'
                      for item in sorted(occurrences, key=lambda item: item["translation_span"]["start"])
                      if "gloss_ja" in item)
    glosses = f'<div class="paragraph-glosses" lang="ja">{glosses}</div>' if glosses else ""
    return (f'<section class="segment {esc(segment["kind"])}" id="{esc(segment["id"])}">'
            f'<{tag} class="story-text translation" lang="ja">{japanese}</{tag}>{glosses}</section>')


def render_notes(data, refs_by_note, note_numbers, *, origin_labels=False, segment_note_links=False):
    notes = data.get("notes", [])
    segments = {segment["id"]: segment for segment in data["segments"]}
    sources = {source["id"]: source for source in data["sources"]}
    items = []
    for note in notes:
        nid = note["id"]
        inline = note.get("form") == "inline" and all("translation_span" in item for item in note["body"])
        if inline:
            body = "".join(f'<div id="{esc(nid)}-body-{i}" class="story-text note-body">{esc(segments[item["segment_id"]]["translation_ja"][item["translation_span"]["start"]:item["translation_span"]["end"]])}</div>' for i, item in enumerate(note["body"], 1))
        else:
            body = "".join(f'<div id="{esc(item["segment_id"])}" class="story-text note-body">{esc(segments[item["segment_id"]]["translation_ja"])}</div>' for item in note["body"])
        backlinks = []
        note_label = {"author": "原注", "unknown": "書込み（筆者不明）", "translator": "訳注"}.get(note.get("origin"), "注") if origin_labels else "訳注"
        description = f'<p>{esc(note["description_ja"])}</p>' if origin_labels and note.get("description_ja") else ""
        if origin_labels and note.get("origin") != "translator":
            if inline:
                if note.get("origin") == "unknown":
                    note_label = "原割注（筆者未詳）"
                backlinks.extend(f'<a href="#{esc(item["segment_id"])}">原注を含む本文へ戻る ↑</a>' for item in note["body"])
            else:
                backlinks.append(f'<a href="#source-note-{esc(nid)}">原注の位置へ戻る ↑</a>')
        for i, ref in enumerate(refs_by_note[nid], 1):
            for field, lang, label in (("translation_span", "ja", "本文"),):
                if field in ref["from"]:
                    backlinks.append(f'<a href="#{esc(ref["id"])}-{lang}">{label}の該当箇所 {i} へ戻る ↑</a>')
            if segment_note_links and "translation_span" not in ref["from"]:
                backlinks.append(f'<a href="#{esc(ref["id"])}-ja">本文の該当段落 {i} へ戻る ↑</a>')
        locations = "".join(f'<li>{external_link(loc["url"], sources[loc["source_id"]]["title"])}</li>' for loc in note.get("source_locations", []) if loc.get("url"))
        sources_html = f'<ul class="note-sources">{locations}</ul>' if locations else ""
        items.append(f'<li class="note-card" id="{esc(nid)}"><h3 id="note-label-{esc(nid)}">{note_label} {note_numbers[nid]:02d}</h3>{description}{body}{sources_html}<div class="backlinks">{"".join(backlinks)}</div></li>')
    return f'<ol class="notes-list">{"".join(items)}</ol>' if items else ""


def render_annotations(data, refs_by_note, note_numbers, *, include_ocr=True, include_scoped_issues=False, segment_note_links=False, resolve_attribution_names=False, include_source_rights_notes=False):
    contributors = {c["id"]: c["name_ja"] for c in data["metadata"]["contributors"]}
    def attribution_name(item):
        if item.get("name_ja"):
            return item["name_ja"]
        if resolve_attribution_names:
            return contributors.get(item.get("contributor_id")) or {
                "author": "著者", "translator": "訳者", "editor": "編集者",
                "quoted_person": "引用者（氏名未記載）", "unknown": "話者不明",
            }[item["voice"]]
        return "話者不明"
    gaps = []
    covered = set()
    for gap in data["scope"]["known_gaps"]:
        ids = gap.get("segment_ids", [])
        covered.update(ids)
        links = " ・ ".join(f'<a href="#{esc(sid)}">本文の該当箇所</a>' for sid in ids)
        gaps.append(f'<li>{esc(gap["description_ja"])} {links}</li>')
    for segment in data["segments"]:
        messages = []
        if include_scoped_issues or segment["id"] not in covered:
            messages.extend(issue["message_ja"] for issue in segment.get("issues", []))
        messages.extend(attribution_name(item) + (f'：{item["evidence_ja"]}' if item.get("evidence_ja") else "") for item in segment.get("attributions", []))
        # Corrected transcription history is not an alternative reading.
        for variant in segment.get("source_variants", []):
            if variant["kind"] == "corrected" or (not include_ocr and variant["kind"] == "ocr"):
                continue
            links = " ・ ".join(external_link(loc["url"], "照合資料")
                               for loc in variant.get("source_locations", []) if loc.get("url"))
            gaps.append(f'<li>{esc(variant["description_ja"])} '
                        f'「{esc(variant["text"])}」 {links} '
                        f'<a href="#{esc(segment["id"])}">本文の該当箇所</a></li>')

        for message in messages:
            gaps.append(f'<li>{esc(message)} <a href="#{esc(segment["id"])}">本文の該当箇所</a></li>')
    caveats = f'<ul class="caveats">{"".join(gaps)}</ul>' if gaps else ""
    sources = []
    for source in data["sources"]:
        parts = [external_link(source["url"], source["title"])]
        for key in ("work_rights", "transcription_rights"):
            rights = source[key]
            if rights.get("attribution"):
                parts.append(esc(rights["attribution"]))
            if rights.get("license_url"):
                parts.append(external_link(rights["license_url"], rights.get("license_id", "利用条件")))
            if include_source_rights_notes:
                if rights.get("note_ja"):
                    parts.append(esc(rights["note_ja"]))
                if rights.get("evidence_url"):
                    parts.append(external_link(rights["evidence_url"], "利用条件の根拠"))
        sources.append(f'<li>{" / ".join(dict.fromkeys(parts))}</li>')
    authors = "、".join(c["name_ja"] for c in data["metadata"]["contributors"] if "author" in c["roles"])
    rights = data["metadata"]["translation_rights"]
    license_link = external_link(rights["license_url"], rights.get("license_id", "利用条件")) if rights.get("license_url") else esc(rights.get("note_ja", ""))
    return (f'<section id="notes" class="apparatus"><h2>注釈</h2>'
            f'{render_notes(data, refs_by_note, note_numbers, origin_labels=not include_ocr, segment_note_links=segment_note_links)}{caveats}'
            f'<p>原著：{esc(authors)}。{esc(DISCLAIMER)}</p><p>{esc(rights["attribution"])} {license_link}</p>'
            f'<ul class="sources-list">{"".join(sources)}</ul></section>')



def render_chapter(data, number):
    note_numbers = {note["id"]: i for i, note in enumerate(data.get("notes", []), 1)}
    by_segment, by_note = defaultdict(list), defaultdict(list)
    for ref in data.get("references", []):
        if ref["to"]["type"] != "note":
            raise ValueError(f'Unsupported reference target: {ref["id"]}')
        by_segment[ref["from"]["segment_id"]].append(ref)
        by_note[ref["to"]["id"]].append(ref)
    occurrences = defaultdict(list)
    for item in data.get("lexicon", {}).get("first_occurrences", []):
        occurrences[item["segment_id"]].append(item)
    body_segments = [s for s in data["segments"] if s["kind"] != "note_body"]
    body = "\n".join(render_segment(s, by_segment[s["id"]], note_numbers, occurrences[s["id"]]) for s in body_segments)
    content = (f'{chapter_navigation(number)}<article id="reading" class="reading-body">{body}</article>'
               f'{render_annotations(data, by_note, note_numbers)}{chapter_navigation(number)}')
    return page_shell(data["metadata"]["title_ja"], content, "assets/reading.css")



def render_index(documents):
    links = []
    for number, document in enumerate(documents, 1):
        heading = next(segment["translation_ja"] for segment in document["segments"]
                       if segment["kind"] == "heading")
        # Reuse the complete existing Japanese title, folding layout whitespace only.
        title = " ".join(heading.split())
        links.append(f'<li><a href="chapter-{number:03d}.html">{esc(title)}</a></li>')
    links = "".join(links)
    # The landing page contains only the book title, translator credit, contents and repository address.
    # Notes and required attribution stay on chapter pages.
    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self'; base-uri 'none'; form-action 'none'; connect-src 'none'">
<title>西遊記日本語訳</title>
<link rel="stylesheet" href="../assets/reading.css">
</head>
<body class="index-page">
<main id="main" class="contents">
<h1>西遊記</h1>
<p class="translator-credit">翻訳者：{external_link("https://x.com/cacazu_right", "心霊研究家ポロミン(@cacazu_right)")}　ChatGPT訳</p>
<h2 id="chapters">目次</h2>
<ul>{links}</ul>
<p><a href="../index.html">索引に戻る</a></p>
<p><a href="https://github.com/cacazu/nihonjinbun" rel="noreferrer">https://github.com/<wbr>cacazu/nihonjinbun</a></p>
</main>
</body>
</html>
'''


def render_library_index():
    return page_shell("索引", '<h1>索引</h1><ul><li><a href="xiyouji/index.html">西遊記</a></li>'
                      '<li><a href="tanaka/index.html">田中義能</a></li></ul>'
                      '<p><a href="https://github.com/cacazu/nihonjinbun">リポジトリ</a></p>', "assets/reading.css")


def render_tanaka_index(documents):
    links = ''.join(f'<li><a href="{esc(slug)}.html">{esc(data["metadata"]["title_ja"])}</a></li>' for slug, data in documents)
    return page_shell("田中義能", '<h1>田中義能</h1><ul>' + links + '</ul>'
                      '<p><a href="../index.html">索引に戻る</a></p>')


def render_redirect(number):
    target = f"xiyouji/chapter-{number:03d}.html"
    # No script is needed for the page-level redirect.
    content = page_shell("西遊記", f'<p><a href="{target}">西遊記 第{NUMERALS[number-1]}回</a></p>', "assets/reading.css")
    return content.replace('<title>', f'<meta http-equiv="refresh" content="0;url={target}">\n<link rel="canonical" href="{target}">\n<title>', 1)


def render_branch_table(group, segments, refs, note_numbers):
    """Read the source's five cells once, in source order, with explicit branching."""
    positions = [(m.get("row"), m.get("column")) for m in group["members"]]
    if positions != [(1, 1), (1, 2), (2, 2), (3, 2), (1, 3)]:
        raise ValueError("Unsupported table layout; review the source before rendering")
    cells = []
    for member, role in zip(group["members"], ("origin", "branch-one", "branch-two", "branch-three", "outcome")):
        sid = member["segment_id"]
        if segments[sid]["kind"] != "table_cell":
            raise ValueError("Reading table must contain table cells")
        text = render_text(segments[sid]["translation_ja"], refs[sid], "translation_span", note_numbers)
        cells.append(f'<div id="{esc(sid)}" class="table_cell translation story-text {role}">{text}</div>')
    return (f'<figure class="source-branch-table" id="{esc(group["id"])}">'
            f'<figcaption>{esc(group["description_ja"])}</figcaption>'
            '<div class="branch-table">' + ''.join(cells) + '</div></figure>')


def render_hongi_contents(data, segments, *, recursive=False):
    """Reader navigation is distinct from the source index's printed-page references."""
    sections = data["sections"]
    def item(section):
        members = [s for s in data["segments"] if s["section_id"] == section["id"]]
        headings = section["heading_segment_ids"]
        if not headings and not members:
            child_ids = {child["id"] for child in sections if child.get("parent_id") == section["id"]}
            members = [s for s in data["segments"] if s["section_id"] in child_ids]
        if not headings and not members:
            return ""
        sid = headings[0] if headings else members[0]["id"]
        label = section.get("label_ja") or segments[sid]["translation_ja"]
        if section["id"] in ("sh-toc", "kdk-toc", "shinto-koen-toc", "jinja-hongi-toc"):
            label = "原目次（原刊頁）"
        children = ''.join(item(child) for child in sections
                           if child.get("parent_id") == section["id"]) if recursive or section["kind"] == "chapter" else ""
        return f'<li><a href="#{esc(sid)}">{esc(label)}</a>' + (f'<ul>{children}</ul>' if children else '') + '</li>'
    return [item(section) for section in sections if section.get("parent_id") is None]


# Publication is opt-in, including every image byte; never copy arbitrary assets.
READING_ASSET_ALLOWLIST = {
    "assets/tanaka-jinja-hongi-1926/shrine-deities-classification.png":
        "e8c74293a29cfcc64d9e1e6a996e7510f2aab69f96b318b55cbed5f8cac599e9",
}


def reading_assets(data):
    """Return only explicitly approved, decoded, hash-verified figure images."""
    assets = {asset["id"]: asset for asset in data.get("assets", [])}
    result = {}
    for figure in data.get("figures", []):
        asset = assets.get(figure["asset_id"])
        if not asset or asset.get("status") != "available" or not figure.get("alt_ja"):
            raise ValueError("Published figures require an available asset and nonempty alt text")
        relative = asset["path"]
        expected = READING_ASSET_ALLOWLIST.get(relative)
        if not expected or asset.get("sha256") != expected or asset.get("media_type") != "image/png":
            raise ValueError("Figure asset is not explicitly approved for publication")
        path = ROOT / relative
        # An allowlisted spelling must not conceal a symlink outside the source tree.
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            raise ValueError("Figure asset paths must not contain symlinks")
        if not path.resolve().is_relative_to((ROOT / "assets" / data["work_id"]).resolve()):
            raise ValueError("Figure asset must remain inside its work asset directory")
        content = path.read_bytes()
        if len(content) != asset["bytes"] or hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("Figure asset bytes or SHA-256 do not match the reviewed manuscript")
        with Image.open(io.BytesIO(content)) as image:
            if image.format != "PNG" or image.size != (asset["width"], asset["height"]):
                raise ValueError("Figure image format or dimensions do not match the manuscript")
            image.verify()
        result[relative] = content
    return result


def render_source_figure(figure, asset):
    caption = f'<figcaption>{esc(figure["caption_ja"])}</figcaption>' if figure.get("caption_ja") else ""
    # Caption/text segments retain their normal reading position and fixed IDs.
    return (f'<figure class="source-figure" id="{esc(figure["id"])}">'
            f'<img src="../{esc(asset["path"])}" width="{asset["width"]}" height="{asset["height"]}" '
            f'alt="{esc(figure["alt_ja"])}" loading="lazy" decoding="async">{caption}</figure>')


def render_column_table(group, segments, render_value, render_links):
    """Keep source column-major order, sparse cells, coordinates and every label.

    A CSS matrix retains source rows and right-to-left source columns. Definition
    lists expose each cell's row/column/label without inventing missing cells or
    guessing shared-cell spans from editorial prose.
    """
    members = group["members"]
    coordinates = [(m.get("column"), m.get("row")) for m in members]
    if (not members or
            any(type(c) is not int or type(r) is not int or not 1 <= c <= 15 or not 1 <= r <= 3
                for c, r in coordinates) or coordinates != sorted(set(coordinates))):
        raise ValueError("Unsupported source table coordinates/order; review before publishing")
    cells = []
    for member in members:
        sid = member["segment_id"]
        if segments[sid]["kind"] != "table_cell" or not member.get("label_ja"):
            raise ValueError("Source tables require labelled table_cell members")
        row, column = member["row"], member["column"]
        label = f'原表 第{column}列・第{row}段：{member["label_ja"]}'
        cells.append(f'<div class="source-table-cell source-row-{row} source-column-{column}" '
                     f'data-source-row="{row}" data-source-column="{column}" data-source-label="{esc(member["label_ja"])}">'
                     f'<dt>{esc(label)}</dt><dd id="{esc(sid)}" class="table_cell translation story-text">'
                     f'{render_value(segments[sid])}</dd>{render_links([sid])}</div>')
    return (f'<figure class="source-table" id="{esc(group["id"])}">'
            f'<figcaption>{esc(group.get("description_ja", ""))}</figcaption>'
            '<p class="paragraph-glosses">原表の列は右から左へ、各列は上・中・下段の順です。横にスクロールして読めます。共通欄・括弧の範囲は各欄の説明に残しています。</p>'
            '<div class="source-table-scroll" tabindex="0" role="region" aria-label="原刊の官社表（横スクロール）">'
            '<dl class="source-table-grid">' + ''.join(cells) + '</dl></div></figure>')


def render_jinja(data, *, include_reader_notes=True):
    """Render the reviewed Jinja manuscript, including references within notes."""
    verified_assets = reading_assets(data)
    segments = {s["id"]: s for s in data["segments"]}
    notes = {n["id"]: n for n in data.get("notes", [])}
    note_numbers = {nid: i for i, nid in enumerate(notes, 1)}
    by_segment, by_target = defaultdict(list), defaultdict(list)
    for ref in data.get("references", []):
        target = ref.get("to") or {}
        if ref.get("status") != "verified" or target.get("type") not in ("note", "segment", "source_location"):
            raise ValueError(f'Unsupported reading reference: {ref["id"]}')
        if target["type"] == "note" and target["id"] not in notes:
            raise ValueError("Missing reading note target")
        if target["type"] == "segment" and target["id"] not in segments:
            raise ValueError("Missing reading segment target")
        by_segment[ref["from"]["segment_id"]].append(ref)
        if target["type"] in ("note", "segment"):
            by_target[target["id"]].append(ref)

    source_marker_refs = {nid: by_target[nid][0]["id"] for nid, note in notes.items()
                          if note["origin"] != "translator" and by_target[nid]}

    def note_label(nid):
        return "訳注" if notes[nid]["origin"] == "translator" else "原注"

    def value(segment):
        text = segment["translation_ja"]
        refs = sorted((r for r in by_segment[segment["id"]] if "translation_span" in r["from"]),
                      key=lambda r: r["from"]["translation_span"]["start"])
        result, offset = [], 0
        for ref in refs:
            span = ref["from"]["translation_span"]
            start, end = span["start"], span["end"]
            if start < offset or not 0 <= start < end <= len(text) or text[start:end] != span["exact"]:
                raise ValueError(f'Overlapping or invalid text span: {ref["id"]}')
            target = ref["to"]
            if target["type"] not in ("note", "segment"):
                raise ValueError("Source-page references must not become guessed inline links")
            attrs = 'class="cross-reference"'
            if target["type"] == "note":
                nid = target["id"]
                attrs = (f'class="note-ref" data-note="{note_numbers[nid]}" '
                         f'title="{note_label(nid)} {note_numbers[nid]}" aria-describedby="note-label-{esc(nid)}"')
            result.append(esc(text[offset:start]))
            result.append(f'<a {attrs} id="{esc(ref["id"])}-ja" href="#{esc(target["id"])}">{esc(text[start:end])}</a>')
            offset = end
        result.append(esc(text[offset:]))
        return ''.join(result)

    def links(segment_ids):
        result = []
        for sid in segment_ids:
            for ref in by_segment[sid]:
                if "translation_span" in ref["from"]:
                    continue
                target = ref["to"]
                rid = esc(ref["id"]) + "-ja"
                if target["type"] == "note":
                    nid = target["id"]
                    link = f'<a id="{rid}" href="#{esc(nid)}" aria-describedby="note-label-{esc(nid)}">{note_label(nid)} {note_numbers[nid]}</a>'
                    if source_marker_refs.get(nid) == ref["id"]:
                        link = f'<span class="source-note-marker" id="source-note-{esc(nid)}">{link}</span>'
                    result.append(link)
                elif target["type"] == "segment":
                    label = ref.get("label") or ("本文の続き" if ref["origin"] == "translator" else "本文の参照先")
                    result.append(f'<a id="{rid}" href="#{esc(target["id"])}" title="{esc(ref.get("description_ja", ""))}">{esc(label)} →</a>')
                else:
                    location = target["location"]
                    page = location["printed_page"]
                    if location.get("printed_page_end"):
                        page += "–" + location["printed_page_end"]
                    label = "原目次の参照先" if ref["kind"] == "index" else "原刊の参照先"
                    result.append(f'<span class="index-source-reference" id="{rid}">{label}：原刊{esc(page)}頁。{esc(ref.get("description_ja", ""))}</span>')
        return '<div class="paragraph-glosses segment-references">' + ' ・ '.join(result) + '</div>' if result else ''

    def segment_html(segment):
        tag = "h2" if segment["kind"] == "heading" else "div"
        return (f'<section class="segment {esc(segment["kind"])}" id="{esc(segment["id"])}">'
                f'<{tag} class="story-text translation" lang="ja">{value(segment)}</{tag}></section>')

    body_ids = [s["id"] for s in data["segments"] if s["kind"] != "note_body"]
    groups, grouped = {}, set()
    for group in data.get("groups", []):
        members = [m["segment_id"] for m in group["members"]]
        if not members or group["kind"] not in ("paragraph", "table", "quotation", "list"):
            raise ValueError("Unsupported reading group")
        if group["kind"] == "paragraph" and group.get("separator", "") != "":
            raise ValueError("Continued paragraphs must not invent separators")
        start = body_ids.index(members[0])
        if body_ids[start:start + len(members)] != members or grouped.intersection(members):
            raise ValueError("Reading groups must contain consecutive, unique segments")
        groups[members[0]] = group
        grouped.update(members)
    before, after = defaultdict(list), defaultdict(list)
    assets = {a["id"]: a for a in data.get("assets", [])}
    figure_ids = set()
    for figure in data.get("figures", []):
        placement = figure["placement"]
        anchor, position = placement["anchor_id"], placement["position"]
        if (figure["id"] in figure_ids or placement["anchor_type"] != "segment" or
                anchor not in body_ids or position not in ("before", "after")):
            raise ValueError("Unsupported or duplicate figure placement")
        figure_ids.add(figure["id"])
        for group in groups.values():
            members = [m["segment_id"] for m in group["members"]]
            if anchor in members and anchor != members[0 if position == "before" else -1]:
                raise ValueError("A figure cannot split a joined reading group")
        for sid in figure.get("text_segment_ids", []) + figure.get("caption_segment_ids", []):
            if sid not in body_ids:
                raise ValueError("Figure text and captions must render once in the reading body")
        (before if position == "before" else after)[anchor].append(render_source_figure(figure, assets[figure["asset_id"]]))
    section_anchors, empty_sections = defaultdict(list), []
    for section in data["sections"]:
        members = [s["id"] for s in data["segments"] if s["section_id"] == section["id"]]
        if not members:
            empty_sections.append(section)
        else:
            section_anchors[members[0]].append(section["id"])
    body = []
    for segment in data["segments"]:
        sid = segment["id"]
        body.extend(f'<span id="{esc(section_id)}" class="source-section-anchor" aria-hidden="true"></span>' for section_id in section_anchors[sid])
        if segment["kind"] == "note_body":
            continue
        if sid in grouped and sid not in groups:
            continue
        body.extend(before[sid])
        members = [sid]
        if sid in groups:
            group = groups[sid]
            members = [m["segment_id"] for m in group["members"]]
            if group["kind"] == "table":
                body.append(render_column_table(group, segments, value, links))
            elif group["kind"] == "paragraph":
                spans = ''.join(f'<span id="{esc(mid)}" class="translation">{value(segments[mid])}</span>' for mid in members)
                body.append(f'<section class="segment paragraph" id="{esc(group["id"])}"><div class="story-text">{spans}</div></section>')
            else:
                tag = "blockquote" if group["kind"] == "quotation" else "div"
                body.append(f'<{tag} id="{esc(group["id"])}" class="source-{esc(group["kind"])}" aria-label="{esc(group.get("description_ja", ""))}">' + ''.join(segment_html(segments[mid]) for mid in members) + f'</{tag}>')
        else:
            body.append(segment_html(segment))
        if sid not in groups or groups[sid]["kind"] != "table":
            body.append(links(members))
        body.extend(after[members[-1]])

    note_items = []
    rendered_note_bodies = []
    for nid, note in notes.items():
        content = []
        for item in note["body"]:
            sid = item["segment_id"]
            if segments[sid]["kind"] != "note_body" or "translation_span" in item:
                raise ValueError("Unsupported inline note-body layout")
            rendered_note_bodies.append(sid)
            content.append(f'<div id="{esc(sid)}" class="story-text note-body">{value(segments[sid])}</div>' + links([sid]))
        backlinks = []
        if note["origin"] != "translator":
            if nid not in source_marker_refs:
                raise ValueError("Source notes require an explicit source-position reference")
            backlinks.append(f'<a href="#source-note-{esc(nid)}">原注の位置へ戻る ↑</a>')
        backlinks.extend(f'<a href="#{esc(r["id"])}-ja">参照元 {i} へ戻る ↑</a>' for i, r in enumerate(by_target[nid], 1))
        source_links = ''.join(f'<li>{external_link(loc["url"], "原注の出典" + ("（原刊" + loc["printed_page"] + "頁）" if loc.get("printed_page") else ""))}</li>' for loc in note.get("source_locations", []) if loc.get("url"))
        description = f'<p>{esc(note["description_ja"])}</p>' if note.get("description_ja") else ''
        note_items.append(f'<li class="note-card" id="{esc(nid)}"><h3 id="note-label-{esc(nid)}">{note_label(nid)} {note_numbers[nid]:02d}</h3>{description}' + ''.join(content) + (f'<ul class="note-sources">{source_links}</ul>' if source_links else '') + '<div class="backlinks">' + ''.join(backlinks) + '</div></li>')
    expected_note_bodies = {s["id"] for s in data["segments"] if s["kind"] == "note_body"}
    if set(rendered_note_bodies) != expected_note_bodies or len(rendered_note_bodies) != len(expected_note_bodies):
        raise ValueError("Note bodies must render exactly once")
    # Reuse caveats, source attribution and rights without rendering notes twice.
    without_notes = dict(data, notes=[])
    annotations = render_annotations(without_notes, defaultdict(list), {}, include_ocr=False, include_scoped_issues=True, resolve_attribution_names=True, include_source_rights_notes=True)
    annotations = annotations.replace('<h2>注釈</h2>', '<h2>注釈</h2><ol class="notes-list">' + ''.join(note_items) + '</ol>', 1)
    source_annotations = []
    for segment in data["segments"]:
        for annotation in segment.get("annotations", []):
            label = {"ruby": "原文のルビ", "emphasis": "原文の傍点", "language": "原文の言語", "strong": "原文の太字"}.get(annotation["kind"])
            if label is None:
                raise ValueError("Unsupported source annotation")
            detail = annotation.get("reading") or annotation.get("language")
            source_annotations.append(f'<li>{label}「{esc(annotation["span"]["exact"])}」' + (f'：{esc(detail)}' if detail else '') + f' <a href="#{esc(segment["id"])}">該当箇所</a></li>')
    original_annotations = '<section class="apparatus"><h2>原典の注記</h2><ul>' + ''.join(source_annotations) + '</ul></section>'
    source_correspondences = []
    for segment in data["segments"]:
        locations = segment.get("source_locations", [])
        if len(locations) > 1:
            source_correspondences.append('<li><a href="#' + esc(segment["id"]) + '">本文の該当箇所</a>：' + ' ・ '.join(external_link(loc["url"], f'原典第{loc["source_sequence"] + 1}コマ（原刊{loc.get("printed_page", "")}頁）') for loc in locations if loc.get("url") and "source_sequence" in loc) + '</li>')
    correspondence_html = '<section class="apparatus"><h2>重複撮影を含む原典の対応</h2><ul>' + ''.join(source_correspondences) + '</ul></section>' if source_correspondences else ''
    inventory_items = []
    for source in data["sources"]:
        for record in source.get("page_inventory", []):
            if record.get("segment_ids"):
                continue
            location = record["location"]
            label = f'原典第{location["source_sequence"] + 1}コマ'
            label_html = external_link(location["url"], label) if location.get("url") else esc(label)
            inventory_items.append(f'<li>{label_html}：{esc(record.get("description_ja", ""))}</li>')
    empty_anchors = ''.join(f'<span id="{esc(section["id"])}" class="source-section-anchor" aria-hidden="true"></span>' for section in empty_sections)
    inventory_html = '<section class="apparatus">' + empty_anchors + '<h2>原典の本文外ページ</h2><ul>' + ''.join(inventory_items) + '</ul></section>' if inventory_items else ''
    asset_items = []
    for figure in data.get("figures", []):
        asset = assets[figure["asset_id"]]
        rights = asset["rights"]
        parts = [f'<a href="#{esc(figure["id"])}">図へ戻る</a>', esc(figure.get("description_ja", "")), esc(rights.get("attribution", "")), esc(rights.get("note_ja", ""))]
        for key, label in (("license_url", rights.get("license_id", "図版の利用条件")), ("evidence_url", "利用条件の根拠")):
            if rights.get(key):
                parts.append(external_link(rights[key], label))
        for location in asset["source_locations"]:
            label = f'図版の出典（原刊{location.get("printed_page", "")}頁）'
            if location.get("url"):
                parts.append(external_link(location["url"], label))
        parts.extend(esc(item["description_ja"]) for item in asset.get("processing", []))
        asset_items.append(f'<li id="{esc(asset["id"])}">' + ' / '.join(part for part in parts if part) + '</li>')
    asset_html = '<section class="apparatus figure-rights"><h2>原図の出典・利用条件</h2><p>以下は原図の利用条件です。現代語訳の利用条件とは別です。</p><ul>' + ''.join(asset_items) + '</ul></section>' if asset_items else ''
    # Exact source cross-references receive return paths, not guessed TOC links.
    cross_backlinks = []
    for sid, refs in by_target.items():
        if sid not in segments:
            continue
        for ref in refs:
            cross_backlinks.append(f'<li><a href="#{esc(sid)}">参照先</a>：{esc(ref.get("description_ja", ""))} <a href="#{esc(ref["id"])}-ja">参照元へ戻る ↑</a></li>')
    reference_html = '<section class="apparatus"><h2>本文の参照・改頁の接続</h2><ul>' + ''.join(cross_backlinks) + '</ul></section>' if cross_backlinks else ''
    toc = render_hongi_contents(data, segments, recursive=True)
    reader_notes = '<section class="apparatus"><h2>この訳について</h2>' + ''.join(f'<p>{esc(n)}</p>' for n in data["metadata"].get("reader_notes_ja", [])) + '</section>' if include_reader_notes else ''
    nav = '<nav class="chapter-nav" aria-label="読書ページの移動"><a href="#contents">目次に戻る</a><a href="index.html">田中義能</a><a href="../index.html">索引に戻る</a></nav>'
    title = data["metadata"]["title_ja"]
    content = (nav + f'<h1>{esc(title)}</h1><nav id="contents" aria-label="{esc(title)}の目次"><h2>読書用目次</h2><ul>' + ''.join(toc) + '</ul></nav><article id="reading" class="reading-body">' + '\n'.join(body) + '</article>' + annotations + reader_notes + asset_html + correspondence_html + inventory_html + reference_html + original_annotations + nav)
    return page_shell(title + " 日本語訳", content, allow_images=bool(verified_assets))


def render_taii(data, *, include_reader_notes=False):
    if data["work_id"] == "tanaka-jinja-hongi-1926":
        return render_jinja(data, include_reader_notes=include_reader_notes)
    title = data["metadata"]["title_ja"]
    # This book records notes against entire source paragraphs, not guessed words.
    segment_note_links = data["work_id"] == "tanaka-kokumin-dotoku-yoryo-kogi-1924"
    note_numbers = {note["id"]: i for i, note in enumerate(data.get("notes", []), 1)}
    by_segment, by_note, continuations = defaultdict(list), defaultdict(list), defaultdict(list)
    index_refs = defaultdict(list)
    for ref in data.get("references", []):
        if ref["to"]["type"] == "note":
            by_segment[ref["from"]["segment_id"]].append(ref)
            by_note[ref["to"]["id"]].append(ref)
        elif ref["to"]["type"] == "segment" and ref["kind"] == "cross_reference" and ref["origin"] == "translator" and not any(key in ref["from"] for key in ("source_span", "translation_span")):
            continuations[ref["from"]["segment_id"]].append(ref)
        elif ref["to"]["type"] == "source_location" and (ref["kind"] == "index" or
                (ref["kind"] == "cross_reference" and ref["origin"] == "source")):
            index_refs[ref["from"]["segment_id"]].append(ref)
        else:
            raise ValueError(f'Unsupported reference target: {ref["id"]}')
    segments = {s["id"]: s for s in data["segments"]}
    body_segments = [s for s in data["segments"] if s["kind"] != "note_body"]
    groups, grouped = {}, set()
    ids = [s["id"] for s in body_segments]
    for group in data.get("groups", []):
        members = [m["segment_id"] for m in group["members"]]
        if group["kind"] not in ("paragraph", "table") or not members or (group["kind"] == "paragraph" and group.get("separator", "") != ""):
            raise ValueError("Unsupported reading group")
        start = ids.index(members[0])
        if ids[start:start+len(members)] != members or grouped.intersection(members):
            raise ValueError("Reading groups must contain consecutive, unique segments")
        groups[members[0]] = group
        grouped.update(members)
    def continuation_links(segment_ids):
        return ''.join(f'<p class="paragraph-glosses continuation-link" id="{esc(ref["id"])}-ja"><a href="#{esc(ref["to"]["id"])}">{esc(ref.get("label", "本文の続き"))} →</a></p>'
                       for sid in segment_ids for ref in continuations[sid])
    def paragraph_note_links(segment_ids):
        if not segment_note_links:
            return ""
        links = []
        for sid in segment_ids:
            for ref in by_segment[sid]:
                if "translation_span" in ref["from"]:
                    continue
                nid = ref["to"]["id"]
                note = next(note for note in data["notes"] if note["id"] == nid)
                label = {"author": "原注", "unknown": "書込み（筆者不明）", "translator": "訳注"}.get(note.get("origin"), "注")
                links.append(f'<a id="{esc(ref["id"])}-ja" href="#{esc(nid)}" aria-describedby="note-label-{esc(nid)}">{label} {note_numbers[nid]}</a>')
        return '<p class="paragraph-glosses segment-note-references">' + ' ・ '.join(links) + '</p>' if links else ""
    marginal_ids = {sid for record in data.get("provenance", {}).get("nonadjacent_continuations", [])
                    for sid in record.get("intervening_segment_ids", []) if segments[sid]["kind"] == "heading"}
    body = []
    source_note_by_segment = {b["segment_id"]: n for n in data.get("notes", []) for b in n["body"] if n.get("origin") != "translator"}
    for segment in data["segments"]:
        if segment["kind"] == "note_body":
            note = source_note_by_segment.get(segment["id"])
            if note:
                label = "原注" if note["origin"] == "author" else "書込み（筆者不明）"
                body.append(f'<p class="source-note-marker" id="source-note-{esc(note["id"])}"><a href="#{esc(note["id"])}">{label} {note_numbers[note["id"]]}</a></p>')
            continue
        sid = segment["id"]
        if sid in groups:
            group = groups[sid]
            if group["kind"] == "table":
                body.append(render_branch_table(group, segments, by_segment, note_numbers))
                continue
            spans = ''.join(f'<span id="{esc(m["segment_id"])}" class="translation">'
                            f'{render_text(segments[m["segment_id"]]["translation_ja"], by_segment[m["segment_id"]], "translation_span", note_numbers)}</span>'
                            for m in group["members"])
            body.append(f'<section class="segment paragraph" id="{esc(group["id"])}"><div class="story-text">{spans}</div></section>')
            note_links = paragraph_note_links([member["segment_id"] for member in group["members"]])
            if note_links:
                body.append(note_links)
            links = continuation_links([member["segment_id"] for member in group["members"]])
            if links:
                body.append(links)
        elif sid not in grouped:
            rendered = render_segment(segment, by_segment[sid], note_numbers)
            if segment["kind"] == "heading":
                rendered = rendered.replace('<h1 ', '<h2 ').replace('</h1>', '</h2>')
            if sid in marginal_ids:
                rendered = '<aside class="source-marginal-heading" aria-label="原典の欄外見出し"><p class="paragraph-glosses">原典の欄外見出し</p>' + rendered + '</aside>'
            body.append(rendered)
            note_links = paragraph_note_links([sid])
            if note_links:
                body.append(note_links)
            for ref in index_refs[sid]:
                location = ref["to"]["location"]
                page = location["printed_page"]
                if location.get("printed_page_end"):
                    page += "–" + location["printed_page_end"]
                label = "原目次の参照先" if ref["kind"] == "index" else "演習の参照先"
                body.append(f'<p class="paragraph-glosses index-source-reference" id="{esc(ref["id"])}-ja">{label}：原刊{esc(page)}頁。{esc(ref.get("description_ja", ""))}</p>')
            if continuations[sid]:
                body.append(continuation_links([sid]))
    toc = []
    for section in data["sections"]:
        if section.get("parent_id") == "main-text":
            headings = section["heading_segment_ids"]
            members = [segment for segment in body_segments if segment["section_id"] == section["id"]]
            if not headings and not members:
                continue
            sid = headings[0] if headings else members[0]["id"]
            label = segments[sid]["translation_ja"] if headings else section.get("label_ja", segments[sid]["translation_ja"])
            toc.append(f'<li><a href="#{esc(sid)}">{esc(label)}</a></li>')
        elif section["id"] in ("colophon", "advertisements"):
            sid = next(s["id"] for s in body_segments if s["section_id"] == section["id"] or
                       (section["id"] == "advertisements" and s["section_id"].startswith("ads-scan-")))
            toc.append(f'<li><a href="#{esc(sid)}">{esc(section["label_ja"])}</a></li>')
    if not any(section.get("parent_id") == "main-text" for section in data["sections"]):
        toc = []
        for section in data["sections"]:
            members = [segment for segment in body_segments if segment["section_id"] == section["id"]]
            if members:
                target = members[0]
                if data["work_id"] == "tanaka-nihon-shoki-gaisetsu-1938" and section["heading_segment_ids"]:
                    target = segments[section["heading_segment_ids"][0]]
                label = section.get("label_ja") or target["translation_ja"]
                toc.append(f'<li><a href="#{esc(target["id"])}">{esc(label)}</a></li>')
    if data["work_id"] in ("tanaka-shinto-hongi-1914", "tanaka-kokumin-dotoku-yoryo-kogi-1924", "tanaka-shinto-koen-1923"):
        toc = render_hongi_contents(data, segments)
    nav = '<nav class="chapter-nav" aria-label="読書ページの移動"><a href="#contents">目次に戻る</a><a href="index.html">田中義能</a><a href="../index.html">索引に戻る</a></nav>'
    # Source-side ruby/emphasis remains provenance, not newly invented translation ruby.
    source_annotations = []
    for segment in data["segments"]:
        for annotation in segment.get("annotations", []):
            label = {"ruby": "原文のルビ", "emphasis": "原文の傍点", "language": "原文の言語", "strong": "原文の太字"}.get(annotation["kind"])
            if label is None:
                raise ValueError(f"Unsupported source annotation: {annotation['kind']}")
            value = f'：{annotation["reading"]}' if annotation.get("reading") else (f'：{annotation["language"]}' if annotation.get("language") else "")
            source_annotations.append(f'<li>{label}「{esc(annotation["span"]["exact"])}」{esc(value)} <a href="#{esc(segment["id"])}">該当箇所</a></li>')
    annotation_html = '<section class="apparatus"><h2>原典の注記</h2><ul>' + ''.join(source_annotations) + '</ul></section>' if source_annotations else ''
    reader_notes = ('<section class="apparatus"><h2>この訳について</h2>' + ''.join(f'<p>{esc(note)}</p>' for note in data["metadata"].get("reader_notes_ja", [])) + '</section>') if include_reader_notes and data["metadata"].get("reader_notes_ja") else ""
    contents_label = "読書用目次" if data["work_id"] in ("tanaka-shinto-hongi-1914", "tanaka-kokumin-dotoku-yoryo-kogi-1924", "tanaka-shinto-koen-1923") else "目次"
    content = (nav + f'<h1>{esc(title)}</h1><nav id="contents" aria-label="{esc(title)}の目次"><h2>{contents_label}</h2><ul>'
               + ''.join(toc) + '</ul></nav><article id="reading" class="reading-body">' + '\n'.join(body) + '</article>'
               + render_annotations(data, by_note, note_numbers, include_ocr=False, include_scoped_issues=data["work_id"] in ("tanaka-nihon-shoki-gaisetsu-1938", "tanaka-shinto-hongi-1914", "tanaka-kokumin-dotoku-yoryo-kogi-1924", "tanaka-shinto-koen-1923"), segment_note_links=segment_note_links) + reader_notes + annotation_html + nav)
    return page_shell(title + " 日本語訳", content)


def build(output):
    documents = []
    for filename in CHAPTERS:
        path = ROOT / "translations" / "wu-chengen" / filename
        data = load_document(path)
        errors = validate_document(data, ROOT)
        if errors:
            raise ValueError(f"{path.name}: " + "; ".join(errors))
        if any(s["kind"] not in ("heading", "paragraph", "verse", "note_body") for s in data["segments"]):
            raise ValueError(f"Unsupported segment kind in {filename}")
        # Do not silently omit orphan note bodies when the manuscript changes.
        note_body_ids = {s["id"] for s in data["segments"] if s["kind"] == "note_body"}
        rendered_ids = [body["segment_id"] for note in data.get("notes", []) for body in note["body"]]
        if note_body_ids != set(rendered_ids) or len(rendered_ids) != len(set(rendered_ids)):
            raise ValueError(f"Note bodies must render exactly once: {filename}")
        documents.append(data)
    tanaka_documents = []
    for slug in TANAKA_WORKS:
        data = load_document(ROOT / f"translations/tanaka/{slug}-ja.yaml")
        reading_assets(data)
        errors = validate_document(data, ROOT)
        if errors:
            raise ValueError(slug + ": " + "; ".join(errors))
        if data["workflow"]["stage"] != "ready":
            raise ValueError(slug + ": manuscript must be reviewed before publication")
        if any(segment["kind"] not in ("heading", "paragraph", "verse", "note_body", "list_item", "separator", "index_entry", "table_cell", "figure_text") for segment in data["segments"]):
            raise ValueError(slug + ": unsupported segment kind")
        note_ids = {segment["id"] for segment in data["segments"] if segment["kind"] == "note_body"}
        rendered_ids = [body["segment_id"] for note in data.get("notes", []) for body in note["body"]
                        if body["segment_id"] in note_ids]
        if note_ids != set(rendered_ids) or len(rendered_ids) != len(set(rendered_ids)):
            raise ValueError(slug + ": note bodies must render exactly once")
        tanaka_documents.append((slug, data))
    pages = {"index.html": render_library_index(), "xiyouji/index.html": render_index(documents),
             "tanaka/index.html": render_tanaka_index(tanaka_documents)}
    pages.update({f"tanaka/{slug}.html": render_taii(data, include_reader_notes=slug != "shinto-taii") for slug, data in tanaka_documents})
    pages.update({f"xiyouji/chapter-{i:03d}.html": render_chapter(d, i) for i, d in enumerate(documents, 1)})
    pages.update({f"chapter-{i:03d}.html": render_redirect(i) for i in range(1, len(documents)+1)})
    pages.update({f"assets/reading.{ext}": (ROOT / "scripts" / f"reading_site.{ext}").read_text(encoding="utf-8") for ext in ("css",)})
    pages["xiyouji/assets/reading.css"] = pages["assets/reading.css"]
    for _, data in tanaka_documents:
        pages.update(reading_assets(data))
    pages[".nojekyll"] = ""
    for relative, content in pages.items():
        target = output / relative
        if not target.resolve().is_relative_to(output.resolve()):
            raise ValueError("Generated output path escapes the output directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8", newline="\n")
    # Remove the retired generated control script when rebuilding an existing site.
    (output / "assets" / "reading.js").unlink(missing_ok=True)
    return pages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs")
    args = parser.parse_args()
    pages = build(args.output)
    print(f"Built {len(pages)} files in {args.output}")


if __name__ == "__main__":
    main()
