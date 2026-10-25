# 組立引継ぎ

- 完成候補 `assembled-candidate.yaml`、構造検証 `assembly-validation.json`。
- 199対訳、原注記114件、全45コマ、原注1件。承認済み原文・訳文・順序・固定ID・注記・Issuesを保持。
- 構造訂正のみ：序の見出し・開始段落 `ssk-p0004-001` / `002` を `front-matter` から `preface` に変更。後続序と同節の段落継続にした。
- 改頁継続33組のうち20組は隣接paragraph groups。13組は欄外見出し（1組は割注も）が挟まるため、同じ配列のままtranslator-origin cross_reference＋provenance.nonadjacent_continuationsに保存。見出しを消したり原文を連結変形していない。
- HTML公開には13 cross_referenceの表示が必要。生成器は現状noteのみ対応なので、まだこの原稿を登録しない。本文継続リンク＋欄外見出しの視覚的区別を追加し、原注を含め全文字exact onceと順序を検証する。
- reference.fromには原刊の印刷記号を捏造しないためspanを付けていない。HTML側は本文末尾などに明示的な訳者の継続案内リンクを設置できる。
- 12件のknown_gapsは原刊疑義と微小な訓点の未確読を明示。公開YAML・HTMLとも保持。
- 独立校閲は全原画像・全対訳の検査と注記重点照合。114注記を各字すべて独立再検査したとは記載しない。
- workflow reviewing のまま。統合担当が素材パックと最上位情報を確認後に各単位reviewed/partialとfull_review/content_sha256を確定する。
- 正本・Git・公開HTMLは一切変更していない。
