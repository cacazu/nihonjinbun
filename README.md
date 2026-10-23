# nihonjinbun

原文と日本語訳を対訳YAMLで管理する翻訳リポジトリ。

## 翻訳を始める前に

翻訳の新規作成・改訂・レビューでは、必ず次の順序で読む。

1. **このルート README.md**：作業対象と共通の入口を確認する。
2. **[翻訳スキル](.agents/skills/translation-dialogue/SKILL.md)**：人物の口調設計、発言者表記、翻訳・検証の手順を読む。
3. **各作品フォルダの README.md**：登場人物の口調の特徴・例文・場面別の使い分けを確認する。西遊記は [translations/wu-chengen/README.md](translations/wu-chengen/README.md)。未作成なら、スキルに従い原文を調べて作成してから訳す。
4. **翻訳作業**：作品の口調ガイドを参考に、原文の意味・人物関係・場面を保って訳す。レビューで見つかった再発し得る問題はスキルへ、作品固有の判断は作品 README へ反映する。

会話が続く箇所では、各セリフの前に発言者を明記する。口調ガイドは意味の改変や創作の許可ではなく、訳文の一貫性を保つための基準である。

本文の形式・原文対応・レビュー状態・ハッシュ等は [翻訳YAML仕様](TRANSLATION_YAML_SPECIFICATION.md) に従う。既存の原文・固定ID・無関係な変更を保護し、検証結果を確認してからコミット・プッシュする。

## 西遊記の読書サイト

第一回〜第五回の正本YAMLから、PC・スマートフォン向けの静的読書サイトを `docs/` に生成する。トップページは目次とリポジトリURLのみ。各話はタイトル・日本語本文・注釈と、上部・下部の「前の話・次の話・目次に戻る」リンクのみを表示する。訳注、解釈の留保、必要な出典・帰属・利用条件は注釈欄にまとめる。原文を含む正本YAMLは変更しない。

```sh
python -m pip install -r requirements.txt
python scripts/build_reading_site.py
python -m unittest discover -s tests
python -m http.server 8000 --directory docs
```

`http://localhost:8000/` で確認できる。`docs/` は GitHub Pages の公開用ディレクトリで、生成したHTML・ローカルCSSと `.nojekyll` のみを含む。第一回〜第五回以外の原稿や作業スキルはコピーしない。すべてのサイト内リンクは相対パスなので、`/nihonjinbun/` のようなサブパスでも動作する。Pagesの公開設定・デプロイは別途行う。

生成器は `scripts/build_reading_site.py`、表示用の正本は `scripts/reading_site.css`。生成物を直接編集せず、正本から再生成してコミットする。ビルドは入力YAMLを既存の検証器で検証し、本文・改行・訳注の欠落や参照範囲の不一致があれば失敗する。JavaScriptや設定保存、アクセス解析、外部フォントは使用しない。原稿のレビュー状態を完了に引き上げるものではない。

読書サイトだけの検証は `python -m unittest discover -s tests -p test_reading_site.py` で実行できる。旧表示切替用の `scripts/reading_site.js` とその単体テストは公開サイトでは使用しない。実ブラウザの表示検証は、この単体テストとは別に行う。
