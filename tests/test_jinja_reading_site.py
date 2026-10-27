"""The Jinja Hongi reader preserves the completed manuscript and required image."""
import copy
import hashlib
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from test_reading_site import Elements, ROOT, reader, load_document


class JinjaReadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / "translations/tanaka/jinja-hongi-ja.yaml"
        cls.data = load_document(cls.path)
        cls.original = copy.deepcopy(cls.data)
        cls.rendered = reader.render_taii(cls.data, include_reader_notes=True)
        cls.page = Elements(cls.rendered)
        cls.ids = {}
        for node in cls.page.nodes:
            if node["attrs"].get("id"):
                cls.ids.setdefault(node["attrs"]["id"], []).append(node)
        cls.segments = {s["id"]: s for s in cls.data["segments"]}

    def one(self, identifier):
        node, = self.ids[identifier]
        return node

    def test_exact_completed_manuscript_is_not_mutated(self):
        self.assertEqual(self.data, self.original)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),
                         "e682f541ee459cef243514c36296fad8cb9fb342a7ac87a6b5e69e6e812c787f")
        self.assertEqual(len(self.segments), 1689)
        self.assertEqual(len(self.data["notes"]), 324)
        self.assertEqual(len(self.data["references"]), 543)

    def test_all_1689_translations_fixed_ids_and_body_order_once(self):
        reading = self.one("reading")
        notes = self.one("notes")
        for sid, segment in self.segments.items():
            with self.subTest(segment=sid):
                node = self.one(sid)
                self.assertEqual(node["text"], segment["translation_ja"])
                self.assertIn(notes if segment["kind"] == "note_body" else reading, node["parents"])
        actual = [n["attrs"]["id"] for n in self.page.nodes if n["attrs"].get("id") in self.segments
                  and reading in n["parents"]]
        self.assertEqual(actual, [s["id"] for s in self.data["segments"] if s["kind"] != "note_body"])
        for section in self.data["sections"]:
            self.one(section["id"])
        for group in self.data["groups"]:
            self.one(group["id"])

    def test_all_paragraph_quotation_and_list_groups_preserve_members(self):
        self.assertEqual(Counter(g["kind"] for g in self.data["groups"]),
                         {"paragraph": 134, "table": 14, "quotation": 4, "list": 1})
        for group in self.data["groups"]:
            if group["kind"] == "table":
                continue
            node = self.one(group["id"])
            expected = [m["segment_id"] for m in group["members"]]
            actual = [n["attrs"]["id"] for n in self.page.nodes
                      if n["attrs"].get("id") in expected and node in n["parents"]]
            self.assertEqual(actual, expected)
            self.assertEqual(node["text"], ''.join(self.segments[sid]["translation_ja"] for sid in expected))
            if group["kind"] == "quotation":
                self.assertEqual(node["tag"], "blockquote")
                self.assertEqual(node["attrs"]["aria-label"], group["description_ja"])

    def test_all_14_tables_and_570_sparse_source_cells(self):
        tables = [g for g in self.data["groups"] if g["kind"] == "table"]
        self.assertEqual(sum(len(g["members"]) for g in tables), 570)
        for group in tables:
            table = self.one(group["id"])
            self.assertIn(group["description_ja"], table["text"])
            cells = [n for n in self.page.nodes if n["tag"] == "dd" and table in n["parents"]]
            self.assertEqual([n["attrs"]["id"] for n in cells], [m["segment_id"] for m in group["members"]])
            for member, cell in zip(group["members"], cells):
                coordinate = cell["parents"][-1]
                self.assertEqual(coordinate["attrs"]["data-source-row"], str(member["row"]))
                self.assertEqual(coordinate["attrs"]["data-source-column"], str(member["column"]))
                self.assertEqual(coordinate["attrs"]["data-source-label"], member["label_ja"])
                self.assertIn(member["label_ja"], coordinate["text"])
                self.assertIn(f'source-row-{member["row"]}', coordinate["attrs"]["class"])
                self.assertIn(f'source-column-{member["column"]}', coordinate["attrs"]["class"])
        # Bracketed shared places remain single cells, not duplicated guesses.
        shared = [m for g in tables for m in g["members"] if "共通鎮座地" in m["label_ja"]]
        self.assertGreaterEqual(len(shared), 4)
        for member in shared:
            self.one(member["segment_id"])

    def test_required_figure_placement_dimensions_alt_and_all_ten_texts(self):
        figure, = self.data["figures"]
        asset, = self.data["assets"]
        node = self.one(figure["id"])
        image, = [n for n in self.page.nodes if n["tag"] == "img"]
        self.assertIn(node, image["parents"])
        self.assertEqual(image["attrs"]["src"], "../" + asset["path"])
        self.assertEqual(image["attrs"]["alt"], figure["alt_ja"])
        self.assertEqual((image["attrs"]["width"], image["attrs"]["height"]), ("400", "940"))
        self.assertFalse(any(n["tag"] == "figcaption" and node in n["parents"] for n in self.page.nodes),
                         "A null caption must not become an invented source caption")
        anchor = self.one(figure["placement"]["anchor_id"])
        first_text = self.one(figure["text_segment_ids"][0])
        self.assertLess(self.page.nodes.index(anchor), self.page.nodes.index(node))
        self.assertLess(self.page.nodes.index(node), self.page.nodes.index(first_text))
        self.assertEqual(len(figure["text_segment_ids"]), 10)
        for sid in figure["text_segment_ids"]:
            self.assertEqual(self.segments[sid]["kind"], "figure_text")
            self.assertEqual(self.one(sid)["text"], self.segments[sid]["translation_ja"])
        self.assertEqual(reader.reading_assets(self.data)[asset["path"]], (ROOT / asset["path"]).read_bytes())
        self.assertEqual((ROOT / "docs" / asset["path"]).read_bytes(), (ROOT / asset["path"]).read_bytes())
        self.assertEqual(hashlib.sha256((ROOT / "docs" / asset["path"]).read_bytes()).hexdigest(), asset["sha256"])

    def test_figure_rights_and_locations_are_separate_from_translation(self):
        asset, = self.data["assets"]
        figure, = self.data["figures"]
        node = self.one(asset["id"])
        rights_section = next(p for p in node["parents"] if "figure-rights" in p["attrs"].get("class", ""))
        self.assertIn("現代語訳の利用条件とは別", rights_section["text"])
        for key in ("attribution", "note_ja", "license_id"):
            self.assertIn(asset["rights"][key], node["text"])
        links = [n["attrs"]["href"] for n in self.page.nodes if n["tag"] == "a" and node in n["parents"]]
        self.assertIn(asset["rights"]["license_url"], links)
        self.assertIn(asset["rights"]["evidence_url"], links)
        for loc in asset["source_locations"]:
            self.assertIn(loc["url"], links)
            self.assertIn(loc["printed_page"], node["text"])
        self.assertIn(figure["description_ja"], node["text"])
        text = self.page.nodes[0]["text"]
        all_links = [n["attrs"]["href"] for n in self.page.nodes if n["tag"] == "a"]
        for source in self.data["sources"]:
            for key in ("work_rights", "transcription_rights"):
                self.assertIn(source[key]["note_ja"], text)
                self.assertIn(source[key]["evidence_url"], all_links)
        for item in asset["processing"]:
            self.assertIn(item["description_ja"], node["text"])

    def test_all_543_references_and_backlinks_including_note_to_note(self):
        notes = self.one("notes")
        nested = 0
        for ref in self.data["references"]:
            with self.subTest(reference=ref["id"]):
                node = self.one(ref["id"] + "-ja")
                target = ref["to"]
                if self.segments[ref["from"]["segment_id"]]["kind"] == "note_body":
                    self.assertIn(notes, node["parents"])
                    nested += 1
                if "translation_span" in ref["from"]:
                    self.assertEqual(node["text"], ref["from"]["translation_span"]["exact"])
                if target["type"] in ("note", "segment"):
                    self.assertEqual(node["attrs"]["href"], "#" + target["id"])
                    backlinks = [n for n in self.page.nodes if n["attrs"].get("href") == "#" + ref["id"] + "-ja"]
                    self.assertEqual(len(backlinks), 1)
                else:
                    self.assertNotIn("href", node["attrs"])
                    self.assertIn(target["location"]["printed_page"], node["text"])
                    self.assertIn(ref["description_ja"], node["text"])
                    self.assertFalse(any(n["tag"] == "a" and node in n["parents"] for n in self.page.nodes))
        self.assertEqual(nested, 10)
        for note in self.data["notes"]:
            card = self.one(note["id"])
            self.assertIn(note["description_ja"], card["text"])
            if note["origin"] != "translator":
                marker = self.one("source-note-" + note["id"])
                ref = next(r for r in self.data["references"] if r["to"].get("id") == note["id"])
                expected_parent = self.one("notes") if self.segments[ref["from"]["segment_id"]]["kind"] == "note_body" else self.one("reading")
                self.assertIn(expected_parent, marker["parents"])
                self.assertTrue(any(n["attrs"].get("href") == "#source-note-" + note["id"] and card in n["parents"] for n in self.page.nodes))
        for scan in ("0077", "0175"):
            nid = f"jinja-hongi-p{scan}-note-historical-medical-claim"
            self.assertIn("医療助言", self.one(nid)["text"])
            self.one(nid + "-reference-ja")

    def test_recursive_reader_contents_and_original_page_references_stay_distinct(self):
        toc = self.one("contents")
        links = [n for n in self.page.nodes if n["tag"] == "a" and toc in n["parents"]]
        self.assertEqual(sum(s["kind"] == "chapter" for s in self.data["sections"]), 9)
        for section in self.data["sections"]:
            if section["heading_segment_ids"]:
                sid = section["heading_segment_ids"][0]
                self.assertTrue(any(n["attrs"]["href"] == "#" + sid for n in links), section["id"])
        self.assertTrue(any(n["text"] == "原目次（原刊頁）" for n in links))
        index = [r for r in self.data["references"] if r["kind"] == "index"]
        self.assertEqual(len(index), 55)
        for ref in index:
            self.assertNotIn("href", self.one(ref["id"] + "-ja")["attrs"])

    def test_all_annotations_caveats_metadata_and_duplicate_scan_sources(self):
        text = self.page.nodes[0]["text"]
        annotations = [(s, a) for s in self.data["segments"] for a in s.get("annotations", [])]
        nodes = [n for n in self.page.nodes if n["tag"] == "li" and n["text"].startswith(("原文のルビ", "原文の傍点", "原文の太字", "原文の言語"))]
        self.assertEqual(len(annotations), 542)
        self.assertEqual(len(nodes), len(annotations))
        for node, (segment, annotation) in zip(nodes, annotations):
            self.assertIn(annotation["span"]["exact"], node["text"])
            if annotation.get("reading"):
                self.assertIn(annotation["reading"], node["text"])
        for segment in self.data["segments"]:
            for issue in segment.get("issues", []):
                self.assertIn(issue["message_ja"], text)
        self.assertEqual(len(self.data["scope"]["known_gaps"]), 13)
        for gap in self.data["scope"]["known_gaps"]:
            self.assertIn(gap["description_ja"], text)
        for note in self.data["metadata"].get("reader_notes_ja", []):
            self.assertIn(note, text)
        links = [n["attrs"].get("href") for n in self.page.nodes if n["tag"] == "a"]
        for scan in (190, 191):
            self.assertIn(f"https://dl.ndl.go.jp/pid/1020642/1/{scan}", links)
        self.assertFalse(any(sid.startswith("jinja-hongi-p0191-") for sid in self.segments))
        for scan in range(192, 203):
            self.assertTrue(any(sid.startswith(f"jinja-hongi-p{scan:04}-") for sid in self.segments), scan)

        for source in self.data["sources"]:
            for record in source.get("page_inventory", []):
                if not record.get("segment_ids"):
                    self.assertIn(record["description_ja"], text)
                    self.assertIn(record["location"]["url"], links)

    def test_attribution_names_resolve_contributors_without_inventing_unknown_speakers(self):
        contributors = {c["id"]: c["name_ja"] for c in self.data["metadata"]["contributors"]}
        caveats = [n for n in self.page.nodes if n["tag"] == "ul" and n["attrs"].get("class") == "caveats"]
        caveat, = caveats
        items = [n for n in self.page.nodes if n["tag"] == "li" and caveat in n["parents"]]
        by_target = {}
        for link in self.page.nodes:
            if link["tag"] != "a" or not link["attrs"].get("href", "").startswith("#"):
                continue
            for parent in reversed(link["parents"]):
                if parent["tag"] == "li" and caveat in parent["parents"]:
                    by_target.setdefault(link["attrs"]["href"][1:], []).append(parent)
                    break
        expected_unknown = 0
        for segment in self.data["segments"]:
            for item in segment.get("attributions", []):
                expected = item.get("name_ja") or contributors.get(item.get("contributor_id"))
                if not expected:
                    expected = {"author": "著者", "translator": "訳者", "editor": "編集者",
                                "quoted_person": "引用者（氏名未記載）", "unknown": "話者不明"}[item["voice"]]
                if expected == "話者不明":
                    expected_unknown += 1
                matches = [n for n in by_target.get(segment["id"], []) if n["text"].startswith(expected)]
                self.assertTrue(matches, (segment["id"], expected))
        self.assertEqual(sum(n["text"].startswith("話者不明") for n in items), expected_unknown)

    def test_ids_links_csp_resources_escaping_and_reproducibility(self):
        self.assertTrue(all(len(nodes) == 1 for nodes in self.ids.values()))
        policy, = [n["attrs"]["content"] for n in self.page.nodes if n["attrs"].get("http-equiv") == "Content-Security-Policy"]
        self.assertEqual(policy, "default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'; connect-src 'none'")
        for node in self.page.nodes:
            self.assertNotIn(node["tag"], ("script", "iframe", "object", "embed", "style"))
            self.assertNotIn("style", node["attrs"])
            self.assertFalse(any(a.startswith("on") for a in node["attrs"]))
            for key in ("href", "src"):
                url = node["attrs"].get(key, "")
                if url.startswith("#"):
                    self.one(url[1:])
                elif url and not urlsplit(url).scheme:
                    self.assertFalse(url.startswith("/"))
                    self.assertTrue((ROOT / "docs/tanaka" / url).resolve().is_file())
                elif url:
                    self.assertEqual(node["tag"], "a", "No external resources may load")
            if node["attrs"].get("aria-describedby"):
                self.one(node["attrs"]["aria-describedby"])
        self.assertEqual(self.rendered, (ROOT / "docs/tanaka/jinja-hongi.html").read_text())
        self.assertNotRegex(self.page.nodes[0]["text"], r"(?i)(?:writer|reviewer)\d+[/\\]|(?<![A-Za-z])root(?![A-Za-z])|/(?:tmp|workspace)/|[A-Za-z0-9_./-]+\.(?:png|jpe?g|log)(?![A-Za-z0-9_])")

    def test_malformed_groups_references_and_figure_placement_fail_closed(self):
        mutations = [
            lambda d: d["groups"][0]["members"].reverse(),
            lambda d: d["figures"][0]["placement"].update(anchor_type="section"),
            lambda d: d["figures"][0]["placement"].update(anchor_id="jinja-hongi-p0062-004"),
            lambda d: d["figures"][0]["text_segment_ids"].append("missing-segment"),
            lambda d: next(r for r in d["references"] if "translation_span" in r["from"])["from"]["translation_span"].update(exact="wrong"),
            lambda d: d["notes"][0]["body"].append(d["notes"][0]["body"][0]),
            lambda d: next(g for g in d["groups"] if g["kind"] == "table")["members"][0].update(row=4),
        ]
        for mutate in mutations:
            data = copy.deepcopy(self.data)
            mutate(data)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                reader.render_taii(data)

    def test_asset_allowlist_bytes_dimensions_missing_files_and_symlinks(self):
        asset = self.data["assets"][0]
        for key, bad_values in {
            "path": ["/tmp/secret.png", "../secret.png", "assets/tanaka-jinja-hongi-1926/../../secret.png", "https://example.com/evil.png", "data:image/png;base64,eA==", "assets/tanaka-jinja-hongi-1926/other.png"],
            "sha256": ["0" * 64], "bytes": [1], "width": [1], "height": [1],
            "media_type": ["image/svg+xml"], "status": ["planned"],
        }.items():
            for bad in bad_values:
                data = copy.deepcopy(self.data)
                data["assets"][0][key] = bad
                with self.subTest(key=key, value=bad), self.assertRaises(ValueError):
                    reader.reading_assets(data)
        data = copy.deepcopy(self.data)
        data["figures"][0]["alt_ja"] = None
        with self.assertRaises(ValueError):
            reader.reading_assets(data)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = root / asset["path"]
            local.parent.mkdir(parents=True)
            with patch.object(reader, "ROOT", root), self.assertRaises(FileNotFoundError):
                reader.reading_assets(self.data)
            local.symlink_to(ROOT / asset["path"])
            with patch.object(reader, "ROOT", root), self.assertRaisesRegex(ValueError, "symlink"):
                reader.reading_assets(self.data)
            local.unlink()
            content = bytearray((ROOT / asset["path"]).read_bytes())
            content[-1] ^= 1
            local.write_bytes(content)
            with patch.object(reader, "ROOT", root), self.assertRaisesRegex(ValueError, "SHA-256"):
                reader.reading_assets(self.data)

    def test_matrix_scroll_starts_with_the_rightmost_source_column(self):
        css = (ROOT / "scripts/reading_site.css").read_text()
        scroll = css.split(".source-table-scroll{", 1)[1].split("}", 1)[0]
        grid = css.split(".source-table-grid{", 1)[1].split("}", 1)[0]
        cell = css.split(".source-table-cell{", 1)[1].split("}", 1)[0]
        self.assertIn("direction:rtl", scroll)
        self.assertIn("direction:rtl", grid)
        self.assertIn("direction:ltr", cell)
        self.assertIn("overflow-x:auto", scroll)
        self.assertIn("max-width:100%", scroll)
        image = css.split(".source-figure img{", 1)[1].split("}", 1)[0]
        self.assertIn("max-width:100%", image)
        self.assertIn("height:auto", image)

    def test_output_symlinks_cannot_escape_publication_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output, outside = root / "docs", root / "outside"
            output.mkdir()
            outside.mkdir()
            sentinel = outside / "reading.css"
            sentinel.write_text("untouched")
            (output / "assets").symlink_to(outside, target_is_directory=True)
            with patch.object(reader, "CHAPTERS", ()), patch.object(reader, "TANAKA_WORKS", ()), self.assertRaisesRegex(ValueError, "escapes"):
                reader.build(output)
            self.assertEqual(sentinel.read_text(), "untouched")
            self.assertEqual(list(outside.iterdir()), [sentinel])

    def test_markup_in_source_text_and_figure_metadata_is_escaped(self):
        data = copy.deepcopy(self.data)
        payload = '<img src=x onerror="bad()"> & <script>bad()</script>'
        data["segments"][0]["translation_ja"] = payload
        data["figures"][0]["alt_ja"] = payload
        data["figures"][0]["caption_ja"] = payload
        rendered = reader.render_taii(data)
        page = Elements(rendered)
        self.assertEqual(sum(n["tag"] == "img" for n in page.nodes), 1)
        self.assertFalse(any(n["tag"] == "script" or "onerror" in n["attrs"] for n in page.nodes))
        self.assertEqual(next(n for n in page.nodes if n["tag"] == "img")["attrs"]["alt"], payload)
        self.assertIn('&lt;script&gt;', rendered)


if __name__ == "__main__":
    unittest.main()
