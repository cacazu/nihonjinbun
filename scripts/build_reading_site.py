#!/usr/bin/env python3
"""Build the explicitly published reading library from canonical YAML 2.0."""
import argparse
import html
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from translation_yaml import ROOT, load_document, validate_document

PUBLISHED_CHAPTER_COUNT = 100
CHAPTERS = tuple(f"xiyouji-chapter-{n:03d}-zh-ja.yaml" for n in range(1, PUBLISHED_CHAPTER_COUNT + 1))
TANAKA_WORKS = ("shinto-taii", "kodo-no-shimei-sekai-no-shorai", "kokoku-dento-no-seishin", "nihon-seishin-kokutai")
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


def page_shell(title, content, stylesheet="../assets/reading.css"):
    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self'; base-uri 'none'; form-action 'none'; connect-src 'none'">
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


def render_notes(data, refs_by_note, note_numbers, *, origin_labels=False):
    notes = data.get("notes", [])
    segments = {segment["id"]: segment for segment in data["segments"]}
    sources = {source["id"]: source for source in data["sources"]}
    items = []
    for note in notes:
        nid = note["id"]
        body = "".join(f'<div id="{esc(item["segment_id"])}" class="story-text note-body">{esc(segments[item["segment_id"]]["translation_ja"])}</div>' for item in note["body"])
        backlinks = []
        note_label = {"author": "原注", "unknown": "書込み（筆者不明）", "translator": "訳注"}.get(note.get("origin"), "注") if origin_labels else "訳注"
        description = f'<p>{esc(note["description_ja"])}</p>' if origin_labels and note.get("description_ja") else ""
        if origin_labels and note.get("origin") != "translator":
            backlinks.append(f'<a href="#source-note-{esc(nid)}">原注の位置へ戻る ↑</a>')
        for i, ref in enumerate(refs_by_note[nid], 1):
            for field, lang, label in (("translation_span", "ja", "本文"),):
                if field in ref["from"]:
                    backlinks.append(f'<a href="#{esc(ref["id"])}-{lang}">{label}の該当箇所 {i} へ戻る ↑</a>')
        locations = "".join(f'<li>{external_link(loc["url"], sources[loc["source_id"]]["title"])}</li>' for loc in note.get("source_locations", []) if loc.get("url"))
        sources_html = f'<ul class="note-sources">{locations}</ul>' if locations else ""
        items.append(f'<li class="note-card" id="{esc(nid)}"><h3 id="note-label-{esc(nid)}">{note_label} {note_numbers[nid]:02d}</h3>{description}{body}{sources_html}<div class="backlinks">{"".join(backlinks)}</div></li>')
    return f'<ol class="notes-list">{"".join(items)}</ol>' if items else ""


def render_annotations(data, refs_by_note, note_numbers, *, include_ocr=True):
    gaps = []
    covered = set()
    for gap in data["scope"]["known_gaps"]:
        ids = gap.get("segment_ids", [])
        covered.update(ids)
        links = " ・ ".join(f'<a href="#{esc(sid)}">本文の該当箇所</a>' for sid in ids)
        gaps.append(f'<li>{esc(gap["description_ja"])} {links}</li>')
    for segment in data["segments"]:
        messages = []
        if segment["id"] not in covered:
            messages.extend(issue["message_ja"] for issue in segment.get("issues", []))
        messages.extend(f'{item.get("name_ja") or "話者不明"}' + (f'：{item["evidence_ja"]}' if item.get("evidence_ja") else "") for item in segment.get("attributions", []))
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
        sources.append(f'<li>{" / ".join(dict.fromkeys(parts))}</li>')
    authors = "、".join(c["name_ja"] for c in data["metadata"]["contributors"] if "author" in c["roles"])
    rights = data["metadata"]["translation_rights"]
    license_link = external_link(rights["license_url"], rights.get("license_id", "利用条件")) if rights.get("license_url") else esc(rights.get("note_ja", ""))
    return (f'<section id="notes" class="apparatus"><h2>注釈</h2>'
            f'{render_notes(data, refs_by_note, note_numbers, origin_labels=not include_ocr)}{caveats}'
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


def render_taii(data, *, include_reader_notes=False):
    title = data["metadata"]["title_ja"]
    note_numbers = {note["id"]: i for i, note in enumerate(data.get("notes", []), 1)}
    by_segment, by_note = defaultdict(list), defaultdict(list)
    for ref in data.get("references", []):
        if ref["to"]["type"] != "note":
            raise ValueError(f'Unsupported reference target: {ref["id"]}')
        by_segment[ref["from"]["segment_id"]].append(ref)
        by_note[ref["to"]["id"]].append(ref)
    segments = {s["id"]: s for s in data["segments"]}
    body_segments = [s for s in data["segments"] if s["kind"] != "note_body"]
    groups, grouped = {}, set()
    ids = [s["id"] for s in body_segments]
    for group in data.get("groups", []):
        members = [m["segment_id"] for m in group["members"]]
        if group["kind"] != "paragraph" or not members or group.get("separator", "") != "":
            raise ValueError("Unsupported reading group")
        start = ids.index(members[0])
        if ids[start:start+len(members)] != members or grouped.intersection(members):
            raise ValueError("Reading groups must contain consecutive, unique segments")
        groups[members[0]] = group
        grouped.update(members)
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
            spans = ''.join(f'<span id="{esc(m["segment_id"])}" class="translation">'
                            f'{render_text(segments[m["segment_id"]]["translation_ja"], by_segment[m["segment_id"]], "translation_span", note_numbers)}</span>'
                            for m in group["members"])
            body.append(f'<section class="segment paragraph" id="{esc(group["id"])}"><div class="story-text">{spans}</div></section>')
        elif sid not in grouped:
            rendered = render_segment(segment, by_segment[sid], note_numbers)
            if segment["kind"] == "heading":
                rendered = rendered.replace('<h1 ', '<h2 ').replace('</h1>', '</h2>')
            body.append(rendered)
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
                label = section.get("label_ja") or members[0]["translation_ja"]
                toc.append(f'<li><a href="#{esc(members[0]["id"])}">{esc(label)}</a></li>')
    nav = '<nav class="chapter-nav" aria-label="読書ページの移動"><a href="#contents">目次に戻る</a><a href="index.html">田中義能</a><a href="../index.html">索引に戻る</a></nav>'
    # Source-side ruby/emphasis remains provenance, not newly invented translation ruby.
    source_annotations = []
    for segment in data["segments"]:
        for annotation in segment.get("annotations", []):
            label = {"ruby": "原文のルビ", "emphasis": "原文の傍点", "language": "原文の言語"}.get(annotation["kind"])
            if label is None:
                raise ValueError(f"Unsupported source annotation: {annotation['kind']}")
            value = f'：{annotation["reading"]}' if annotation.get("reading") else (f'：{annotation["language"]}' if annotation.get("language") else "")
            source_annotations.append(f'<li>{label}「{esc(annotation["span"]["exact"])}」{esc(value)} <a href="#{esc(segment["id"])}">該当箇所</a></li>')
    annotation_html = '<section class="apparatus"><h2>原典の注記</h2><ul>' + ''.join(source_annotations) + '</ul></section>' if source_annotations else ''
    reader_notes = ('<section class="apparatus"><h2>この訳について</h2>' + ''.join(f'<p>{esc(note)}</p>' for note in data["metadata"].get("reader_notes_ja", [])) + '</section>') if include_reader_notes and data["metadata"].get("reader_notes_ja") else ""
    content = (nav + f'<h1>{esc(title)}</h1><nav id="contents" aria-label="{esc(title)}の目次"><h2>目次</h2><ul>'
               + ''.join(toc) + '</ul></nav><article id="reading" class="reading-body">' + '\n'.join(body) + '</article>'
               + render_annotations(data, by_note, note_numbers, include_ocr=False) + reader_notes + annotation_html + nav)
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
        errors = validate_document(data, ROOT)
        if errors:
            raise ValueError(slug + ": " + "; ".join(errors))
        if data["workflow"]["stage"] != "ready":
            raise ValueError(slug + ": manuscript must be reviewed before publication")
        if any(segment["kind"] not in ("heading", "paragraph", "verse", "note_body", "list_item", "separator") for segment in data["segments"]):
            raise ValueError(slug + ": unsupported segment kind")
        note_ids = {segment["id"] for segment in data["segments"] if segment["kind"] == "note_body"}
        rendered_ids = [body["segment_id"] for note in data.get("notes", []) for body in note["body"]]
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
    pages[".nojekyll"] = ""
    for relative, content in pages.items():
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
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
