#!/usr/bin/env python3
"""Build the five-chapter Xiyouji reader from validated, canonical YAML 2.0."""
import argparse
import html
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from translation_yaml import ROOT, load_document, validate_document

CHAPTERS = tuple(f"xiyouji-chapter-{n:03d}-zh-ja.yaml" for n in range(1, 6))
NUMERALS = ("一", "二", "三", "四", "五")
DISCLAIMER = "AIによる日本語新訳です。全文レビューは進行中で、専門家による独立校訂は未実施です。解釈の未確定箇所は、本文の留保・訳注をご確認ください。"


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


def page_shell(title, content, chapter=None):
    controls = ""
    if chapter is not None:
        controls = '''<div class="reader-controls" hidden>
  <fieldset><legend>表示</legend><button type="button" data-mode="ja" aria-pressed="true">日本語のみ</button><button type="button" data-mode="parallel" aria-pressed="false">原文と対訳</button></fieldset>
  <fieldset class="size-controls"><legend>文字サイズ</legend><button type="button" data-size="small" aria-label="文字サイズ 小" aria-pressed="false">小</button><button type="button" data-size="medium" aria-label="文字サイズ 標準" aria-pressed="true">標準</button><button type="button" data-size="large" aria-label="文字サイズ 大" aria-pressed="false">大</button></fieldset>
</div>'''
    return f'''<!doctype html>
<html lang="ja" data-mode="parallel" data-size="medium">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="西遊記 第一回から第五回。AIによる日本語新訳を、中国語原文・訳注とともに読む静かな読書室。専門家による独立校訂は未実施。">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'; connect-src 'none'">
<title>{esc(title)} | 西遊記を読む</title>
<link rel="stylesheet" href="assets/reading.css">
<script src="assets/reading.js" defer></script>
</head>
<body class="{'chapter-page' if chapter is not None else 'index-page'}">
<a class="skip-link" href="#main">本文へ移動</a>
<header class="site-header"><a class="brand" href="index.html"><span class="brand-seal" aria-hidden="true">西</span><span>西遊記を読む<small>原文と日本語の読書室</small></span></a><a class="header-link" href="index.html#chapters">公開五回の目次</a></header>
{controls}
<main id="main" tabindex="-1">{content}</main>
<footer class="site-footer"><a href="index.html">西遊記を読む</a><span>呉承恩（伝） / 日本語新訳：ChatGPT</span><p>本文・原文翻刻は各回に表示した出典と利用条件に従います。<br>外部送信・アクセス解析は行いません。表示と文字サイズの設定だけを、このブラウザに保存します。</p><a href="#main">ページの先頭へ ↑</a></footer>
</body>
</html>
'''


def chapter_navigation(number, position):
    previous = f'<a rel="prev" href="chapter-{number-1:03d}.html">← 第{NUMERALS[number-2]}回</a>' if number > 1 else '<span class="nav-edge">物語のはじまり</span>'
    following = f'<a rel="next" href="chapter-{number+1:03d}.html">第{NUMERALS[number]}回 →</a>' if number < len(CHAPTERS) else '<span class="nav-edge">公開分はここまで</span>'
    return f'<nav class="chapter-nav" aria-label="各回の移動（{position}）">{previous}<a href="index.html#chapters">目次へ戻る</a>{following}</nav>'


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


def render_segment(segment, refs, note_numbers):
    sid = segment["id"]
    source = segment.get("source_text")
    kind = segment["kind"]
    tag = "h2" if kind == "heading" else "div"
    japanese = render_text(segment["translation_ja"], refs, "translation_span", note_numbers)
    original = render_text(source, refs, "source_span", note_numbers) if source is not None else ""
    result = [f'<section class="segment {esc(kind)}" id="{esc(sid)}">']
    result.append(f'<div class="translation-column"><span class="column-label">日本語訳</span><{tag} class="story-text translation" lang="ja">{japanese}</{tag}></div>')
    if source is not None:
        result.append(f'<div class="source-column"><span class="column-label">原文</span><div class="story-text source" lang="zh-Hant">{original}</div></div>')
    extras = []
    for issue in segment.get("issues", []):
        extras.append(f'<p><strong>解釈・校訂上の留保：</strong>{esc(issue["message_ja"])}</p>')
    if segment.get("source_variants"):
        variants = []
        for variant in segment["source_variants"]:
            links = " ・ ".join(external_link(loc["url"], "照合資料") for loc in variant.get("source_locations", []) if loc.get("url"))
            variants.append(f'<p>{esc(variant["description_ja"])}</p><p class="variant-text" lang="zh-Hant">{esc(variant["text"])}</p>{links}')
        extras.append(f'<details><summary>原文の異同・転記について</summary>{"".join(variants)}</details>')
    for attribution in segment.get("attributions", []):
        extras.append(f'<p>発話・引用の帰属：{esc(attribution["name_ja"])}。{esc(attribution["evidence_ja"])}</p>')
    if extras:
        result.append(f'<aside class="segment-context">{"".join(extras)}</aside>')
    result.append('</section>')
    return "".join(result)


def render_notes(data, refs_by_note, note_numbers):
    notes = data.get("notes", [])
    if not notes:
        return '<section id="notes" class="apparatus"><h2>訳注について</h2><p>この回には独立した巻末訳注はありません。解釈の留保は該当本文と「この版について」に表示しています。</p></section>'
    segments = {segment["id"]: segment for segment in data["segments"]}
    sources = {source["id"]: source for source in data["sources"]}
    items = []
    for note in notes:
        nid = note["id"]
        body = "".join(f'<div id="{esc(item["segment_id"])}" class="story-text note-body">{esc(segments[item["segment_id"]]["translation_ja"])}</div>' for item in note["body"])
        backlinks = []
        for i, ref in enumerate(refs_by_note[nid], 1):
            for field, lang, label in (("translation_span", "ja", "日本語"), ("source_span", "zh", "原文")):
                if field in ref["from"]:
                    backlinks.append(f'<a href="#{esc(ref["id"])}-{lang}">{label}の該当箇所 {i} へ戻る ↑</a>')
        locations = "".join(f'<li>{external_link(loc["url"], sources[loc["source_id"]]["title"])}</li>' for loc in note.get("source_locations", []) if loc.get("url"))
        sources_html = f'<ul class="note-sources">{locations}</ul>' if locations else ""
        items.append(f'<li class="note-card" id="{esc(nid)}"><h3 id="note-label-{esc(nid)}">訳注 {note_numbers[nid]:02d} <small>訳者による注</small></h3>{body}{sources_html}<div class="backlinks">{"".join(backlinks)}</div></li>')
    return f'<section id="notes" class="apparatus"><p class="eyebrow">NOTES</p><h2>物語のことばを、もう少し。</h2><p>本文の下線付きの語から訳注へ移動できます。以下は原著本文とは区別した、訳者による注です。</p><ol class="notes-list">{"".join(items)}</ol></section>'


def render_rights(rights):
    parts = []
    if rights.get("license_url"):
        parts.append(external_link(rights["license_url"], rights.get("license_id", "ライセンス")))
    for field in ("attribution", "note_ja"):
        if rights.get(field):
            parts.append(esc(rights[field]))
    if rights.get("evidence_url"):
        parts.append(external_link(rights["evidence_url"], "利用条件の根拠"))
    return "<br>".join(parts)


def render_edition(data):
    metadata = data["metadata"]
    readers = "".join(f'<li>{esc(note)}</li>' for note in metadata.get("reader_notes_ja", []))
    gaps = []
    for gap in data["scope"]["known_gaps"]:
        links = " ・ ".join(f'<a href="#{esc(sid)}">該当箇所へ</a>' for sid in gap.get("segment_ids", []))
        gaps.append(f'<li>{esc(gap["description_ja"])} {links}</li>')
    sources = []
    for source in data["sources"]:
        role = "本文の底本" if source["role"] == "primary" else "語義・異文の照合資料"
        sources.append(f'''<li id="source-{esc(source["id"])}"><h3>{external_link(source["url"], source["title"])}</h3><p class="source-role">{role}</p><p>{esc(source.get("edition") or "")}</p><p>{esc(source.get("description_ja") or "")}</p><p>{render_rights(source["work_rights"])}</p><p>{render_rights(source["transcription_rights"])}</p></li>''')
    terms = "".join(f'<div><dt><span lang="zh-Hant">{esc(term["source"])}</span> → {esc(term["translation_ja"])}</dt><dd>{esc(term.get("note_ja", ""))}</dd></div>' for term in data.get("terminology", []))
    glossary = f'<details><summary>人名・用語の表記</summary><dl class="glossary">{terms}</dl></details>' if terms else ""
    return f'''<section id="edition" class="apparatus edition"><p class="eyebrow">ABOUT THIS EDITION</p><h2>この版について</h2><p class="edition-warning">{esc(DISCLAIMER)}</p><details><summary>訳文と校訂の方針</summary><ul>{readers}</ul></details><details open><summary>解釈の未確定箇所・留保</summary><ul>{"".join(gaps)}</ul></details>{glossary}<h3>日本語訳の帰属・利用条件</h3><p>{render_rights(metadata["translation_rights"])}</p><p>この読書サイトは、対訳YAML 2.0の本文・原文・注を変更せず、読みやすいHTML表示と参照リンクを加えたものです。共有・改変時は出典と帰属を表示し、同じライセンス条件を継承してください。</p><h3>出典・原文翻刻の帰属</h3><ol class="sources-list">{"".join(sources)}</ol></section>'''


def render_chapter(data, number):
    note_numbers = {note["id"]: i for i, note in enumerate(data.get("notes", []), 1)}
    by_segment, by_note = defaultdict(list), defaultdict(list)
    for ref in data.get("references", []):
        if ref["to"]["type"] != "note":
            raise ValueError(f'Unsupported reference target: {ref["id"]}')
        by_segment[ref["from"]["segment_id"]].append(ref)
        by_note[ref["to"]["id"]].append(ref)
    body_segments = [s for s in data["segments"] if s["kind"] != "note_body"]
    body = "\n".join(render_segment(s, by_segment[s["id"]], note_numbers) for s in body_segments)
    content = f'''{chapter_navigation(number, "上部")}
<header class="chapter-heading"><p class="eyebrow">JOURNEY TO THE WEST <span aria-hidden="true">/</span> {number:02d}</p><h1>西遊記 <span>第{NUMERALS[number-1]}回</span></h1><p class="byline">呉承恩（伝）<span>日本語新訳：ChatGPT</span></p><p class="review-notice">AI翻訳・専門家校訂未了 <a href="#edition">この版について</a></p><nav class="reading-jumps" aria-label="このページの案内"><a href="#reading">本文へ ↓</a><a href="#notes">訳注</a><a href="#edition">出典・利用条件</a></nav></header>
<noscript><p class="no-script">JavaScriptが無効のため、日本語と原文の両方を表示しています。全文と訳注はそのままお読みいただけます。</p></noscript>
<article id="reading" class="reading-body" aria-label="第{NUMERALS[number-1]}回の本文">{body}</article>
<div class="chapter-end"><span>第{NUMERALS[number-1]}回 おわり</span></div>
{chapter_navigation(number, "本文末")}
{render_notes(data, by_note, note_numbers)}
{render_edition(data)}
{chapter_navigation(number, "ページ末")}
'''
    return page_shell(data["metadata"]["title_ja"], content, number)


def render_index(documents):
    links = "".join(
        f'<li><a href="chapter-{number:03d}.html">第{NUMERALS[number-1]}回</a></li>'
        for number, _ in enumerate(documents, 1)
    )
    # The landing page contains only the contents and repository address.
    # Attribution, edition notes and reading controls stay on chapter pages.
    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self'; base-uri 'none'; form-action 'none'; connect-src 'none'">
<title>目次</title>
<link rel="stylesheet" href="assets/reading.css">
</head>
<body class="index-page">
<main id="main" class="contents">
<h1 id="chapters">目次</h1>
<ul>{links}</ul>
<p><a href="https://github.com/cacazu/nihonjinbun" rel="noreferrer">https://github.com/<wbr>cacazu/nihonjinbun</a></p>
</main>
</body>
</html>
'''


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
    pages = {"index.html": render_index(documents)}
    pages.update({f"chapter-{i:03d}.html": render_chapter(d, i) for i, d in enumerate(documents, 1)})
    pages.update({f"assets/reading.{ext}": (ROOT / "scripts" / f"reading_site.{ext}").read_text(encoding="utf-8") for ext in ("css", "js")})
    pages[".nojekyll"] = ""
    for relative, content in pages.items():
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    return pages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs")
    args = parser.parse_args()
    pages = build(args.output)
    print(f"Built {len(pages)} files in {args.output}")


if __name__ == "__main__":
    main()
