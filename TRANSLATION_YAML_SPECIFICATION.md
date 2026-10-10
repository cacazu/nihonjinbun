# nihonjinbun 翻訳YAML仕様 2.0

翻訳原稿の本文、原文対応、章階層、注、図、出典、利用条件を共通構造で記録する。`schemas/translation-2.0.schema.json` で型を、`scripts/translation_yaml.py` で参照・文字範囲・画像・進捗の意味を検証する。

## 1. ファイルと基本型

- 一作品の原稿は一つのYAML文書。UTF-8、LF、インデント2空白を使用する。原稿の分割管理は2.0の対象にしない。
- [YAML 1.2.2](https://yaml.org/spec/1.2.2/) のJSON互換のデータ型だけを使用する。キーは文字列。重複キー、独自タグ、複数文書、アンカー・エイリアス、マージキーを認めない。順序は配列で表し、マッピングのキー順に意味を持たせない。
- バージョン、日付、原刊頁、注番号、識別子は引用符付きの文字列。原刊頁の `iv`、`29r`、`143–44` を整数に変換しない。PDF頁と文字位置は整数。
- 本文はプレーンテキスト。段落単位の文字列と原著の改行を保持する。HTMLやMarkdownを本文の構造の代わりに使用しない。
- 本文のブロック文字列は原則 `|-`。末尾改行が原文・訳文の値に含まれる場合は、それを保持するブロック形式を使う。移行で文字列の改行、空白、Unicode正規化を勝手に変更しない。
- 言語は [BCP 47](https://www.rfc-editor.org/rfc/rfc5646.html) の言語タグ。例は `ja`、`en`、`la`、`grc`、`he-Latn`。未確定は `und`。
- 出典・人物・利用条件へのURLは `http` または `https`。同梱ファイルの参照はURLと別の相対パス項目へ記録する。
- 配列が空なら `[]`。省略可能な配列の省略も空配列として扱う。配列を文字列や `null` で代用しない。
- `null` は本仕様で認めた未確認値・未訳値に限る。「なし」「未確認」「対象外」は互いに区別する。読者向けの説明は日本語の説明項目へ記録する。
- 本仕様で定義していない処理用項目を追加しない。拡張が必要な場合は共通仕様とスキーマを更新する。

## 2. 最上位項目

| 項目 | 型 | 必須 | 内容 |
|---|---|---|---|
| `schema_version` | string | 必須 | `"2.0"` |
| `work_id` | string | 必須 | 作品の固定識別子。既存値を維持 |
| `metadata` | object | 必須 | 書名、人物、原著言語、日本語訳の利用条件 |
| `sources` | Source[] | 必須 | 使用した版・翻刻・画像・照合資料。一件以上 |
| `scope` | Scope | 必須 | 翻訳対象、対象外、既知の欠落 |
| `sections` | Section[] | 必須 | 章・部・節・フォリオの階層。一件以上 |
| `segments` | Segment[] | 必須 | 全文の対訳単位。本文・見出し・注本文など |
| `workflow` | Workflow | 必須 | 逐次翻訳と全文見直しの実際の状態 |
| `notes` | Note[] | 任意 | 注の定義。注本文は段落IDへ参照 |
| `references` | Reference[] | 任意 | 本文から注・本文・図・原刊頁への参照 |
| `groups` | Group[] | 任意 | 引用、詩、並列本文、表などのまとまり |
| `assets` | Asset[] | 任意 | 同梱画像のファイル、ハッシュ、出典、加工 |
| `figures` | Figure[] | 任意 | 図の説明と配置、対応する画像・図中文字 |
| `aliases` | Alias[] | 任意 | 既に統合された旧IDなどの明示的な移動先 |
| `terminology` | Term[] | 任意 | 用語、人名、呼称の統一に必要な対応 |
| `provenance` | object | 任意 | 元原稿の固定版・照合資料・移行の由来 |

IDは `^[A-Za-z0-9][A-Za-z0-9._:-]*$` に一致する文字列とする。各配列の `id` はその配列内で一意。同じ文字列を別種別で使用した場合は、種別とIDの組で識別する。IDを配列位置・章番号・訳文から再生成しない。

`segments` の配列順を確定原稿の読書順とする。原典の物理的な位置・順番は `source_locations` と `source_alignment` に保持する。`order`、`reader_order`、`render_blocks` を別の順序の正本として並行管理しない。図の挿入位置は `figures` の明示的な配置情報で表す。

## 3. 書誌、出典、範囲

### 3.1 Metadata

必須は `title_ja: string`、`title_original: string|null`、`original_languages: string[]`、`target_language: "ja"`、`contributors: Contributor[]`、`translation_rights: Rights`。日本語書名は空文字にしない。

任意は `subtitle_ja: string`、`genres: string[]`、`reader_notes_ja: string[]`、`cover_asset_id: string`。原著の書名と翻訳底本の書名は区別し、底本名はSourceへ記録する。

Contributorの必須項目は `id: string`、`name_ja: string|null`、`name_original: string|null`、`roles: string[]`。役割は `author`、`contributor`、`editor`、`source_translator`、`translator`、`illustrator`。任意は `url: string`。不明な人物は名前を推測せず `null` とする。寄稿者を単著者として置き換えない。

### 3.2 Source

必須は `id: string`、`role: primary|intermediary|comparison`、`title: string|null`、`languages: string[]`、`url: string|null`、`edition: string|null`、`work_rights: Rights`、`transcription_rights: Rights`。

任意は `contributor_ids: string[]`、`derived_from_source_id: string`、`local_path: string`、`sha256: string`、`description_ja: string`、`page_inventory: PageRecord[]`。重訳の経路は `derived_from_source_id` で元の版へ結び付ける。循環参照を認めない。電子翻刻と原著の利用条件を混同しない。

Rightsの必須項目は `status: public_domain|licensed|unknown`。任意は `license_id: string`、`license_url: string`、`evidence_url: string`、`attribution: string`、`jurisdiction: string`、`note_ja: string`。`licensed` には `license_id` または `license_url` が必要。確認範囲が限定される場合は範囲を記す。原典がパブリックドメインでも、日本語訳の利用条件を自動的に引き継がない。

PageRecordは `location: Location`、`role: string` が必須。任意は `description_ja: string`、`segment_ids: string[]`、`figure_ids: string[]`。白紙・前付・図版・対象外頁の位置と役割を保持する。roleは原典の頁区分を保持する文字列。本文や図を含まない頁も記録できる。

### 3.3 Scope

必須は `included: ScopeItem[]`、`excluded: ScopeItem[]`、`known_gaps: Gap[]`。

ScopeItemは `source_id: string`、`description_ja: string` が必須。任意は `section_ids: string[]`、`segment_ids: string[]`、`source_ranges: SourceRange[]`。SourceRangeの必須は `segment_id: string`、`span: Span`。原文の一部分だけを対象外にする際に使う。段落全体を未訳・対象外にしない。section_idsは指定した節へ直接所属する段落だけに適用し、子孫へ自動適用しない。子孫を含める場合は対象の節または段落を列挙する。Gapは `description_ja: string` が必須。任意は `source_id: string`、`segment_ids: string[]`、`reference_ids: string[]`、`figure_ids: string[]`。所蔵資料の欠落、原典の判読不能、翻訳途中、意図した対象外を説明で区別する。

書誌の収録範囲は原稿の実際の内容と一致させる。原著の欠落や対象外を、訳抜けとして推測補完しない。

## 4. 章と対訳単位

### 4.1 Section

必須は `id: string`、`parent_id: string|null`、`kind: part|chapter|section|folio|editorial_group`、`heading_segment_ids: string[]`。

任意は `label_ja: string`、`origin: source|editorial`、`source_locations: Location[]`。空白や画像だけのフォリオの位置も保持する。配列は階層の先行順で並べ、親は子より前に置く。親参照は既存のSectionに限り、循環を認めない。

原著の見出しはSegmentに保存し、`heading_segment_ids` で結ぶ。書名や見出しの訳文をSectionへ複製しない。原著にない整理用の節には `origin: editorial` と `label_ja` を付け、原著の見出しとして扱わない。見出しがない本でも本文全体に整理用のSectionを一件作れる。

### 4.2 Segment

| 項目 | 型 | 必須 | 規則 |
|---|---|---|---|
| `id` | string | 必須 | 固定ID。原稿の改訂で再採番しない |
| `section_id` | string | 必須 | 所属SectionのID |
| `kind` | enum | 必須 | `heading`、`paragraph`、`verse`、`list_item`、`table_cell`、`index_entry`、`note_body`、`figure_text`、`separator`、`unclassified` |
| `origin` | enum | 必須 | `source` または `translator` |
| `source_text` | string|null | 必須 | 翻訳した原文。原文がない訳注などは `null` |
| `source_languages` | string[] | 必須 | この単位に含まれる原文言語。訳者の新規文は空配列 |
| `source_locations` | Location[] | 必須 | この原文を確認する位置。訳者の新規文は空配列可 |
| `translation_ja` | string|null | 必須 | 日本語訳。未訳は `null` |
| `translation_status` | enum | 必須 | `pending`、`draft`、`reviewed`、`partial` |
| `translation_required` | boolean | 任意 | 省略はtrue。原稿に保持する翻訳対象外の原注などだけfalse |
| `source_alignment` | Alignment[] | 任意 | 複数の原文単位とこの訳文の対応 |
| `source_kind` | string | 任意 | 原稿にあった原文種別。marginalia、aphorismなどの区別を保持 |
| `source_variants` | Variant[] | 任意 | OCR原形、別版、補訂前などの原文の異同 |
| `attributions` | Attribution[] | 任意 | 著者・編者・引用者などの声の違い |
| `annotations` | Annotation[] | 任意 | 強調、ルビ、詩の字下げなどの文字構造 |
| `issues` | Issue[] | 任意 | 判読・翻訳・対応の留保 |

`pending` では `translation_ja: null`。それ以外の訳文は非空文字列。ただし文字のない原著区切りを保存する `separator` は空文字列を認める。`partial` はIssueで不足箇所を説明する。`unclassified` は作業中の構造に限り、確定版には残さない。

`origin: source` は原文言語と原典位置を持つ。`source_text: null` は未翻刻・欠損・判読不能をIssueで明示した場合に限る。`origin: translator` は `source_text: null` とし、原著の文を推測で与えない。

翻訳対象外の原文を比較・来歴のために原稿へ保持する場合は、`translation_required: false`、`translation_ja: null`、`translation_status: pending` とし、Scope.excludedの `segment_ids` または `section_ids` でその単位を特定する。includedとexcludedの対象を重複させない。falseは原著本文の訳抜けを隠すために使用しない。

### 4.3 共通の位置と補助情報

**Location**: 必須は `source_id: string` と `precision: work|page|block|line|region|unknown`。任意は `printed_page: string`、`printed_page_end: string`、`pdf_page: integer>=1`、`pdf_page_end: integer>=1`、`url: string`、`anchor: string`、`xpath: string`、`line_start: integer>=1`、`line_end: integer>=1`、`source_sequence: integer>=0`、`asset_id: string`、`crop: object`。位置は指定の精度に応じた情報を持ち、数値範囲の終端は開始より前にしない。原刊頁の文字列範囲は版の頁付けに照合する。SourceSequenceは指定Source内の原文の順番であり、訳文の読書順とは区別する。

Cropは `unit: pixel|fraction` と `x`、`y`、`width`、`height` の数値を持つ。原点は左上、幅と高さは正。fractionは画像全体を1として画像内に収める。pixelは元画像の寸法に照合する。切り出す画像は `asset_id` または明示した元画像URLで特定する。

**Alignment**: 必須は `source_id: string`、`original_unit_id: string`。任意は `source_span: Span` と `description_ja: string`。数値だった原文IDはその表記を文字列として保持する。一つのSegmentが複数の原文単位へ対応してよい。元の境界が未確認ならSpanを省略し、元単位IDと説明だけを保持する。

**Variant**: 必須は `kind: ocr|diplomatic|corrected|comparison`、`text: string`。任意は `source_locations: Location[]`、`description_ja: string`。異なる原文を無名の文字列として上書きしない。

**Attribution**: 必須は `voice: author|editor|digital_editor|quoted_person|translator|unknown`。任意は `contributor_id: string`、`name_ja: string`、`name_original: string`、`source_span: Span`、`translation_span: Span`、`evidence_ja: string`。範囲省略は単位全体。声の出自が不確かな場合はunknownと説明を保持し、著者や編者へ推測で割り当てない。異なる声が入れ子になる場合は範囲を含む関係を明示し、交差する曖昧な範囲を認めない。

**Annotation**: 必須は `side: source|translation`、`kind: emphasis|strong|ruby|indent|language`、`span: Span`。rubyは `reading: string`、indentは空白字幅で表す `columns: integer>=0`、languageは `language: string` を追加で必須とする。languageの値は言語タグ。emphasisとstrongは追加値を持たない。

**Issue**: 必須は `kind: unreadable|source_untranscribed|missing_source|uncertain_translation|unresolved_reference|unclassified_structure`、`status: open|resolved`、`message_ja: string`。任意は `source_span: Span`、`translation_span: Span`。必要な留保を無言の空欄で代用しない。

## 5. 注と参照

### 5.1 Span

必須は `start: integer>=0`、`end: integer>=0`、`exact: string`。Unicodeコードポイントで0から数え、`[start,end)` の半開区間とする。バイト位置、UTF-16単位、画面上の見かけの文字数では数えない。

`0 <= start < end <= 対象文字列のコードポイント数` と、対象部分文字列が `exact` に完全一致することを検証する。原文と訳文の位置は個別に指定し、原文側の位置を訳文へ流用しない。参照を含む原文・訳文の変更では関連Spanを再照合する。

### 5.2 Note

必須は `id: string`、`origin: author|editor|digital_editor|translator|unknown`、`body: NotePart[]`。任意は `label: string`、`contributor_id: string`、`source_locations: Location[]`、`form: footnote|endnote|marginal|inline|unlocated`、`description_ja: string`。bodyは一件以上。unknownには出自の留保をdescription_jaへ記す。傍注などの原典上の形式を確認できる場合はformへ記録する。

NotePartの必須は `segment_id: string`。任意は `source_span: Span`、`translation_span: Span`。範囲の省略は該当文字列の全体を意味する。注本文は `segments` に一度だけ保存する。一つの既存段落に複数の注がある場合は、それぞれの注を別Noteにして、段落内の範囲へ結ぶ。

`label` は原典の表示番号であり識別子ではない。同じ `[1]` を複数のNoteで使用してよい。印刷されたラベルは原文・訳文から勝手に除去しない。Noteのラベルを理由に本文の文字列へ別の番号を自動挿入しない。

訳注も `origin: translator` のNoteと `origin: translator` のSegmentで記録する。文字列だけの `notes` と別形式の `translator_notes` を維持しない。本文参照のない原注にはReferenceを捏造せず、定義と原典位置を保持する。

### 5.3 Reference

必須は `id: string`、`kind: note|cross_reference|index|figure`、`origin: source|translator`、`from: ReferenceFrom`、`to: ReferenceTarget|null`、`status: verified|unresolved`。

ReferenceFromの必須は `segment_id: string`。任意は `source_span: Span` と `translation_span: Span`。本文中の番号・文字列を参照にする場合は、その側のSpanを指定する。原典にある参照か、訳者が付した参照かを `origin: source|translator` で必ず指定する。

ReferenceTargetは次のいずれかとする。

- 内部の注・段落・図: `type: note|segment|figure` と `id: string`。
- 原刊頁・図像上の場所: `type: source_location` と `location: Location`。

任意の補足は `label: string`、`unresolved_label: string`、`work_code: string`、`description_ja: string`、`evidence: Location[]`。`kind: note` はNoteへ、`kind: figure` はFigureへ結ぶ。`verified` は有効な移動先と照合済みの関係を持つ。未解決は `to: null` と説明を持ち、壊れたリンクへ置き換えない。

本文から注へのReferenceを唯一の参照関係の正本とする。注から本文への戻り先はこの配列から導出し、逆向きの別配列を保守しない。索引の頁範囲・他作品コード・ローマ数字も保持する。原刊頁しか確定していない索引を、推測した段落IDへ結ばない。

## 6. 引用、詩、並列本文、表

Groupの必須は `id: string`、`kind: quotation|poem|list|parallel|table`、`members: GroupMember[]`、`separator: string`。

GroupMemberの必須は `segment_id: string`。任意は `row: integer>=1`、`column: integer>=1`、`label_ja: string`、`source_span: Span`、`translation_span: Span`。範囲を省略した側は段落全体。段落の一部の引用は範囲を指定し、固定IDや本文を分割しない。Groupの任意は `parent_id: string`、`description_ja: string`、`source_variants: Variant[]`。

- 本文・訳文はGroupへ複製しない。段落IDと区切り文字でまとまりを定義する。
- 既存グループの原文が単位原文の連結と異なる場合は、別の組み立て・校訂による異同としてsource_variantsに保持する。訳文の連結が一致していても原文の異同は保持する。
- Membersの順序は `segments` の順序に一致させる。間に別の注などが入っていても、それをグループの本文として取り込まない。
- 親子グループは循環せず、子の段落集合は親の集合に含まれる。同じ親の下で同じ段落を重複所属させない。交差する重なりを認めない。
- 並列本文の旧訳・新訳、欄、行の区別は確認済みのラベル・座標で表す。既存IDの語句から版系統を推測しない。
- 表のセルは `kind: table_cell` のSegmentと行・列の組で表し、同じ表の同一セルを重複させない。

複数段落を見た目でまとめても各SegmentのIDは維持する。単位そのものの統合は形式変換とは別の編集判断とし、原文・訳文の対応と旧IDの到達先を確認する。

## 7. 図と画像

### 7.1 Asset

必須は `id: string`、`status: planned|available`、`path: string`、`media_type: string`、`rights: Rights`、`source_locations: Location[]`。2.0のAssetは画像とし、media_typeは `image/png`、`image/jpeg`、`image/gif`、`image/webp`、`image/svg+xml` のいずれか。

`available` は `sha256: string`、`bytes: integer>=1`、`width: integer>=1`、`height: integer>=1` を持つ。ハッシュは同梱ファイルの実バイトに対する小文字16進SHA-256。パスはリポジトリルート相対、区切り `/`、`assets/<work_id>/...` 配下。絶対パス、`..`、URL、Base64をファイル参照の代用にしない。

任意は `derived_from_asset_id: string`、`processing: Processing[]`。Processingの必須は `kind: crop|rotate|resize|compress|translate_labels|redraw` と `description_ja: string`。Processingの任意は `crop: Crop`、`coordinate_image_width: integer>=1`、`coordinate_image_height: integer>=1`。crop座標はkindがcropの場合だけ使用する。加工の座標系の寸法が既知なら記録し、その範囲内に収める。元画像の高さが未確認でも幅1000pxの画像からの切り出し手順などを正確に保持できる。この加工記録を、元画像の寸法まで実測したLocation.cropと同一の検証済み状態にはしない。

原図と加工図を別Assetにして、加工図を元のIDへ結ぶ。原典の帰属・利用条件は保持する。

plannedの元画像には出典URLと、判明している元画像ハッシュを保持できる。画像バイトの実測が済むまではavailableとしない。

本文の図中文字は `kind: figure_text` のSegmentで翻訳し、画像上の位置や言語を保持する。再描画・日本語ラベル追加は加工情報で明示する。

### 7.2 Figure

必須は `id: string`、`asset_id: string`、`caption_ja: string|null`、`alt_ja: string|null`、`placement: Placement`、`required: boolean`。

任意は `caption_segment_ids: string[]`、`text_segment_ids: string[]`、`description_ja: string`。原著にあるキャプションはSegmentへ保存し、`caption_segment_ids` で参照する。その場合は `caption_ja: null` とし、同じ文を二箇所へ保存しない。独自の説明は `caption_ja` へ記録する。

Placementの必須は `anchor_type: segment|section|figure`、`anchor_id: string`、`position: before|after|start|end`。Segment・Figureにはbefore/after、Sectionにはstart/endを使用する。Figureを起点にする配置は循環を認めない。同じ起点・位置の複数図は `figures` 配列順。本文のない図版節はSectionを起点にできる。

`required: true` の図は確定時にavailableのAssetと非空altを必要とする。未確保の図を黙って削除しない。図版内の手書き書簡などの訳もSegmentsへ置き、必要なら整理用Sectionに所属させる。図の後にその訳を続ける場合は、図のPlacementを最初の補足Segmentのbeforeに指定する。物理的な原典位置と読書順を区別する。

## 8. 用語、旧ID、由来

Termの必須は `id: string`、`kind: term|person|form_of_address`、`source_language: string`、`source: string`、`translation_ja: string`。任意は `related_work_ids: string[]`、`note_ja: string`。既存の作者・ジャンル・登場人物の訳語を参照するための項目とし、全語彙を必須登録しない。

Aliasの必須は `type: segment|section|note|figure`、`old_id: string`、`new_id: string`。任意は `source_span: Span` と `translation_span: Span`。移動先は現存するID。同種別の現役IDを旧IDとして重複登録しない。AliasからAliasへの連鎖は認めず、最終移動先を記録する。

ProvenanceはJSON互換の記録用マッピング。元原稿のリポジトリ、固定コミット、パス、ハッシュ、照合資料や補訂の由来を保持できる。本文・章階層・参照・利用条件をこの項目だけに隠して、作品別の処理分岐にしない。未対応の意味を持つ項目は、標準項目を定義してから移行する。

原稿の正本は一つとする。旧原稿の完全な状態は固定Gitコミットへ残し、同じ作品の旧形式と新形式を二つの現役原稿として置かない。

## 9. 進捗と全文見直し

Workflowの必須は `stage: translating|reviewing|ready`。任意は `full_review: FullReview`。

FullReviewの必須は `status: not_started|in_progress|complete`。`complete` は `completed_at: string`、`reviewed_by: string`、`content_sha256: string` を持つ。日時は引用符付きのUTCのISO 8601表記。逐次翻訳中の部分確認を完稿後の全文見直しとして記録しない。

確認対象のハッシュは、`workflow` と `provenance` を除く文書データを [RFC 8785 JCS](https://www.rfc-editor.org/rfc/rfc8785.html) で正規化してUTF-8のSHA-256を計算する。省略された任意の最上位配列は、計算前に空配列へ補う。文字列のUnicode正規化は行わない。画像データはAssetに保持した実ファイルハッシュで対象へ含める。

`ready` の条件は次のすべて。

1. 完稿後の原文対応の照合と、日本語全文の用語・表現・雰囲気の見直しが完了している。
2. `full_review.status: complete` の対象ハッシュが現在の原稿と一致する。
3. translation_requiredがtrueのSegmentにpending、draft、unclassifiedがない。falseの単位が対象外範囲へ明示されている。
4. partial、原文未確定、未解決参照はIssueまたは説明とScopeの既知の欠落へ記録されている。
5. 必須図の同梱、ID参照、原文・訳文の位置指定、書誌・利用条件の型と関係が有効。

`ready` は「この収録範囲と留保で確定できる」状態であり、原著全体の完訳を意味しない。原稿変更後に対象ハッシュが変わった場合はreviewingへ戻し、変更の影響と全体の整合を再確認する。

## 10. 最小の記入例

次は形式を示す架空の短い原稿。利用条件を確認した実在作品の記録ではない。

```yaml
schema_version: "2.0"
work_id: "example-scene"
metadata:
  title_ja: "幕が上がるまで"
  title_original: "Until the Curtain Rises"
  original_languages: ["en"]
  target_language: "ja"
  contributors:
    - id: "author"
      name_ja: null
      name_original: "Example Author"
      roles: ["author"]
    - id: "translator"
      name_ja: null
      name_original: null
      roles: ["translator"]
  translation_rights:
    status: "unknown"
sources:
  - id: "source-1"
    role: "primary"
    title: "Until the Curtain Rises"
    languages: ["en"]
    url: null
    edition: null
    work_rights: {status: "unknown"}
    transcription_rights: {status: "unknown"}
scope:
  included:
    - source_id: "source-1"
      description_ja: "例示用の見出し、本文一段落と原注。"
  excluded: []
  known_gaps: []
sections:
  - id: "chapter-1"
    parent_id: null
    kind: "chapter"
    heading_segment_ids: ["heading-1"]
segments:
  - id: "heading-1"
    section_id: "chapter-1"
    kind: "heading"
    origin: "source"
    source_text: "The Waiting"
    source_languages: ["en"]
    source_locations:
      - source_id: "source-1"
        precision: "page"
        printed_page: "1"
    translation_ja: "待つ時間"
    translation_status: "draft"
  - id: "paragraph-1"
    section_id: "chapter-1"
    kind: "paragraph"
    origin: "source"
    source_text: "Helen waited.[1]"
    source_languages: ["en"]
    source_locations:
      - source_id: "source-1"
        precision: "page"
        printed_page: "1"
    translation_ja: "ヘレンは待った。[1]"
    translation_status: "draft"
  - id: "note-text-1"
    section_id: "chapter-1"
    kind: "note_body"
    origin: "source"
    source_text: "[1] For the curtain to rise."
    source_languages: ["en"]
    source_locations:
      - source_id: "source-1"
        precision: "page"
        printed_page: "1"
    translation_ja: "[1] 幕が上がるのを。"
    translation_status: "draft"
notes:
  - id: "note-1"
    origin: "author"
    label: "1"
    body:
      - segment_id: "note-text-1"
references:
  - id: "callout-1"
    kind: "note"
    origin: "source"
    from:
      segment_id: "paragraph-1"
      source_span: {start: 13, end: 16, exact: "[1]"}
      translation_span: {start: 8, end: 11, exact: "[1]"}
    to: {type: "note", id: "note-1"}
    status: "verified"
workflow:
  stage: "translating"
```

## 11. 機械検証の契約

型・必須項目・enum・未知の項目は [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12/json-schema-core) で定義する。JSON互換のYAMLを読み込んだ値へ適用する。項目名の旧別名を2.0内で許可しない。

参照先の存在、IDの一意性、章・Group・加工元・配置の循環、Spanと実文字列の一致、IDごとの欠落・重複、ファイルの実在とハッシュ、確定状態と対象ハッシュは意味の検証として追加する。一般のJSON Schemaだけでこれらを検証済みとしない。

受け入れに必要なケースは次のとおり。

- 通常の章と対訳段落、原文と訳文の異なる文字位置を持つ注参照。
- 任意の深さの部・章・節、前付、フォリオの表裏。
- 一つの訳文に複数原文単位が対応するケース。
- 同じ番号の別注、一段落内の複数注、本文参照のない注、原注と訳注の混在。
- 詩の改行と引用のグループ、並列本文、表のセル。
- 本文のない図版節、同じ画像の共有、原図と加工図、図中文字と部分訳。
- 索引の頁範囲・他作品コード・空白頁、確認できない移動先。
- 未訳・部分訳・原典の欠落・対象外を区別した状態。
- 未訳編者注の原文を保持しつつ、本文の翻訳対象から除外するケース。異なる組み立て原文を持つ引用グループ。
- 誤ったID、古いSpan、矛盾する利用条件、改訂後の古い全文確認ハッシュを拒否するケース。


## 12. 目録と編集手順

`catalog.yaml` は翻訳本文とは別の目録。schema_versionは `"2.0"`、worksは配列。各作品に `work_id`、`file`、`title`、`sha256` が必須。fileはtranslations配下のYAML、titleはmetadata.title_ja、sha256は原稿ファイルの実バイト。作品IDとファイルパスは一意。全原稿を一件ずつ登録する。目録の利用条件・収録範囲の説明は保持する。

原稿の編集・追加後は次のコマンドを使用する。目録の書名やハッシュを手で二重管理しない。sync_catalogは既存の掲載順と説明を保持し、新規ファイルをパス順に末尾へ追加する。削除されたファイルは目録から除く。

```sh
python -m pip install -r requirements.txt
python scripts/translation_yaml.py translations/<genre>/<work>.yaml
python scripts/sync_catalog.py
python scripts/translation_yaml.py
python scripts/translation_yaml.py translations/<genre>/<work>.yaml --hash
```

最後のハッシュを全文見直しの完了時に記録する。機械検証だけで全文見直しを完了扱いにしない。原稿改訂後は以前の確認ハッシュを再使用しない。
