# 西遊記辞書

正本は [xiyouji.yaml](xiyouji.yaml)。翻訳原稿ではないため `translations/` と `catalog.yaml` には入れない。西遊記全体を通して使う共通の語彙資産であり、回ごとには分けない。収録語は編集中であり、作品全体の全語彙を網羅したとみなさない。各話の初出・掲載箇所・本文の文字位置は辞書に保存しない。

## 形式の選定

[YAML 1.2.2](https://yaml.org/spec/1.2.2/) のうち [JSON互換の型](https://www.rfc-editor.org/info/rfc8259/)だけを使う。既存の翻訳YAML読込・Python検証とそろい、長い日本語の語義・別名・出典を人が読み直しやすいためである。[TEI Lex-0](https://lex-0.org/) は辞書の構造化・交換に適した標準だが、この小規模辞書にはXMLと変換処理の追加負担がある。[JSON Lines](https://jsonlines.org/) は逐次処理に便利だが、長い一項目を一行で編集する運用には向かない。必要になれば変換し、並行する別正本は作らない。

型は [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12/json-schema-core) の [専用schema](../schemas/xiyouji-lexicon.schema.json)、語彙・出典の相互参照は [Python検証器](../scripts/validate_xiyouji_lexicon.py) で検証する。追加のDBやフレームワークは不要。

## 項目

- 最上位は `schema_version: "1.0"`、`dictionary_id: "xiyouji"`、`title_ja`、`sources`、`entries`。
- `sources` は `id, title, url, accessed_at`。日付は引用符付き `YYYY-MM-DD`、URLは参照した公開資料のHTTP(S) URL。書名だけで調査済みとしない。
- `entries` は `id, kind, headword, definition_ja, definition_evidence, forms`。`kind` は `person / place / title / object / concept / term`。人物、地名、称号、物品、概念、難語の全カテゴリで、読みと日本語の意味を必須とする。
- 意味の根拠 `definition_evidence` は `status, source_ids, reason_ja`。読みの根拠も同じ形式で、`reading` に `kana` を加える。`verified` は確認資料ID必須。`estimated` は推定理由必須。確認済みでも `reason_ja` に出典の該当箇所や判断を短く記す。中国語原文に語があるだけでは日本語読みの確認にはならない。
- `forms` は `id, text, relation, reading`。`relation` は `preferred / alias / variant / title / short_form`。見出しと一致する `preferred` を一つ置く。同じ人物の石猿・美猴王・孫悟空などは別entryでなく同じentryの別formとする。称号を別人物として扱わない。
- IDは英数字と `._:-`。source、entryはそれぞれ一意、formは辞書全体で一意。読みは仮名で記す。重複キー、アンカー、エイリアス、明示タグ、独自型を使わない。

## 本文の読み規則との分離

各話の本文に初出の読みと難語説明を付ける作業では、この共通辞書を参照する。初出の位置は各話の正本YAMLの `lexicon.first_occurrences` に保存する（[翻訳仕様8.1](../TRANSLATION_YAML_SPECIFICATION.md#81-共通辞書と原稿ごとの初出)）。初出の判断・記録・検証は本文側の作業であり、辞書には回ID・段落ID・文字範囲・本文表示文字列を入れない。別名の部分一致、説明括弧内の語、注本文、回題を独立した本文初出と取り違えないよう、人が文脈を確認する。

辞書検証器は項目の型、IDの一意性、別表記、読み・意味の確度、出典参照を確認する。語の網羅性・語義の妥当性・資料の裏付けは人が調査して判断する。本文初出の正しさや注参照の文字位置を、この辞書検証器で保証しない。

## 編集・確認

1. ルートREADME → 翻訳スキル → 西遊記README → 対象回とこの辞書の順に確認する。
2. 全本文を読み、対象語・別名・初出を確認し、資料の読みと語義を照合する。未確定は推定と根拠を記す。
3. 原文・固定ID・順序を保って本文へ読みと説明を入れ、その回の `lexicon.first_occurrences` と本文側のすべての注参照spanを更新する。調査した読み・意味・別名・出典は共通辞書へ反映する。独立校訂を実施していなければ完了扱いにしない。
4. 通常の語彙追加・対象回の改訂では次の対象別検証を実行し、差分・対象読書ページ・その回の初出を目視で確認する。生成HTMLを直接編集しない。対象回のパスは作業する回に置き換える。

```sh
python scripts/validate_xiyouji_lexicon.py
python scripts/translation_yaml.py translations/wu-chengen/xiyouji-chapter-001-zh-ja.yaml
python -m unittest discover -s tests -p test_xiyouji_lexicon.py
python -m unittest discover -s tests -p test_lexicon_occurrences.py
python scripts/build_reading_site.py
python -m unittest discover -s tests -p test_reading_site.py
```

本文を変更した場合は、対象原稿の目録ハッシュも更新する。辞書だけの変更では目録・読書HTMLの更新は不要。

共有schema・共通検証器などの変更で他作品への影響が想定される場合は、影響範囲を判断して既存翻訳検証テストや全件検証を追加する。通常の語彙追加のたびに全原稿・全テストを反復実行しない。目録全体を再同期する必要がある場合のみ `python scripts/sync_catalog.py` を使い、無関係な差分がないことを確認する。
