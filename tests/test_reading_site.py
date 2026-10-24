"""The reader must faithfully publish only the five explicitly selected chapters."""
import copy
import hashlib
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


class ReadingSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name)
        cls.documents = [load_document(ROOT / "translations" / "wu-chengen" / name) for name in reader.CHAPTERS]
        cls.pages = reader.build(cls.output)
        cls.html = {name: Elements(text) for name, text in cls.pages.items() if name.endswith(".html")}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_only_explicit_public_files(self):
        self.assertEqual(set(self.pages), {"index.html", ".nojekyll", "assets/reading.css", *(f"chapter-{n:03d}.html" for n in range(1, 8))})

    def test_index_contains_only_contents_and_repository(self):
        page = self.html["index.html"]
        body, = [node for node in page.nodes if node["tag"] == "body"]
        self.assertEqual(
            body["text"].split(),
            ["目次", "第一回第二回第三回第四回第五回第六回第七回", "https://github.com/cacazu/nihonjinbun"],
        )
        links = [(node["text"], node["attrs"]["href"])
                 for node in page.nodes if node["tag"] == "a"]
        self.assertEqual(links, [
            *((f"第{numeral}回", f"chapter-{number:03d}.html")
              for number, numeral in enumerate(reader.NUMERALS, 1)),
            ("https://github.com/cacazu/nihonjinbun", "https://github.com/cacazu/nihonjinbun"),
        ])
        self.assertFalse(any(node["tag"] in ("header", "footer", "script", "button")
                             for node in page.nodes))
        heading, = page.by_id("chapters")
        self.assertEqual((heading["tag"], heading["text"]), ("h1", "目次"))

    def test_chapter_navigation_and_publication_range(self):
        for number in range(1, 8):
            with self.subTest(chapter=number):
                page = self.html[f"chapter-{number:03d}.html"]
                previous = [node["attrs"]["href"] for node in page.nodes
                            if node["attrs"].get("rel") == "prev"]
                following = [node["attrs"]["href"] for node in page.nodes
                             if node["attrs"].get("rel") == "next"]
                self.assertEqual(previous, [f"chapter-{number-1:03d}.html"] * 2 if number > 1 else [])
                self.assertEqual(following, [f"chapter-{number+1:03d}.html"] * 2 if number < 7 else [])
                navigations = [node for node in page.nodes if node["tag"] == "nav"]
                self.assertEqual(len(navigations), 2)
                for navigation in navigations:
                    links = [node for node in page.nodes if any(parent is navigation for parent in node["parents"]) and node["tag"] == "a"]
                    self.assertEqual(links[-1]["text"], "目次に戻る")
                    self.assertEqual(links[-1]["attrs"]["href"], "index.html")
                    self.assertEqual([node["text"] for node in links[:-1]],
                                     (["前の話"] if number > 1 else []) + (["次の話"] if number < 7 else []))

    def test_every_character_and_newline_is_preserved(self):
        for n, data in enumerate(self.documents, 1):
            page = self.html[f"chapter-{n:03d}.html"]
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
                    target = url.path or name
                    self.assertIn(target, self.pages, (name, node))
                    if url.fragment:
                        self.assertEqual(len(self.html[target].by_id(unquote(url.fragment))), 1, (name, node))

    def test_all_eighteen_references_and_ten_notes(self):
        data = self.documents[0]
        page = self.html["chapter-001.html"]
        self.assertEqual(len(data["notes"]), 10)
        self.assertEqual(len(data["references"]), 18)
        for ref in data["references"]:
            for field, lang in (("translation_span", "ja"),):
                node, = page.by_id(f'{ref["id"]}-{lang}')
                self.assertEqual(node["text"], ref["from"][field]["exact"])
                self.assertEqual(node["attrs"]["href"], "#" + ref["to"]["id"])
                backlinks = [n for n in page.nodes if n["attrs"].get("href") == f'#{ref["id"]}-{lang}']
                self.assertEqual(len(backlinks), 1)

    def test_metadata_caveats_and_attribution_are_present(self):
        for number, data in enumerate(self.documents, 1):
            text = self.html[f"chapter-{number:03d}.html"].nodes[0]["text"]
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
        before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
        self.assertEqual(self.pages, reader.build(self.output))
        self.assertEqual(before, [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths])
        for name, content in self.pages.items():
            self.assertEqual((ROOT / "docs" / name).read_text(encoding="utf-8"), content, "Committed docs must be regenerated")

    def test_chapters_contain_only_reading_annotations_and_navigation(self):
        for number, data in enumerate(self.documents, 1):
            page = self.html[f"chapter-{number:03d}.html"]
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

    def test_retired_generated_script_is_removed_on_rebuild(self):
        stale = self.output / "assets" / "reading.js"
        stale.write_text("old controls", encoding="utf-8")
        reader.build(self.output)
        self.assertFalse(stale.exists())


if __name__ == "__main__":
    unittest.main()
