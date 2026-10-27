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
        self.assertEqual(set(self.pages), {"index.html", "xiyouji/index.html", "tanaka/index.html", "tanaka/shinto-taii.html", "tanaka/kodo-no-shimei-sekai-no-shorai.html", "tanaka/kokoku-dento-no-seishin.html", "tanaka/nihon-seishin-kokutai.html", "tanaka/shinto-shi-koyo.html", "tanaka/nihon-shoki-gaisetsu.html", "tanaka/shinto-hongi.html", "tanaka/kokumin-dotoku-yoryo-kogi.html", ".nojekyll", "assets/reading.css", "xiyouji/assets/reading.css", *(f"chapter-{n:03d}.html" for n in range(1, len(reader.CHAPTERS) + 1)), *(f"xiyouji/chapter-{n:03d}.html" for n in range(1, len(reader.CHAPTERS) + 1))})

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
                         [("神道大意", "shinto-taii.html"), ("皇道の使命と世界の将来", "kodo-no-shimei-sekai-no-shorai.html"), ("皇国伝統の精神", "kokoku-dento-no-seishin.html"), ("日本精神と国体の本質", "nihon-seishin-kokutai.html"), ("神道史綱要", "shinto-shi-koyo.html"), ("日本書紀概説", "nihon-shoki-gaisetsu.html"), ("神道本義", "shinto-hongi.html"), ("国民道徳要領講義", "kokumin-dotoku-yoryo-kogi.html"), ("索引に戻る", "../index.html")])
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

    def test_history_full_text_continuation_links_marginal_headings_and_note(self):
        data = load_document(ROOT / "translations/tanaka/shinto-shi-koyo-ja.yaml")
        page = self.html["tanaka/shinto-shi-koyo.html"]
        self.assertEqual(len(data["segments"]), 199)
        segments = {s["id"]: s for s in data["segments"]}
        for segment in data["segments"]:
            node, = page.by_id(segment["id"])
            self.assertEqual(node["text"], segment["translation_ja"])
        self.assertEqual(len(data["groups"]), 20)
        for group in data["groups"]:
            node, = page.by_id(group["id"])
            self.assertEqual(node["text"], ''.join(segments[m["segment_id"]]["translation_ja"] for m in group["members"]))
        refs = [r for r in data["references"] if r["to"]["type"] == "segment"]
        self.assertEqual(len(refs), 13)
        for ref in refs:
            marker, = page.by_id(ref["id"]+"-ja")
            self.assertTrue(any(n["tag"] == "a" and marker in n["parents"] and n["attrs"].get("href") == "#"+ref["to"]["id"] for n in page.nodes))
        for record in data["provenance"]["nonadjacent_continuations"]:
            for sid in record["intervening_segment_ids"]:
                if segments[sid]["kind"] == "heading":
                    node, = page.by_id(sid)
                    self.assertTrue(any(n["tag"] == "aside" and n["attrs"].get("aria-label") == "原典の欄外見出し" for n in node["parents"]))
        note, = data["notes"]
        self.assertEqual(len(page.by_id(note["id"])), 1)
        self.assertEqual(len(page.by_id("source-note-"+note["id"])), 1)
        for gap in data["scope"]["known_gaps"]:
            self.assertIn(gap["description_ja"], page.nodes[0]["text"])

    def test_nihon_full_translation_groups_notes_and_uncertainties(self):
        data = load_document(ROOT / "translations/tanaka/nihon-seishin-kokutai-ja.yaml")
        page = self.html["tanaka/nihon-seishin-kokutai.html"]
        self.assertEqual(len(data["segments"]), 62)
        segments = {s["id"]: s for s in data["segments"]}
        for segment in data["segments"]:
            node, = page.by_id(segment["id"])
            self.assertEqual(node["text"], segment["translation_ja"])
        self.assertEqual(len(data["groups"]), 9)
        for group in data["groups"]:
            node, = page.by_id(group["id"])
            self.assertEqual(node["text"], ''.join(segments[m["segment_id"]]["translation_ja"] for m in group["members"]))
        self.assertEqual(len(data["notes"]), 2)
        for note in data["notes"]:
            self.assertEqual(len(page.by_id(note["id"])), 1)
        self.assertEqual(len(data["scope"]["known_gaps"]), 3)
        for gap in data["scope"]["known_gaps"]:
            self.assertIn(gap["description_ja"], page.nodes[0]["text"])
        self.assertEqual(sum(n["tag"] == "li" and (n["text"].startswith("原文のルビ") or n["text"].startswith("原文の傍点")) for n in page.nodes), 50)

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



class NihonShokiReadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_document(ROOT / "translations/tanaka/nihon-shoki-gaisetsu-ja.yaml")
        cls.rendered = reader.render_taii(cls.data, include_reader_notes=True)
        cls.page = Elements(cls.rendered)
        cls.ids = {}
        for node in cls.page.nodes:
            if node["attrs"].get("id"):
                cls.ids.setdefault(node["attrs"]["id"], []).append(node)

    def test_full_manuscript_and_groups_are_exact(self):
        self.assertEqual(len(self.data["segments"]), 1144)
        by = {s["id"]: s for s in self.data["segments"]}
        for sid, segment in by.items():
            node, = self.ids[sid]
            self.assertEqual(node["text"], segment["translation_ja"])
        self.assertEqual(len(self.data["groups"]), 116)
        for group in self.data["groups"]:
            node, = self.ids[group["id"]]
            self.assertEqual(node["text"], "".join(by[m["segment_id"]]["translation_ja"] for m in group["members"]))

    def test_ids_and_fragment_targets_are_valid(self):
        self.assertTrue(all(len(nodes) == 1 for nodes in self.ids.values()))
        for node in self.page.nodes:
            href = node["attrs"].get("href", "")
            if href.startswith("#"):
                self.assertIn(href[1:], self.ids)
        self.assertFalse(any(n["tag"] in ("script", "iframe", "button") for n in self.page.nodes))

    def test_source_variants_ruby_and_local_reservations_are_visible(self):
        text = self.page.nodes[0]["text"]
        for segment in self.data["segments"]:
            for variant in segment.get("source_variants", []):
                if variant["kind"] not in ("corrected", "ocr"):
                    self.assertIn(variant["text"], text)
            for issue in segment.get("issues", []):
                self.assertIn(issue["message_ja"], text)
            for annotation in segment.get("annotations", []):
                if annotation.get("reading"):
                    self.assertIn(annotation["reading"], text)
        self.assertNotIn("号数の判読は要再確認", text)
        self.assertNotIn("線形転記した途中稿", text)

    def test_toc_prefers_explicit_section_heading(self):
        toc, = self.ids["contents"]
        links = [n for n in self.page.nodes if n["tag"] == "a" and toc in n["parents"]]
        self.assertTrue(any(n["attrs"].get("href") == "#ns-p0012-035" for n in links))
        self.assertFalse(any(n["attrs"].get("href") == "#ns-p0012-032" for n in links))

    def test_inline_source_notes_render_only_the_declared_span(self):
        self.assertEqual(len(self.data["notes"]), 2)
        for note in self.data["notes"]:
            label, = self.ids["note-label-" + note["id"]]
            self.assertIn("原割注（筆者未詳）", label["text"])
            for i, item in enumerate(note["body"], 1):
                body, = self.ids[note["id"] + "-body-" + str(i)]
                self.assertEqual(body["text"], item["translation_span"]["exact"])
                self.assertEqual(len(self.ids[item["segment_id"]]), 1)

    def test_generated_page_is_reproducible(self):
        self.assertEqual(self.rendered, (ROOT / "docs/tanaka/nihon-shoki-gaisetsu.html").read_text())

    def test_previous_tanaka_pages_are_unchanged(self):
        for slug in reader.TANAKA_WORKS:
            if slug == "nihon-shoki-gaisetsu":
                continue
            data = load_document(ROOT / f"translations/tanaka/{slug}-ja.yaml")
            rendered = reader.render_taii(data, include_reader_notes=slug != "shinto-taii")
            self.assertEqual(rendered, (ROOT / f"docs/tanaka/{slug}.html").read_text())


class ShintoHongiReadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_document(ROOT / "translations/tanaka/shinto-hongi-ja.yaml")
        cls.rendered = reader.render_taii(cls.data, include_reader_notes=True)
        cls.page = Elements(cls.rendered)
        cls.ids = {}
        for node in cls.page.nodes:
            if node["attrs"].get("id"):
                cls.ids.setdefault(node["attrs"]["id"], []).append(node)

    def test_all_1030_translations_once_in_manuscript_order(self):
        self.assertEqual(len(self.data["segments"]), 1030)
        segments = {s["id"]: s for s in self.data["segments"]}
        for sid, segment in segments.items():
            with self.subTest(segment=sid):
                node, = self.ids[sid]
                self.assertEqual(node["text"], segment["translation_ja"])
        reading, = self.ids["reading"]
        actual = [n["attrs"]["id"] for n in self.page.nodes
                  if n["attrs"].get("id") in segments and any(parent is reading for parent in n["parents"])]
        self.assertEqual(actual, [s["id"] for s in self.data["segments"] if s["kind"] != "note_body"])
        paragraphs = [g for g in self.data["groups"] if g["kind"] == "paragraph"]
        self.assertEqual(len(paragraphs), 101)
        for group in paragraphs:
            node, = self.ids[group["id"]]
            self.assertEqual(node["text"], "".join(segments[m["segment_id"]]["translation_ja"]
                                                  for m in group["members"]))

    def test_three_branch_diagram_preserves_five_cells(self):
        group, = [g for g in self.data["groups"] if g["kind"] == "table"]
        figure, = self.ids[group["id"]]
        self.assertEqual(figure["tag"], "figure")
        self.assertIn(group["description_ja"], figure["text"])
        cells = [n for n in self.page.nodes if any(parent is figure for parent in n["parents"])
                 and "table_cell" in n["attrs"].get("class", "").split()]
        self.assertEqual([n["attrs"]["id"] for n in cells], [m["segment_id"] for m in group["members"]])
        self.assertEqual(len(cells), 5)
        self.assertIn("三分岐", figure["text"])
        self.assertIn("合流", figure["text"])

    def test_reader_toc_distinguishes_original_index_and_nine_chapters(self):
        toc, = self.ids["contents"]
        links = [n for n in self.page.nodes if n["tag"] == "a" and any(parent is toc for parent in n["parents"])]
        chapters = [s for s in self.data["sections"] if s["kind"] == "chapter"]
        self.assertEqual(len(chapters), 9)
        for chapter in chapters:
            chapter_link, = [n for n in links if n["attrs"]["href"] == "#" + chapter["heading_segment_ids"][0]]
            chapter_item = next(n for n in reversed(chapter_link["parents"]) if n["tag"] == "li")
            for section in self.data["sections"]:
                if section.get("parent_id") == chapter["id"] and section["heading_segment_ids"]:
                    section_link, = [n for n in links if n["attrs"]["href"] == "#" + section["heading_segment_ids"][0]]
                    self.assertTrue(any(parent is chapter_item for parent in section_link["parents"]))
        original, = [n for n in links if n["attrs"]["href"] == "#sh-p0007-005"]
        self.assertEqual(original["text"], "原目次（原刊頁）")
        for target in ("sh-p0120-004", "sh-p0121-001", "sh-p0125-001", "sh-p0129-001"):
            self.assertTrue(any(n["attrs"]["href"] == "#" + target for n in links),
                            "Colophon and all three advertisement groups need navigation")
        source_refs = [r for r in self.data["references"] if r["kind"] == "index"]
        self.assertEqual(len(source_refs), 69)
        for ref in source_refs:
            node, = self.ids[ref["id"] + "-ja"]
            location = ref["to"]["location"]
            self.assertIn(str(location["printed_page"]), node["text"])
            if location.get("printed_page_end"):
                self.assertIn(str(location["printed_page_end"]), node["text"])
            self.assertIn(ref["description_ja"], node["text"])
            self.assertFalse(any(n["tag"] == "a" and any(parent is node for parent in n["parents"]) for n in self.page.nodes),
                             "Printed-page references must not become guessed body links")

    def test_all_annotations_local_caveats_and_reader_notes_are_retained(self):
        text = self.page.nodes[0]["text"]
        annotations = [(s, a) for s in self.data["segments"] for a in s.get("annotations", [])]
        self.assertEqual(len(annotations), 163)
        nodes = [n for n in self.page.nodes if n["tag"] == "li" and
                 n["text"].startswith(("原文のルビ", "原文の傍点", "原文の太字"))]
        self.assertEqual(len(nodes), len(annotations))
        for node, (segment, annotation) in zip(nodes, annotations):
            self.assertIn(annotation["span"]["exact"], node["text"])
            if annotation.get("reading"):
                self.assertIn(annotation["reading"], node["text"])
            link, = [n for n in self.page.nodes if n["tag"] == "a" and any(parent is node for parent in n["parents"])]
            self.assertEqual(link["attrs"]["href"], "#" + segment["id"])
        for segment in self.data["segments"]:
            for issue in segment.get("issues", []):
                self.assertIn(issue["message_ja"], text)
        for gap in self.data["scope"]["known_gaps"]:
            self.assertIn(gap["description_ja"], text)
        for note in self.data["metadata"].get("reader_notes_ja", []):
            self.assertIn(note, text)
        for note in self.data["notes"]:
            card, = self.ids[note["id"]]
            self.assertIn(note["description_ja"], card["text"])
            label, = self.ids["note-label-" + note["id"]]
            self.assertIn("原注", label["text"])
            marker, = self.ids["source-note-" + note["id"]]
            self.assertTrue(any(n["attrs"].get("id") == "reading" for n in marker["parents"]))
            self.assertTrue(any(n["attrs"].get("href") == "#source-note-" + note["id"]
                                for n in self.page.nodes if any(parent is card for parent in n["parents"])))

    def test_ids_links_and_generated_file_are_valid(self):
        self.assertTrue(all(len(nodes) == 1 for nodes in self.ids.values()))
        for node in self.page.nodes:
            href = node["attrs"].get("href", "")
            if href.startswith("#"):
                self.assertIn(href[1:], self.ids)
            elif href and not urlsplit(href).scheme:
                self.assertTrue((ROOT / "docs/tanaka" / href).resolve().is_file())
        self.assertFalse(any(n["tag"] in ("script", "iframe", "button") for n in self.page.nodes))
        self.assertEqual(self.rendered, (ROOT / "docs/tanaka/shinto-hongi.html").read_text())

    def test_bad_group_order_or_shape_fails_closed(self):
        for kind in ("paragraph", "table"):
            data = copy.deepcopy(self.data)
            group = next(g for g in data["groups"] if g["kind"] == kind)
            group["members"].reverse()
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                reader.render_taii(data)
        data = copy.deepcopy(self.data)
        group = next(g for g in data["groups"] if g["kind"] == "table")
        group["members"][2]["column"] = 3
        with self.assertRaises(ValueError):
            reader.render_taii(data)


class KokuminDotokuReadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / "translations/tanaka/kokumin-dotoku-yoryo-kogi-ja.yaml"
        cls.data = load_document(cls.path)
        cls.before = copy.deepcopy(cls.data)
        cls.rendered = reader.render_taii(cls.data, include_reader_notes=True)
        cls.page = Elements(cls.rendered)
        cls.ids = {}
        for node in cls.page.nodes:
            if node["attrs"].get("id"):
                cls.ids.setdefault(node["attrs"]["id"], []).append(node)

    def test_all_1017_translations_once_and_body_order_unchanged(self):
        self.assertEqual(self.data, self.before)
        self.assertEqual(len(self.data["segments"]), 1017)
        segments = {s["id"]: s for s in self.data["segments"]}
        reading, = self.ids["reading"]
        for sid, segment in segments.items():
            with self.subTest(segment=sid):
                node, = self.ids[sid]
                self.assertEqual(node["text"], segment["translation_ja"])
                self.assertEqual(any(parent is reading for parent in node["parents"]),
                                 segment["kind"] != "note_body")
        actual = [n["attrs"]["id"] for n in self.page.nodes
                  if n["attrs"].get("id") in segments and any(parent is reading for parent in n["parents"])]
        self.assertEqual(actual, [s["id"] for s in self.data["segments"] if s["kind"] != "note_body"])

    def test_all_95_page_joins_are_unbroken_including_note_adjacent_join(self):
        self.assertEqual(len(self.data["groups"]), 95)
        segments = {s["id"]: s for s in self.data["segments"]}
        for group in self.data["groups"]:
            with self.subTest(group=group["id"]):
                node, = self.ids[group["id"]]
                self.assertEqual(node["text"], "".join(segments[m["segment_id"]]["translation_ja"]
                                                      for m in group["members"]))
                self.assertFalse(any(n["tag"] in ("p", "br") and any(parent is node for parent in n["parents"])
                                     for n in self.page.nodes))
        group, = self.ids["kdk-continuation-kdk-p0101-005"]
        self.assertIn("我が国運の発展と文明の進歩は、速やかに進み", group["text"])
        group90, = self.ids["kdk-continuation-kdk-p0104-005"]
        self.assertIn("国際道徳を尊重しなければなりません。", group90["text"])

    def test_reader_toc_covers_seventeen_chapters_supplements_and_all_ad_groups(self):
        toc, = self.ids["contents"]
        self.assertTrue(toc["text"].startswith("読書用目次"))
        links = [n for n in self.page.nodes if n["tag"] == "a" and any(parent is toc for parent in n["parents"])]
        chapters = [s for s in self.data["sections"] if s["id"].startswith("kdk-chapter-")]
        self.assertEqual(len(chapters), 17)
        for section in chapters:
            self.assertTrue(any(n["attrs"]["href"] == "#" + section["heading_segment_ids"][0] for n in links))
        original, = [n for n in links if n["attrs"]["href"] == "#kdk-p0011-003"]
        self.assertEqual(original["text"], "原目次（原刊頁）")
        for target in ("kdk-p0101-003", "kdk-p0113-003", "kdk-p0117-005", "kdk-p0118-001",
                       "kdk-p0120-001", "kdk-p0121-001", "kdk-p0123-001", "kdk-p0126-001", "kdk-p0127-001"):
            self.assertTrue(any(n["attrs"]["href"] == "#" + target for n in links), target)

    def test_original_index_and_109_exercises_preserve_printed_pages_without_guessed_links(self):
        exercises = [s for s in self.data["segments"]
                     if s["section_id"].startswith("kdk-exercises-") and s["kind"] == "list_item"]
        self.assertEqual(len(exercises), 109)
        source_refs = [r for r in self.data["references"] if r["to"]["type"] == "source_location"]
        self.assertEqual(sum(r["kind"] == "index" for r in source_refs), 19)
        self.assertEqual(sum(r["kind"] == "cross_reference" for r in source_refs), 124)
        self.assertEqual({r["from"]["segment_id"] for r in source_refs if r["kind"] == "cross_reference"},
                         {s["id"] for s in exercises})
        for ref in source_refs:
            node, = self.ids[ref["id"] + "-ja"]
            label = "原目次の参照先" if ref["kind"] == "index" else "演習の参照先"
            self.assertTrue(node["text"].startswith(label + "：原刊"))
            location = ref["to"]["location"]
            self.assertIn(location["printed_page"], node["text"])
            if location.get("printed_page_end"):
                self.assertIn(location["printed_page_end"], node["text"])
            self.assertIn(ref["description_ja"], node["text"])
            self.assertFalse(any(n["tag"] == "a" and any(parent is node for parent in n["parents"])
                                 for n in self.page.nodes))

    def test_all_13_segment_note_references_have_round_trips_without_invented_word_spans(self):
        refs = [r for r in self.data["references"] if r["to"]["type"] == "note"]
        self.assertEqual(len(refs), 13)
        self.assertEqual(len(self.data["notes"]), 13)
        positions = {id(node): i for i, node in enumerate(self.page.nodes)}
        for ref in refs:
            self.assertNotIn("translation_span", ref["from"])
            link, = self.ids[ref["id"] + "-ja"]
            nid = ref["to"]["id"]
            card, = self.ids[nid]
            source, = self.ids[ref["from"]["segment_id"]]
            self.assertEqual(link["attrs"]["href"], "#" + nid)
            self.assertFalse(any(parent is source for parent in link["parents"]))
            self.assertGreater(positions[id(link)], positions[id(source)])
            self.assertTrue(any(n["attrs"].get("href") == "#" + ref["id"] + "-ja"
                                and any(parent is card for parent in n["parents"]) for n in self.page.nodes))
        label11, = self.ids["note-label-kdk-note-p0072-review002"]
        link11, = self.ids["kdk-ref-p0072-review002-ja"]
        self.assertEqual(label11["text"], "訳注 11")
        self.assertEqual(link11["text"], "訳注 11")

    def test_all_551_original_annotations_and_local_caveats_are_retained(self):
        text = self.page.nodes[0]["text"]
        annotations = [(s, a) for s in self.data["segments"] for a in s.get("annotations", [])]
        self.assertEqual(len(annotations), 551)
        nodes = [n for n in self.page.nodes if n["tag"] == "li" and
                 n["text"].startswith(("原文のルビ", "原文の傍点", "原文の太字"))]
        self.assertEqual(len(nodes), len(annotations))
        for node, (segment, annotation) in zip(nodes, annotations):
            self.assertIn(annotation["span"]["exact"], node["text"])
            if annotation.get("reading"):
                self.assertIn(annotation["reading"], node["text"])
            link, = [n for n in self.page.nodes if n["tag"] == "a" and any(parent is node for parent in n["parents"])]
            self.assertEqual(link["attrs"]["href"], "#" + segment["id"])
        for segment in self.data["segments"]:
            for issue in segment.get("issues", []):
                self.assertIn(issue["message_ja"], text)
        for gap in self.data["scope"]["known_gaps"]:
            self.assertIn(gap["description_ja"], text)
        for note in self.data["metadata"]["reader_notes_ja"]:
            self.assertIn(note, text)

    def test_duplicate_photographs_keep_both_sources_but_one_translation(self):
        duplicates = [s for s in self.data["segments"] if s["id"].startswith("kdk-p0006-")]
        self.assertTrue(duplicates)
        self.assertFalse(any(s["id"].startswith("kdk-p0007-") for s in self.data["segments"]))
        for segment in duplicates:
            self.assertEqual(len(self.ids[segment["id"]]), 1)
            self.assertEqual({loc["url"] for loc in segment["source_locations"]},
                             {"https://dl.ndl.go.jp/pid/957393/1/6", "https://dl.ndl.go.jp/pid/957393/1/7"})
        self.assertIn("第6・7コマは同じ見開きの重複撮影", self.page.nodes[0]["text"])

    def test_ids_links_css_and_generated_file_are_valid(self):
        self.assertTrue(all(len(nodes) == 1 for nodes in self.ids.values()))
        for node in self.page.nodes:
            href = node["attrs"].get("href", "")
            if href.startswith("#"):
                self.assertIn(href[1:], self.ids)
            elif href and not urlsplit(href).scheme:
                self.assertTrue((ROOT / "docs/tanaka" / href).resolve().is_file())
            describedby = node["attrs"].get("aria-describedby")
            if describedby:
                self.assertIn(describedby, self.ids)
        self.assertFalse(any(n["tag"] in ("script", "iframe", "button") for n in self.page.nodes))
        self.assertEqual(self.rendered, (ROOT / "docs/tanaka/kokumin-dotoku-yoryo-kogi.html").read_text())


if __name__ == "__main__":
    unittest.main()
