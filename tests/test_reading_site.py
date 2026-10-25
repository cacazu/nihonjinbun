"""The reader must faithfully publish only the explicitly selected chapters."""
import copy
import hashlib
import posixpath
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_reading_site as reader
from translation_yaml import load_document


class Elements(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.nodes, self.stack = [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "text": "", "parents": list(self.stack)}
        self.nodes.append(node)
        if tag not in ("meta", "link", "br", "img", "input", "hr", "wbr"):
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                self.stack = self.stack[:i]
                break

    def handle_data(self, data):
        for node in self.stack:
            node["text"] += data

    def by_id(self, value):
        return [n for n in self.nodes if n["attrs"].get("id") == value]


class IndexCreditTests(unittest.TestCase):
    def test_exact_credit_link_position_and_page_title(self):
        # Synthetic input keeps this small header-only regression check independent
        # of the full book build and all 100 chapter validation.
        document = {"segments": [{"kind": "heading", "translation_ja": "第一回 題名"}]}
        page = Elements(reader.render_index([document]))
        main, = page.by_id("main")
        children = [node for node in page.nodes if node["parents"]
                    and node["parents"][-1] is main]
        self.assertEqual(children[0]["text"], "西遊記")
        credit = children[1]
        self.assertEqual((credit["tag"], credit["attrs"].get("class")),
                         ("p", "translator-credit"))
        self.assertEqual(credit["text"],
                         "翻訳者：心霊研究家ポロミン(@cacazu_right)　ChatGPT訳")
        link, = [node for node in page.nodes if node["tag"] == "a"
                 and any(parent is credit for parent in node["parents"])]
        self.assertEqual(link["text"], "心霊研究家ポロミン(@cacazu_right)")
        self.assertEqual(link["attrs"]["href"], "https://x.com/cacazu_right")
        self.assertEqual(children[2]["text"], "目次")
        self.assertEqual([node["text"] for node in page.nodes if node["tag"] == "title"],
                         ["西遊記日本語訳"])


class IndexRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = [load_document(ROOT / "translations" / "wu-chengen" / name)
                         for name in reader.CHAPTERS]

    def test_index_contains_book_title_credit_chapter_titles_and_repository_only(self):
        page = Elements(reader.render_index(self.documents))
        main, = page.by_id("main")
        children = [node for node in page.nodes if node["parents"]
                    and node["parents"][-1] is main]
        self.assertEqual([node["tag"] for node in children], ["h1", "p", "h2", "ul", "p", "p"])
        self.assertEqual(children[0]["text"], "西遊記")
        self.assertEqual(children[2]["text"], "目次")
        self.assertEqual(children[2]["attrs"]["id"], "chapters")
        expected = [("心霊研究家ポロミン(@cacazu_right)", "https://x.com/cacazu_right")]
        for number, document in enumerate(self.documents, 1):
            heading, = [segment["translation_ja"] for segment in document["segments"]
                        if segment["kind"] == "heading"]
            expected.append((" ".join(heading.split()), f"chapter-{number:03d}.html"))
        expected.append(("索引に戻る", "../index.html"))
        expected.append(("https://github.com/cacazu/nihonjinbun",
                         "https://github.com/cacazu/nihonjinbun"))
        self.assertEqual([(node["text"], node["attrs"]["href"])
                          for node in page.nodes if node["tag"] == "a"], expected)
        self.assertFalse(any(node["tag"] in ("header", "footer", "script", "button")
                             for node in page.nodes))
        self.assertEqual([node["text"] for node in page.nodes if node["tag"] == "title"],
                         ["西遊記日本語訳"])

    def test_index_escapes_titles_and_only_folds_layout_whitespace(self):
        title = '第一回\n<仏> & "猿"\n 天地'
        document = {"segments": [{"kind": "heading", "translation_ja": title}]}
        before = copy.deepcopy(document)
        rendered = reader.render_index([document])
        page = Elements(rendered)
        first_link = next(node for node in page.nodes
                          if node["attrs"].get("href") == "chapter-001.html")
        self.assertEqual(first_link["text"], '第一回 <仏> & "猿" 天地')
        self.assertIn('&lt;仏&gt; &amp; &quot;猿&quot;', rendered)
        self.assertEqual(document, before)


class ReadingSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name)
        cls.documents = [load_document(ROOT / "translations" / "wu-chengen" / name) for name in reader.CHAPTERS]
        cls.taii = load_document(ROOT / "translations/tanaka/shinto-taii-ja.yaml")
        cls.pages = reader.build(cls.output)
        cls.html = {name: Elements(text) for name, text in cls.pages.items() if name.endswith(".html")}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_only_explicit_public_files(self):
        self.assertEqual(set(self.pages), {"index.html", "xiyouji/index.html", "tanaka/index.html", "tanaka/shinto-taii.html", "tanaka/kodo-no-shimei-sekai-no-shorai.html", "tanaka/kokoku-dento-no-seishin.html", ".nojekyll", "assets/reading.css", "xiyouji/assets/reading.css", *(f"chapter-{n:03d}.html" for n in range(1, len(reader.CHAPTERS) + 1)), *(f"xiyouji/chapter-{n:03d}.html" for n in range(1, len(reader.CHAPTERS) + 1))})

    def test_chapter_navigation_and_publication_range(self):
        for number in range(1, len(reader.CHAPTERS) + 1):
            with self.subTest(chapter=number):
                page = self.html[f"xiyouji/chapter-{number:03d}.html"]
                previous = [node["attrs"]["href"] for node in page.nodes
                            if node["attrs"].get("rel") == "prev"]
                following = [node["attrs"]["href"] for node in page.nodes
                             if node["attrs"].get("rel") == "next"]
                self.assertEqual(previous, [f"chapter-{number-1:03d}.html"] * 2 if number > 1 else [])
                self.assertEqual(following, [f"chapter-{number+1:03d}.html"] * 2 if number < len(reader.CHAPTERS) else [])
                navigations = [node for node in page.nodes if node["tag"] == "nav"]
                self.assertEqual(len(navigations), 2)
                for navigation in navigations:
                    links = [node for node in page.nodes if any(parent is navigation for parent in node["parents"]) and node["tag"] == "a"]
                    self.assertEqual(links[-1]["text"], "目次に戻る")
                    self.assertEqual(links[-1]["attrs"]["href"], "index.html")
                    self.assertEqual([node["text"] for node in links[:-1]],
                                     (["前の話"] if number > 1 else []) + (["次の話"] if number < len(reader.CHAPTERS) else []))

    def test_every_character_and_newline_is_preserved(self):
        for n, data in enumerate(self.documents, 1):
            page = self.html[f"xiyouji/chapter-{n:03d}.html"]
            ids_in_order = []
            for segment in data["segments"]:
                with self.subTest(chapter=n, segment=segment["id"]):
                    nodes = page.by_id(segment["id"])
                    self.assertEqual(len(nodes), 1)
                    node = nodes[0]
                    ids_in_order.append(page.nodes.index(node))
                    if segment["kind"] == "note_body":
                        self.assertEqual(node["text"], segment["translation_ja"])
                    else:
                        for css, field in (("translation", "translation_ja"),):
                            matches = [child for child in page.nodes if node in child["parents"] and css in child["attrs"].get("class", "").split()]
                            self.assertEqual(len(matches), 1)
                            self.assertEqual(matches[0]["text"], segment[field])
            self.assertEqual(ids_in_order, sorted(ids_in_order))

    def test_ids_unique_and_all_local_links_resolve(self):
        for name, page in self.html.items():
            ids = [n["attrs"]["id"] for n in page.nodes if "id" in n["attrs"]]
            self.assertEqual(len(ids), len(set(ids)), name)
            for node in page.nodes:
                for key in ("href", "src"):
                    if key not in node["attrs"]:
                        continue
                    url = urlsplit(node["attrs"][key])
                    if url.scheme:
                        self.assertIn(url.scheme, ("https", "http"))
                        self.assertEqual(node["tag"], "a", "External resources must never load")
                        continue
                    self.assertFalse(url.path.startswith("/"), "All site links must work under /nihonjinbun/")
                    target = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(url.path))) if url.path else name
                    self.assertIn(target, self.pages, (name, node))
                    if url.fragment:
                        self.assertEqual(len(self.html[target].by_id(unquote(url.fragment))), 1, (name, node))

    def test_all_eighteen_references_and_ten_notes(self):
        data = self.documents[0]
        page = self.html["xiyouji/chapter-001.html"]
        self.assertEqual(len(data["notes"]), 10)
        self.assertEqual(len(data["references"]), 18)
        self.assertTrue(all(n["text"].startswith("訳注 ") for n in page.nodes
                            if n["tag"] == "h3" and n["attrs"].get("id", "").startswith("note-label-")))
        for ref in data["references"]:
            for field, lang in (("translation_span", "ja"),):
                node, = page.by_id(f'{ref["id"]}-{lang}')
                self.assertEqual(node["text"], ref["from"][field]["exact"])
                self.assertEqual(node["attrs"]["href"], "#" + ref["to"]["id"])
                backlinks = [n for n in page.nodes if n["attrs"].get("href") == f'#{ref["id"]}-{lang}']
                self.assertEqual(len(backlinks), 1)

    def test_metadata_caveats_and_attribution_are_present(self):
        for number, data in enumerate(self.documents, 1):
            text = self.html[f"xiyouji/chapter-{number:03d}.html"].nodes[0]["text"]
            self.assertIn(reader.DISCLAIMER, text)
            for contributor in data["metadata"]["contributors"]:
                if "author" in contributor["roles"]:
                    self.assertIn(contributor["name_ja"], text)
            for gap in data["scope"]["known_gaps"]:
                self.assertIn(gap["description_ja"], text)
            for segment in data["segments"]:
                for variant in segment.get("source_variants", []):
                    if variant["kind"] != "corrected":
                        self.assertIn(variant["description_ja"], text)
                        self.assertIn(variant["text"], text)
                for attribution in segment.get("attributions", []):
                    self.assertIn(attribution["evidence_ja"], text)
            self.assertIn(data["metadata"]["translation_rights"]["attribution"], text)
            for source in data["sources"]:
                for rights in (source["work_rights"], source["transcription_rights"]):
                    if rights.get("attribution"):
                        self.assertIn(rights["attribution"], text)

    def test_html_escaping_and_url_safety(self):
        segment = copy.deepcopy(self.documents[1]["segments"][1])
        malicious = '<script>alert("x")</script><img src=x onerror=alert(1)>&'
        segment["translation_ja"] = malicious
        segment["source_text"] = malicious
        result = reader.render_segment(segment, [], {})
        self.assertNotIn("<script>", result)
        self.assertNotIn("<img", result)
        self.assertIn("&lt;script&gt;", result)
        for url in ("javascript:alert(1)", "data:text/html,evil", "//evil.example", "https://name:secret@example.com"):
            with self.assertRaises(ValueError):
                reader.external_link(url, "unsafe")
        self.assertIn("&amp;", reader.external_link("https://example.com/?x=1&y=2", '<unsafe>'))

    def test_span_mismatch_is_not_silently_published(self):
        data = self.documents[0]
        ref = copy.deepcopy(data["references"][0])
        ref["from"]["translation_span"]["exact"] = "wrong"
        segment = next(s for s in data["segments"] if s["id"] == ref["from"]["segment_id"])
        with self.assertRaises(ValueError):
            reader.render_text(segment["translation_ja"], [ref], "translation_span", {ref["to"]["id"]: 1})

    def test_reproducible_and_sources_untouched(self):
        paths = [ROOT / "translations" / "wu-chengen" / name for name in reader.CHAPTERS]
        paths.append(ROOT / "translations/tanaka/shinto-taii-ja.yaml")
        before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
        self.assertEqual(self.pages, reader.build(self.output))
        self.assertEqual(before, [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths])
        for name, content in self.pages.items():
            self.assertEqual((ROOT / "docs" / name).read_text(encoding="utf-8"), content, "Committed docs must be regenerated")

    def test_chapters_contain_only_reading_annotations_and_navigation(self):
        for number, data in enumerate(self.documents, 1):
            page = self.html[f"xiyouji/chapter-{number:03d}.html"]
            main, = page.by_id("main")
            children = [n for n in page.nodes if n["parents"] and n["parents"][-1] is main]
            self.assertEqual([n["tag"] for n in children], ["nav", "article", "section", "nav"])
            self.assertEqual(children[2]["attrs"]["id"], "notes")
            heading, = [n for n in page.nodes if n["tag"] == "h1"]
            expected, = [s for s in data["segments"] if s["kind"] == "heading"]
            self.assertEqual(heading["text"], expected["translation_ja"])
            notes, = page.by_id("notes")
            notes_heading, = [n for n in page.nodes if n["tag"] == "h2"]
            self.assertEqual(notes_heading["text"], "注釈")
            self.assertIn(notes, notes_heading["parents"])
            self.assertFalse(any(n["tag"] in ("script", "noscript", "button", "header", "footer", "details") for n in page.nodes))
            self.assertFalse(any(n["attrs"].get("lang") == "zh-Hant" for n in page.nodes))
            self.assertNotIn("data-mode", page.nodes[0]["attrs"])
            self.assertNotIn("data-size", page.nodes[0]["attrs"])
            self.assertFalse(page.by_id("edition"))
            policy = next(n["attrs"]["content"] for n in page.nodes if n["attrs"].get("http-equiv") == "Content-Security-Policy")
            self.assertIn("connect-src 'none'", policy)
            self.assertNotIn("script-src", policy)
            # No duplicated Chinese references or controls in the public document.
            self.assertFalse(any(n["attrs"].get("id", "").endswith("-zh") for n in page.nodes))

    def test_root_and_author_indexes_are_minimal_and_navigable(self):
        root = self.html["index.html"]
        self.assertEqual([n["text"] for n in root.nodes if n["tag"] == "h1"], ["索引"])
        self.assertEqual([(n["text"], n["attrs"]["href"]) for n in root.nodes if n["tag"] == "a"],
                         [("西遊記", "xiyouji/index.html"), ("田中義能", "tanaka/index.html"),
                          ("リポジトリ", "https://github.com/cacazu/nihonjinbun")])
        author = self.html["tanaka/index.html"]
        self.assertEqual([n["text"] for n in author.nodes if n["tag"] == "h1"], ["田中義能"])
        self.assertEqual([(n["text"], n["attrs"]["href"]) for n in author.nodes if n["tag"] == "a"],
                         [("神道大意", "shinto-taii.html"), ("皇道の使命と世界の将来", "kodo-no-shimei-sekai-no-shorai.html"), ("皇国伝統の精神", "kokoku-dento-no-seishin.html"), ("索引に戻る", "../index.html")])
        for page in (root, author):
            self.assertFalse(any(n["tag"] in ("script", "button", "iframe") for n in page.nodes))

    def test_old_chapter_urls_redirect_to_exact_new_canonical_page(self):
        for number in range(1, len(reader.CHAPTERS) + 1):
            page = self.html[f"chapter-{number:03d}.html"]
            target = f"xiyouji/chapter-{number:03d}.html"
            refresh, = [n for n in page.nodes if n["attrs"].get("http-equiv") == "refresh"]
            self.assertEqual(refresh["attrs"]["content"], "0;url=" + target)
            canonical, = [n for n in page.nodes if n["attrs"].get("rel") == "canonical"]
            self.assertEqual(canonical["attrs"]["href"], target)
            link, = [n for n in page.nodes if n["tag"] == "a"]
            self.assertEqual(link["attrs"]["href"], target)
            self.assertFalse(page.by_id("reading"), "Old paths must not duplicate the book")

    def test_kokoku_full_translation_groups_notes_and_intro_toc(self):
        data = load_document(ROOT / "translations/tanaka/kokoku-dento-no-seishin-ja.yaml")
        page = self.html["tanaka/kokoku-dento-no-seishin.html"]
        self.assertEqual(len(data["segments"]), 85)
        segments = {s["id"]: s for s in data["segments"]}
        for segment in data["segments"]:
            node, = page.by_id(segment["id"])
            self.assertEqual(node["text"], segment["translation_ja"])
        self.assertEqual(len(data["groups"]), 18)
        for group in data["groups"]:
            node, = page.by_id(group["id"])
            self.assertEqual(node["text"], ''.join(segments[m["segment_id"]]["translation_ja"] for m in group["members"]))
        for note in data["notes"]:
            self.assertEqual(len(page.by_id(note["id"])), 1)
        intro = next(s for s in data["segments"] if s["section_id"] == "introduction")
        self.assertTrue(any(n["tag"] == "a" and n["attrs"].get("href") == "#"+intro["id"] and n["text"] == "導入・潜在精神" for n in page.nodes))
        self.assertEqual(sum(n["tag"] == "li" and n["text"].startswith("原文のルビ") for n in page.nodes), 144)

    def test_kodo_full_translation_groups_caveat_and_language_labels(self):
        data = load_document(ROOT / "translations/tanaka/kodo-no-shimei-sekai-no-shorai-ja.yaml")
        page = self.html["tanaka/kodo-no-shimei-sekai-no-shorai.html"]
        self.assertEqual([n["text"] for n in page.nodes if n["tag"] == "h1"], [data["metadata"]["title_ja"]])
        self.assertEqual(len(data["segments"]), 62)
        segments = {s["id"]: s for s in data["segments"]}
        for segment in data["segments"]:
            node, = page.by_id(segment["id"])
            self.assertEqual(node["text"], segment["translation_ja"])
        self.assertEqual(len(data["groups"]), 15)
        for group in data["groups"]:
            node, = page.by_id(group["id"])
            self.assertEqual(node["text"], ''.join(segments[m["segment_id"]]["translation_ja"] for m in group["members"]))
        for gap in data["scope"]["known_gaps"]:
            self.assertIn(gap["description_ja"], page.nodes[0]["text"])
        labels = [n["text"] for n in page.nodes if n["tag"] == "li"]
        self.assertEqual(sum(t.startswith("原文のルビ") for t in labels), 303)
        self.assertEqual(sum(t.startswith("原文の言語") for t in labels), 3)
        self.assertEqual(sum(t.startswith("原文の傍点") for t in labels), 1)

    def test_taii_every_translation_character_and_segment_once(self):
        page = self.html["tanaka/shinto-taii.html"]
        self.assertEqual(len(self.taii["segments"]), 422)
        reading, = page.by_id("reading")
        notes, = page.by_id("notes")
        positions = []
        for segment in self.taii["segments"]:
            node, = page.by_id(segment["id"])
            self.assertEqual(node["text"], segment["translation_ja"], segment["id"])
            if segment["kind"] == "note_body":
                self.assertIn(notes, node["parents"])
            else:
                self.assertIn(reading, node["parents"])
                positions.append(page.nodes.index(node))
        self.assertEqual(positions, sorted(positions))
        self.assertEqual([n["text"] for n in page.nodes if n["tag"] == "h1"], ["神道大意"])

    def test_taii_continued_paragraphs_join_without_added_breaks(self):
        page = self.html["tanaka/shinto-taii.html"]
        segments = {s["id"]: s for s in self.taii["segments"]}
        self.assertEqual(len(self.taii["groups"]), 24)
        for group in self.taii["groups"]:
            node, = page.by_id(group["id"])
            expected = group.get("separator", "").join(segments[m["segment_id"]]["translation_ja"]
                                                       for m in group["members"])
            self.assertEqual(node["text"], expected, group["id"])
            members = [n for n in page.nodes if n["attrs"].get("id") in
                       {m["segment_id"] for m in group["members"]} and node in n["parents"]]
            self.assertEqual([n["attrs"]["id"] for n in members],
                             [m["segment_id"] for m in group["members"]])
            self.assertTrue(all(n["tag"] == "span" for n in members))

    def test_taii_toc_source_annotations_and_note_backlinks(self):
        page = self.html["tanaka/shinto-taii.html"]
        toc, = page.by_id("contents")
        toc_links = [n for n in page.nodes if n["tag"] == "a" and toc in n["parents"]]
        segments = {s["id"]: s for s in self.taii["segments"]}
        expected = []
        for section in self.taii["sections"]:
            if section.get("parent_id") == "main-text":
                sid = section["heading_segment_ids"][0]
                expected.append((segments[sid]["translation_ja"], "#" + sid))
            elif section["id"] in ("colophon", "advertisements"):
                sid = next(s["id"] for s in self.taii["segments"]
                           if s["section_id"] == section["id"] or
                           (section["id"] == "advertisements" and s["section_id"].startswith("ads-scan-")))
                expected.append((section["label_ja"], "#" + sid))
        self.assertEqual([(n["text"], n["attrs"]["href"]) for n in toc_links], expected)
        annotation_nodes = [n for n in page.nodes if n["tag"] == "li" and
                            n["text"].startswith(("原文のルビ", "原文の傍点"))]
        annotations = [(s, a) for s in self.taii["segments"] for a in s.get("annotations", [])]
        self.assertEqual(len(annotations), 26)
        self.assertEqual(len(annotation_nodes), len(annotations))
        for node, (segment, annotation) in zip(annotation_nodes, annotations):
            self.assertIn(annotation["span"]["exact"], node["text"])
            if annotation.get("reading"):
                self.assertIn(annotation["reading"], node["text"])
            link, = [n for n in page.nodes if n["tag"] == "a" and any(parent is node for parent in n["parents"])]
            self.assertEqual(link["attrs"]["href"], "#" + segment["id"])
        for ref in self.taii["references"]:
            node, = page.by_id(ref["id"] + "-ja")
            self.assertEqual(node["text"], ref["from"]["translation_span"]["exact"])
            self.assertEqual(node["attrs"]["href"], "#" + ref["to"]["id"])
            self.assertEqual(len([n for n in page.nodes if n["attrs"].get("href") == "#" + ref["id"] + "-ja"]), 1)

    def test_taii_note_origins_descriptions_and_source_positions(self):
        page = self.html["tanaka/shinto-taii.html"]
        self.assertEqual([n["text"] for n in page.nodes if n["tag"] == "h3" and
                          n["attrs"].get("id", "").startswith("note-label-")],
                         ["書込み（筆者不明） 01", "原注 02", "訳注 03"])
        for note in self.taii["notes"]:
            card, = page.by_id(note["id"])
            self.assertIn(note["description_ja"], card["text"])
            if note["origin"] != "translator":
                marker, = page.by_id("source-note-" + note["id"])
                self.assertTrue(any(n["attrs"].get("id") == "reading" for n in marker["parents"]))
                link, = [n for n in page.nodes if n["tag"] == "a" and marker in n["parents"]]
                self.assertEqual(link["attrs"]["href"], "#" + note["id"])
                self.assertTrue(any(n["attrs"].get("href") == "#source-note-" + note["id"]
                                    for n in page.nodes if card in n["parents"]))

    def test_taii_reader_keeps_caveats_but_not_raw_ocr_history(self):
        text = self.html["tanaka/shinto-taii.html"].nodes[0]["text"]
        for gap in self.taii["scope"]["known_gaps"]:
            self.assertIn(gap["description_ja"], text)
        ocr_descriptions = {v["description_ja"] for s in self.taii["segments"]
                            for v in s.get("source_variants", []) if v["kind"] == "ocr"}
        for description in ocr_descriptions:
            self.assertNotIn(description, text)
        self.assertIn(self.taii["metadata"]["translation_rights"]["attribution"], text)
        self.assertIn(self.taii["metadata"]["translation_rights"]["note_ja"], text)

    def test_taii_invalid_group_order_fails_instead_of_losing_text(self):
        data = copy.deepcopy(self.taii)
        data["groups"][0]["members"].reverse()
        with self.assertRaises(ValueError):
            reader.render_taii(data)

    def test_retired_generated_script_is_removed_on_rebuild(self):
        stale = self.output / "assets" / "reading.js"
        stale.write_text("old controls", encoding="utf-8")
        reader.build(self.output)
        self.assertFalse(stale.exists())


if __name__ == "__main__":
    unittest.main()
