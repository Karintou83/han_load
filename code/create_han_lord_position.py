"""
edo-daimyo-genealogy: 「○○藩主」役職のWikidata項目を自動生成するスクリプト

峰山藩(Q141515630)で確立した項目構造を、任意の藩に汎用化したもの。
小城藩での試し打ちで実際に動作確認済み(2026-09時点)。

【重要】このスクリプトはWikidataへの書き込みを一切行わない。
生成したQuickStatements V1形式のTSVファイルを出力するだけなので、
中身を必ず目視確認してから https://quickstatements.toolforge.org/ に
手動で貼り付けて投入すること(CLAUDE.mdの「必ず数件だけ試し打ちして
から本番投入する」運用方針に従う)。

依存パッケージ:
    pip install requests
(mwparserfromhellは使わず、標準のreだけでwikitextを解析する設計にした。
 依存を減らすためと、実際に正規表現ベースで表記ゆれに対応できることを
 このスクリプト作成時にオフラインでテスト済みのため。)

実行方法:
    # 1藩分の下ごしらえ(役職項目の作成TSV + 家系ドラフト)をまとめて生成
    python create_han_lord_position.py prepare-han <藩名> <旧国名>
    # -> <藩名>_position_create.tsv をQuickStatementsに投入し、発行されたQIDを控える

    # 発行されたQIDを使って、逆リンク+各藩主個人へのP39等を生成
    python create_han_lord_position.py add-person-statements <藩名> <役職QID>

    # 各藩主の記事Infoboxから父・養父の関係をドラフト生成する(要人間レビュー)
    python create_han_lord_position.py draft-family <藩名>

    【重要】値の位置に"LAST"を使うQuickStatementsコマンドは、実際の投入で
    Error 422 (patch-result-invalid-value) となり、以降のLAST参照も連鎖的に
    無効になることが確認されている(赤穂藩での実投入)。そのためLASTは
    常に主語(1列目)としてのみ使い、値には実際のQID文字列を使うこと。

    在任年の書式(<small>年-年</small> か （年-年） か)が想定と違う藩に
    当たった場合は、_LINK_YEAR_PATTERNS に新しいパターンを追加すること。

    【重要】テンプレートに載っている人物のうち、Wikidata項目が見つからず
    スキップされる代がいる場合、それ以降の代のP1545(代数)が実際の代数と
    ずれてしまわないよう、各人物の本来の出現順(ordinal)をそのまま保持する
    設計にしている。そのため前任者・後任者(P1365/P1366)や養子関係の自動
    補完も、単純にリスト上の前後ではなく、ordinalが実際に1つ違いかどうかで
    判定する(詳細は resolve_officeholders() / build_all_person_statements() /
    build_family_relation_draft() の各docstringを参照)。
"""

from __future__ import annotations

import argparse
import os
import re
import time
import requests

JAWIKI_API = "https://ja.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
# Wikimediaの User-Agent policy は、連絡先(メールアドレスまたはURL)を含めることを求めている。
# 環境変数 EDO_UA_CONTACT があればそれを使い、なければ作者のWikipedia利用者ページを使う。
# 他の人が使うときは、自分の連絡先を EDO_UA_CONTACT に設定すること。
#   例(PowerShell): $env:EDO_UA_CONTACT = "https://ja.wikipedia.org/wiki/User:YourName"
_UA_CONTACT = os.environ.get("EDO_UA_CONTACT", "https://ja.wikipedia.org/wiki/User:Lin_Xiangru")
USER_AGENT = f"edo-daimyo-genealogy-script/0.1 ({_UA_CONTACT}; personal research project)"
_REQUEST_TIMEOUT = 30  # 秒。回線が遅い/応答が返ってこない場合にリクエストが無限に固まるのを防ぐ

# --- 全藩共通の定数(峰山藩 Q141515630 の実例から確定させたもの) -----------
Q_HISTORICAL_POSITION = "Q114962596"   # 歴史上の職位
Q_EARLY_MODERN_DAIMYO = "Q24887524"    # 近世大名
Q_JAPAN               = "Q17"          # 日本
Q_EDO_PERIOD          = "Q184963"      # 江戸時代


# ---------------------------------------------------------------------------
# Wikipedia側:テンプレートのwikitext取得
# ---------------------------------------------------------------------------

def _jawiki_get(params: dict, max_retries: int = 6) -> dict:
    """
    jawiki APIへのGETラッパー。429(Too Many Requests)を検知したら、
    Retry-Afterヘッダ(無ければ指数バックオフ)に従って待機し、再試行する。
    また、回線が遅い・パケットが落ちた等でサーバーから応答が一切返って
    こない場合に備えてtimeout=_REQUEST_TIMEOUTを付け、タイムアウトや
    接続エラーが起きた場合も429と同様に指数バックオフで再試行する
    (timeoutを付けないとrequests.get()は応答が来るまで無期限に待ち続け、
    ハングしたのか単に遅いだけなのか外から区別が付かなくなるため)。

    draft-familyで11人分の記事を連続取得した際にja.wikipedia.org側でも
    429が発生したため、_wikidata_getと同じ仕組みをこちらにも適用した。
    """
    for attempt in range(max_retries):
        try:
            resp = requests.get(
                JAWIKI_API, params=params, headers={"User-Agent": USER_AGENT},
                timeout=_REQUEST_TIMEOUT,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            wait = 2 ** attempt
            print(f"    (通信エラー: {e!r} -> {wait}秒待機してリトライ)")
            time.sleep(wait)
            continue
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 2 ** attempt))
            print(f"    (429 Too Many Requests -> {retry_after}秒待機してリトライ)")
            time.sleep(retry_after)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(
        "jawiki APIへのリクエストが繰り返しレート制限/タイムアウトになりました。"
        "時間を置くか、リクエスト間隔をさらに広げてください。"
    )


def get_wikitext(title: str) -> str:
    """jawikiの指定ページの最新版wikitextを取得する。"""
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "titles": title,
        "format": "json",
        "formatversion": "2",
    }
    data = _jawiki_get(params)
    pages = data["query"]["pages"]
    if not pages or pages[0].get("missing"):
        raise ValueError(f"ページが見つかりません: {title}")
    return pages[0]["revisions"][0]["slots"]["main"]["content"]


def get_template_wikitext(han_title: str) -> str:
    """「Template:○○藩主」のwikitextを取得する。"""
    return get_wikitext(f"Template:{han_title}主")


# ---------------------------------------------------------------------------
# テンプレートから在職順・在任年を抽出
# ---------------------------------------------------------------------------

# [[人物]] または [[人物|表示名]] の直後に在任年が続くパターン。
# Template:小城藩主 の実物を確認したところ、括弧書きではなく
# <small>1642-1654</small> 形式が標準だったため、これを最優先にする。
# 括弧書き(（1622-1628）等)は、別の藩のテンプレートが違う書式を
# 使っていた場合のフォールバックとして残す。
_LINK_YEAR_PATTERNS = [
    # <small>1642-1654</small> 形式(実物のTemplate:小城藩主で確認済み)
    re.compile(
        r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]\s*<small>\s*(\d{3,4})\s*[-–〜]\s*(\d{3,4})\s*</small>"
    ),
    # （1622-1628） 形式(念のため残すフォールバック)
    re.compile(
        r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]\s*[（(]\s*(\d{3,4})\s*[-–〜]\s*(\d{3,4})\s*[）)]"
    ),
]


# <small>...</small> の中身を、カンマ等で区切られた「1つ以上の在任期間」として読む。
# 例: "1866-1868"(通常) / "1866"(単年) / "1866-1868,1868"(再任を含む複数期間)
# 単年の記述(阿部正静の "1866" "1868" など)は、開始年=終了年=その年として扱う。
# "1866-" のように終了年が欠けている場合は、終了年を None のまま返す。
_SMALL_RE = re.compile(
    r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]\s*<small>(.*?)</small>", re.DOTALL
)
_PERIOD_SPLIT_RE = re.compile(r"\s*[,、，/／]\s*")
_PERIOD_RE = re.compile(r"^(\d{3,4})?\s*(?:([-–〜~－])\s*(\d{3,4})?)?$")
# 年の直後の補足(1809) / （1809） は無視する(例: 伊達周宗 "1796-1812(1809)")。
# 補足年の意味はTemplateごとに異なり(隠居・実質的な交代など)、正式な在任期間は括弧の外の年とみなす。
_PAREN_YEAR_RE = re.compile(r"[（(]\s*\d{3,4}\s*[）)]")

# 取り込めなかった <small> を警告するために、解析結果の横に残しておく
LAST_PARSE_WARNINGS: list[str] = []


def _parse_periods(text: str) -> list[tuple[int | None, int | None]] | None:
    """
    <small>の中身を [(開始年, 終了年), ...] に変換する。解釈できなければNone。
    "1866" は単年(開始=終了)、"-1616" は開始年なし、"1700-" は終了年なしとして
    それぞれ None を返す(P580/P582は取れた側だけ付与される)。
    """
    text = re.sub(r"<[^>]+>", "", text)
    text = _PAREN_YEAR_RE.sub("", text).strip()
    periods = []
    for part in _PERIOD_SPLIT_RE.split(text):
        if not part:
            continue
        m = _PERIOD_RE.match(part)
        if not m:
            return None
        start, dash, end = m.groups()
        if start is None and end is None:
            return None
        if dash is None:
            periods.append((int(start), int(start)))  # 単年
        else:
            periods.append((int(start) if start else None, int(end) if end else None))
    return periods or None


def parse_officeholders_with_years(wikitext: str) -> list[dict]:
    """
    テンプレートのwikitextから [[人物]]+在任年 の並びを出現順に抽出する。

    戻り値: [{"title": "鍋島元茂", "start_year": 1642, "end_year": 1654}, ...]

    <small>年-年</small> に加え、単年(<small>1866</small>)と、再任などで
    1つの <small> に複数の期間が入る形(<small>1866-1868,1868</small>)に対応する。
    複数期間は期間ごとに1件ずつ(出現順に)返す。
    解釈できなかった <small> は LAST_PARSE_WARNINGS に残し、呼び出し側が表示する
    (黙って落とすと、藩主が抜けたことに気づけないため)。
    <small> 形式が1件も無い場合は、（年-年）形式にフォールバックする。
    """
    LAST_PARSE_WARNINGS.clear()
    results: list[dict] = []
    for m in _SMALL_RE.finditer(wikitext):
        title, body = m.group(1).strip(), m.group(2)
        periods = _parse_periods(body)
        if periods is None:
            LAST_PARSE_WARNINGS.append(f"[[{title}]]<small>{body.strip()}</small> を年として解釈できませんでした")
            continue
        for start, end in periods:
            if start is None or end is None:
                LAST_PARSE_WARNINGS.append(
                    f"[[{title}]] は{'開始' if start is None else '終了'}年がありません"
                    f"(取れた年のみ P580/P582 に付与します): {start}-{end}")
            results.append({"title": title, "start_year": start, "end_year": end})
    if results:
        return results

    # フォールバック: （1622-1628） 形式
    pattern = re.compile(
        r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]\s*[（(]\s*(\d{3,4})\s*[-–〜]\s*(\d{3,4})\s*[）)]"
    )
    return [
        {"title": t.strip(), "start_year": int(a), "end_year": int(b)}
        for t, a, b in pattern.findall(wikitext)
    ]


# ---------------------------------------------------------------------------
# Wikidata側:タイトル→QID変換
# ---------------------------------------------------------------------------

def _wikidata_get(params: dict, max_retries: int = 6) -> dict:
    """
    Wikidata APIへのGETラッパー。429(Too Many Requests)を検知したら、
    Retry-Afterヘッダ(無ければ指数バックオフ)に従って待機し、再試行する。
    また、回線が遅い・パケットが落ちた等でサーバーから応答が一切返って
    こない場合に備えてtimeout=_REQUEST_TIMEOUTを付け、タイムアウトや
    接続エラーが起きた場合も429と同様に指数バックオフで再試行する
    (timeoutを付けないとrequests.get()は応答が来るまで無期限に待ち続け、
    ハングしたのか単に遅いだけなのか外から区別が付かなくなるため)。

    11人分を0.5秒間隔で連続リクエストしただけで429が出たことから、
    単純にsleepを延ばすだけでなく、リトライそのものを組み込む設計にした。
    """
    for attempt in range(max_retries):
        try:
            resp = requests.get(
                WIKIDATA_API, params=params, headers={"User-Agent": USER_AGENT},
                timeout=_REQUEST_TIMEOUT,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            wait = 2 ** attempt
            print(f"    (通信エラー: {e!r} -> {wait}秒待機してリトライ)")
            time.sleep(wait)
            continue
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 2 ** attempt))
            print(f"    (429 Too Many Requests -> {retry_after}秒待機してリトライ)")
            time.sleep(retry_after)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(
        "Wikidata APIへのリクエストが繰り返しレート制限/タイムアウトになりました。"
        "時間を置くか、リクエスト間隔をさらに広げてください。"
    )


def title_to_qid(jawiki_title: str) -> str | None:
    """
    jawikiのページタイトル(名前空間込みでよい。例: "Category:小城藩主")から
    対応するWikidata項目のQIDを引く。見つからなければNoneを返す。
    """
    params = {
        "action": "wbgetentities",
        "sites": "jawiki",
        "titles": jawiki_title,
        "props": "info",
        "format": "json",
    }
    data = _wikidata_get(params)
    for qid in data.get("entities", {}):
        if not qid.startswith("-"):  # "-1" 等はヒットなしを意味する
            return qid
    return None


def search_qid_by_label(name: str) -> str | None:
    """
    wbsearchentitiesで日本語ラベルからWikidata項目を検索する。

    title_to_qid()はjawikiのサイトリンク経由でしか探せないため、
    Wikipedia記事が存在しない人物(赤リンク)には使えない。しかし
    Wikipedia記事が無くてもWikidata項目だけ単独で存在するケースが
    あるため、そのフォールバックとして用意した。
    """
    params = {
        "action": "wbsearchentities",
        "search": name,
        "language": "ja",
        "type": "item",
        "format": "json",
        "limit": 5,
    }
    data = _wikidata_get(params)
    results = data.get("search", [])
    for result in results:
        if result.get("label") == name:  # ラベル完全一致を優先
            return result["id"]
    return None  # 完全一致が無ければ「見つからない」扱いにする(誤爆防止)


_QID_OVERRIDES_PATH = "person_qid_overrides.tsv"
_qid_overrides_cache: dict[str, str] | None = None


def _load_qid_overrides() -> dict[str, str]:
    """
    person_qid_overrides.tsv(人物名<TAB>QID)を読み込む。日本語版Wikipediaに記事が無く、
    Wikidata側だけに作った項目は、記事タイトル経由では見つからず、ラベル検索も
    索引の反映待ちで外れることがあるため、判明しているQIDをここに書いて最優先で使う。
    ファイルが無ければ空。スクリプトと同じフォルダ(カレントではなく)から読む。
    """
    global _qid_overrides_cache
    if _qid_overrides_cache is not None:
        return _qid_overrides_cache
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), _QID_OVERRIDES_PATH)
    table: dict[str, str] = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 2 and re.fullmatch(r"Q\d+", parts[1].strip()):
                    table[parts[0].strip()] = parts[1].strip()
    _qid_overrides_cache = table
    return table


def resolve_person_qid(name: str) -> str | None:
    """
    人物名からQIDを解決する。まずjawiki記事経由(title_to_qid)を試し、
    見つからなければWikidataのラベル完全一致検索にフォールバックする。
    """
    override = _load_qid_overrides().get(name)
    if override:
        return override
    qid = title_to_qid(name)
    if qid:
        return qid
    return search_qid_by_label(name)


# ---------------------------------------------------------------------------
# QuickStatements V1コマンド生成
# ---------------------------------------------------------------------------

def _year_to_qs_date(year: int) -> str:
    """年精度(precision=9)のQuickStatements V1日付形式に変換する。"""
    return f"+{year:04d}-00-00T00:00:00Z/9"


def build_officeholder_qualifiers(
    ordinal: int, start_year: int | None, end_year: int | None
) -> list[str]:
    """
    P1308(在職者)ステートメントに付ける修飾子を組み立てる。
    系列内での順序(P1545)は常に付け、開始・終了年(P580/P582)は
    テンプレートから取れた場合のみ付ける。
    """
    qualifiers = ["P1545", f'"{ordinal}"']
    if start_year is not None:
        qualifiers += ["P580", _year_to_qs_date(start_year)]
    if end_year is not None:
        qualifiers += ["P582", _year_to_qs_date(end_year)]
    return qualifiers


def build_han_lord_position_commands(
    han_title: str,
    han_qid: str,
    province: str,
    officeholders: list[dict],   # {"qid", "start_year", "end_year", "ordinal"} を在職順に
    template_qid: str | None,
    category_qid: str | None,
) -> list[list[str]]:
    """
    「○○藩主」役職項目をCREATEするQuickStatements V1コマンド列を生成する。
    峰山藩(Q141515630)の実際の構造をそのまま一般化したもの。

    【重要】以前はここで藩・Template・Categoryからの逆リンクも
    値を"LAST"にして同じバッチ内で張っていたが、赤穂藩での実投入で
    「値の位置にLASTを使うと Error 422 (patch-result-invalid-value) で
    失敗し、しかもそれ以降のLAST参照がすべて連鎖的に無効になる」ことが
    判明したため撤回した。LASTは常に主語(1列目)としてのみ使い、値には
    使わない設計に統一している。逆リンクは build_reciprocal_link_commands()
    で、実際に発行されたQIDが判明してから別バッチとして生成すること。
    """
    label = f"{han_title}主"
    description = f"{province}{han_title}を治めた藩主"
    alias = f"{han_title}知事"  # 明治期の「藩知事」呼称。P39は分けずこちらに統合する方針

    cmds: list[list[str]] = [
        ["CREATE"],
        ["LAST", "Lja", f'"{label}"'],
        ["LAST", "Dja", f'"{description}"'],
        ["LAST", "Aja", f'"{alias}"'],
        ["LAST", "P31", Q_HISTORICAL_POSITION],
        ["LAST", "P279", Q_EARLY_MODERN_DAIMYO],
        ["LAST", "P2389", han_qid],
        ["LAST", "P17", Q_JAPAN],
        ["LAST", "P2348", Q_EDO_PERIOD],
    ]
    if template_qid:
        cmds.append(["LAST", "P1424", template_qid])
    if category_qid:
        cmds.append(["LAST", "P910", category_qid])

    for holder in officeholders:
        qualifiers = build_officeholder_qualifiers(
            holder["ordinal"], holder["start_year"], holder["end_year"]
        )
        cmds.append(["LAST", "P1308", holder["qid"], *qualifiers])

    return cmds


def build_reciprocal_link_commands(
    position_qid: str,
    han_qid: str,
    template_qid: str | None,
    category_qid: str | None,
) -> list[list[str]]:
    """
    藩(組織)・Template・Categoryの3項目それぞれから、既に作成済みの
    役職項目(position_qid、実際のQID)への逆リンクを張る。

    値には必ず実際のQID文字列を使う("LAST"は使わない)。position_qidは
    役職項目のTSVを実際にQuickStatementsへ投入したあと、発行された
    QIDを見て手動で渡すこと。
    """
    cmds: list[list[str]] = [[han_qid, "P2388", position_qid]]
    if template_qid:
        cmds.append([template_qid, "P1423", position_qid])
    if category_qid:
        cmds.append([category_qid, "P301", position_qid])
    return cmds


def commands_to_tsv(commands: list[list[str]]) -> str:
    """QuickStatements V1形式(タブ区切り)のテキストに変換する。"""
    return "\n".join("\t".join(row) for row in commands)


# ---------------------------------------------------------------------------
# 各藩主の記事Infoboxから父・養父を抽出する(家系関係のドラフト生成用)
# ---------------------------------------------------------------------------

# 日本の武将・大名の伝記記事でよく使われるInfoboxテンプレート名の候補。
# 記事によって異なるため、複数候補を順に試す。実際に一致しない藩に
# 当たった場合は、その記事のwikitextを見てここに候補を追加すること。
_BIOGRAPHY_INFOBOX_TEMPLATE_NAMES = [
    "基礎情報 武士",
    "基礎情報 大名",
    "日本の武将",
    "政治家",  # 明治期に藩知事等を務めた人物の記事でよく使われる
]

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")

# 「父母」「親族」のような1つのフィールドに「ラベル：[[人物]]」あるいは
# 「ラベル・[[人物]]」(中黒区切り、{{政治家}}系でよく見る)の形で
# まとめて書かれているケース全般に対応する汎用正規表現。
# ラベルは「父」「養父」だけでなく「叔父」「兄」等の任意の続柄も拾う
# (これらは自動でプロパティに変換せず、人間のレビュー対象として報告する)。
_LABELED_RELATION_RE = re.compile(r"([一-龥]{1,3})[:：・]\s*(?:'{2,5})?\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def extract_person_name(value: str) -> str | None:
    """
    Infoboxのフィールド値(wikitext)から人物名を1つ取り出す。
    "[[鍋島勝茂]]" のようにリンクがあればリンク先を、無ければ
    テキストそのまま(空なら None)を返す。
    """
    value = value.strip()
    if not value:
        return None
    m = _WIKILINK_RE.search(value)
    if m:
        return m.group(1).strip()
    return value or None


def extract_labeled_relations(text: str) -> list[tuple[str, str]]:
    """"ラベル：[[人物]]" または "ラベル・[[人物]]" の形のペアをすべて拾う。"""
    return [(label, name.strip()) for label, name in _LABELED_RELATION_RE.findall(text)]


# 「父母」欄がラベルなしのプレーンな名前の列挙(例: "森忠賛、'''森忠哲'''")で
# 書かれているケースに対応する。Wikipediaでは養父を強調記法(''または''')で
# 囲んで表す慣例があるとのこと(森忠敬の記事で確認)。
_EMPHASIS_RE = re.compile(r"'{2,5}([^']+)'{2,5}")


def extract_plain_name_list_relations(text: str) -> dict:
    """
    「実父、'''養父'''」のように、ラベルもリンクも無い(あるいはリンクは
    あってもラベル無し)、カンマ区切りの名前列挙形式から父・養父を推定する。
    先頭の名前を実父、強調記法で囲まれた名前を養父とみなす。
    """
    parts = re.split(r"[、,]", text)
    father = adoptive_father = None
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = _EMPHASIS_RE.search(part)
        if m:
            if adoptive_father is None:
                adoptive_father = extract_person_name(m.group(1))
        elif father is None:
            father = extract_person_name(part)
    return {"father": father, "adoptive_father": adoptive_father}


def extract_template_params(wikitext: str, template_names: list[str]) -> dict[str, str] | None:
    """
    wikitext内から、template_namesのいずれかに一致する最初のテンプレート
    呼び出しを探し、そのパラメータをキー:値の辞書として返す。
    見つからなければNoneを返す。

    mwparserfromhellを使わない簡易実装だが、ネストした{{...}}や[[...]]の
    深さを数えながら処理するため、Infoboxの値にリンクや別テンプレートが
    入っていても、フィールドの区切り("|")を誤検出しない。
    """
    normalized_names = {name.replace("_", " ").strip() for name in template_names}

    idx = 0
    while True:
        start = wikitext.find("{{", idx)
        if start == -1:
            return None

        name_end = start + 2
        while name_end < len(wikitext) and wikitext[name_end] not in "|}":
            name_end += 1
        name = wikitext[start + 2:name_end].strip().replace("_", " ")
        if name not in normalized_names:
            idx = start + 2
            continue

        # 対応する閉じ"}}"を、深さを数えながら探す
        depth = 1
        pos = name_end
        while depth > 0 and pos < len(wikitext):
            two = wikitext[pos:pos + 2]
            if two == "{{":
                depth += 1
                pos += 2
            elif two == "}}":
                depth -= 1
                pos += 2
            else:
                pos += 1
        body = wikitext[name_end:pos - 2]  # 先頭の"|"を含み、末尾の"}}"は含まない

        # 深さ0の"|"だけをフィールド区切りとして分割する
        fields = []
        field_start = 1  # 先頭の"|"をスキップ
        depth2 = 0
        i = 1
        while i < len(body):
            two = body[i:i + 2]
            if two in ("{{", "[["):
                depth2 += 1
                i += 2
                continue
            if two in ("}}", "]]"):
                depth2 -= 1
                i += 2
                continue
            if body[i] == "|" and depth2 == 0:
                fields.append(body[field_start:i])
                field_start = i + 1
            i += 1
        fields.append(body[field_start:])

        params = {}
        for field in fields:
            if "=" not in field:
                continue
            key, value = field.split("=", 1)
            params[key.strip()] = value.strip()
        return params


# 続柄のラベル自体がリンクになっている書き方(例: "[[父]]：[[伊達重村]]、[[母]]：...")が
# ある。そのままだと「ラベル：[[人物]]」の正規表現に合わず父を取りこぼしたり、最初のリンク
# "[[父]]" を人名と取り違えたりする(20藩で74件)。ラベルのリンクは外して素の語にそろえる。
_KINSHIP_LABEL_LINK_RE = re.compile(
    r"\[\[(父親|母親|父|母|養父|養母|実父|実母|義父|義母|叔父|伯父|祖父|祖母|兄|弟|姉|妹|娘|子|養子|嫡子|孫|甥)"
    r"(?:\|[^\]]*)?\]\]"
)


_KINSHIP_LABEL_ALIAS = {"父親": "父", "母親": "母", "実父親": "実父"}


def _strip_kinship_label_links(text: str) -> str:
    return _KINSHIP_LABEL_LINK_RE.sub(
        lambda m: _KINSHIP_LABEL_ALIAS.get(m.group(1), m.group(1)), text
    )


# 「養父：佐竹義格」のようにラベルの後の人名にリンクが付いていない書き方がある。
# リンク付きの抽出で拾えなかった場合に限り、次の区切り(、 , <br> 括弧 改行)までを人名として拾う。
_PLAIN_LABEL_RE = re.compile(
    r"(養父|実父|(?<![養実義叔伯祖])父)[:：]\s*(?:'{2,5})?([^、,<>\[\]\n（()'：:]{2,20}?)(?:'{2,5})?(?=[、,<（(\n]|$)"
)


def _extract_plain_label_names(text: str) -> dict:
    found = {}
    for label, name in _PLAIN_LABEL_RE.findall(text):
        name = name.strip()
        label = "父" if label == "実父" else label
        if name and name not in ("不明", "なし") and label not in found:
            found[label] = name
    return found


def extract_family_fields(wikitext: str) -> dict:
    """
    人物記事のInfoboxから父・養父を抽出する。

    小城藩の記事では「父母」という1つのフィールドに
    「父：[[X]]、母：...、養父：[[Y]]」とまとめて書かれているケースが多い。
    また{{政治家}}系の記事では「親族」というフィールドに
    「父・[[X]]、養父・[[Y]]」(中黒区切り)とまとめて書かれていることが多い。
    さらに、赤穂藩の記事(森忠敬)では「森忠賛、'''森忠哲'''」のように
    ラベルもリンクも無い、カンマ区切りの名前列挙形式(先頭が実父、
    強調記法で囲まれた方が養父)も確認されている。
    父・養父の代わりに「叔父」等が使われているケース(鍋島直虎)も
    確認されているため、以下の優先順で探す:
      1. 「父母」または「親族」フィールドの中から、ラベル付きの関係を
         すべて正規表現で抽出する
      2. 見つからなければ、同じフィールドをプレーンな名前列挙形式として
         解釈する(先頭=実父、強調記法=養父)
      3. どちらも見つからなければ、全フィールドの値を連結して1と同様に探す
         (他のフィールド名で書かれているケースへの保険)
      4. それでも見つからなければ、独立した「父」「養父」キーそのものを見る
         (峰山藩のように昔ながらの形式で書かれている記事向け)

    「父」「養父」以外のラベル(叔父、兄など)は自動でプロパティに変換せず、
    "other_relations" として返すので、レビュー時に人間が判断すること。
    """
    params = extract_template_params(wikitext, _BIOGRAPHY_INFOBOX_TEMPLATE_NAMES)
    if params is None:
        return {"father": None, "adoptive_father": None, "other_relations": []}

    params = {k: _strip_kinship_label_links(v) for k, v in params.items()}

    candidates = []
    if "父母" in params:
        candidates.append(params["父母"])
    if "親族" in params:
        candidates.append(params["親族"])

    father = adoptive_father = None
    other_relations: list[tuple[str, str]] = []
    found_in_dedicated_field = False
    for text in candidates:
        relations = extract_labeled_relations(text)
        if relations:
            found_in_dedicated_field = True
            for label, name in relations:
                if label == "父" and father is None:
                    father = name
                elif label == "養父" and adoptive_father is None:
                    adoptive_father = name
                elif label not in ("父", "養父") and (label, name) not in other_relations:
                    other_relations.append((label, name))
            continue  # ラベル付き形式が見つかったので、プレーン形式の判定は不要

        plain = extract_plain_name_list_relations(text)
        if plain["father"] or plain["adoptive_father"]:
            found_in_dedicated_field = True
            if father is None:
                father = plain["father"]
            if adoptive_father is None:
                adoptive_father = plain["adoptive_father"]

    # プレーン列挙の解析が「父：佐竹義長」とラベルごと拾ってしまった値は捨てて、下の抽出に任せる
    if father and re.search(r"[:：]", father):
        father = None
    if adoptive_father and re.search(r"[:：]", adoptive_father):
        adoptive_father = None

    # リンク無しの書き方(例: 養父：佐竹義格)で、上で拾えなかった父・養父を補う
    for text in candidates:
        plain_labeled = _extract_plain_label_names(text)
        if father is None and "父" in plain_labeled:
            father = plain_labeled["父"]
        if adoptive_father is None and "養父" in plain_labeled:
            adoptive_father = plain_labeled["養父"]

    # 「父母」「親族」で何も見つからなかった場合のみ、他のフィールド名で
    # 書かれているケースへの保険として全フィールドを連結して探す
    # (見つかったのに二重に走査すると同じ関係を重複計上してしまうため)
    if not found_in_dedicated_field:
        for label, name in extract_labeled_relations(" ".join(params.values())):
            if label == "父" and father is None:
                father = name
            elif label == "養父" and adoptive_father is None:
                adoptive_father = name
            elif label not in ("父", "養父") and (label, name) not in other_relations:
                other_relations.append((label, name))

    if father is None and "父" in params:
        father = extract_person_name(params["父"])
    if adoptive_father is None and "養父" in params:
        adoptive_father = extract_person_name(params["養父"])

    return {"father": father, "adoptive_father": adoptive_father, "other_relations": other_relations}


# 養子関係の修飾子に使う定数(CLAUDE.mdの峰山藩での確定ルールに基づく)
Q_ADOPTIVE_PARENT = "Q20746742"        # 養親(養父側の項目に付ける基本値)
Q_ADOPTIVE_FATHER_IN_LAW = "Q13204680"  # 義父(婿養子の場合、上記に追加する)
Q_ADOPTED_CHILD = "Q20746725"          # 養子(養親側から見た逆方向。全ケース共通)


# Infoboxの欄に人名ではなく続柄の語そのもの(「父」等)が入っているページがあり、
# それがWikipedia記事/Wikidata項目(例: Q54553304, Q7565)に解決されて、
# 誤ったP22/P40を生成する不具合があった(20藩で74件)。続柄の語は人名として扱わない。
_GENERIC_KINSHIP_WORDS = {
    "父", "父親", "実父", "養父", "義父", "母", "母親", "養母", "実母", "子", "養子", "嫡子",
    "兄", "弟", "姉", "妹", "叔父", "伯父", "祖父", "祖母", "孫", "甥", "従兄弟", "従兄", "従弟",
    "親", "親族", "家族", "不明", "なし", "-", "―", "？", "?",
}


def build_family_relation_draft(
    officeholders: list[dict],
    new_persons: list[dict] | None = None,
) -> tuple[list[list[str]], list[str]]:
    """
    各在職者のWikipedia記事Infoboxを参照し、父・養父の関係をドラフトとして
    組み立てる。

    P22(父)+P40(子、逆方向)は機械的に確定できるのでそのままコマンド化する。
    P1038(養父)側も生成するが、婿養子か単純養子かの判別は行わず、
    常にP1039=「養親」のみを設定する(この判別は本文を読まないと
    確定できず自動化が難しいため、意図的に踏み込まない方針)。
    逆方向(養親側)のP1039=「養子」は全ケース共通のため自動生成する。

    ヒューリスティック: Infoboxに養父の記載が無く、かつ実父が先代
    (直前の在職者)と一致しない場合、先代を養父とみなして補完する
    (藩主の座を継ぐには、実子でない限り先代の養子になる必要が
    あったはずという歴史的背景に基づく)。Infoboxに養父が明記されて
    いれば、そちらを優先しこの補完は行わない。初代(先代が存在しない)
    には適用しない。この補完は以下の場合にも行わない(いずれもレポートに
    理由付きで記載する):
      ・officeholders上は直前の要素でも、ordinal(本来の代数)が1つ違いに
        なっていない場合(QID未解決でスキップされた代を挟んでいる可能性が
        あり、その場合は実際の先代とは限らないため)
      ・先代と名字(最初の1文字)が異なる場合(藩主家そのものが交代した
        (改易・転封等)とみなす)
      ・実父がInfoboxに記載されているのに、そのWikidata項目が見つからず
        (father_qidがNoneのまま)、先代と同一人物かどうか判別できない場合

    「父」「養父」以外のラベル(叔父など)が見つかった場合は、コマンドは
    生成せず、レポートに「要確認」として記載するだけにする。対応する
    プロパティ・修飾子(P1038+おじ等)は人間が判断してから手動で追加する。

    人物名からQIDへの解決は resolve_person_qid() を使う。Wikipedia記事が
    無い人物(赤リンク)でも、Wikidata側だけ単独で項目があるケースを
    ラベル検索で拾えるようにしている。

    Wikidata項目が見つからない父は、new_persons(リストを渡した場合のみ)に
    作成候補として追記する(run_draft_family等が new_persons_all.tsv にまとめて出力する)。
    養父は、初代(ordinal==1)の養父のみ作成候補にする。初代以外の養父は
    項目を作らず、養子関係の行も生成しない(方針: 初代以外の養父の項目は不要)。

    戻り値: (QuickStatementsコマンド列, レビュー用の説明行のリスト)
    """
    commands: list[list[str]] = []
    report: list[str] = []
    father_qid_of: dict[int, str | None] = {}  # officeholders上の添字 -> 実父QID(判明分のみ)

    for i, holder in enumerate(officeholders):
        title, person_qid = holder["title"], holder["qid"]
        print(f"  {title} の記事を取得中...")
        try:
            wikitext = get_wikitext(title)
        except ValueError:
            report.append(f"[{title}] 記事の取得に失敗しました。手動で確認してください。")
            continue
        time.sleep(1.0)  # APIへの配慮(429対策でリトライも入れたが、間隔自体も広げた)

        fields = extract_family_fields(wikitext)
        for _key, _label in (("father", "父"), ("adoptive_father", "養父")):
            _v = fields[_key]
            if _v is not None and _v.strip() in _GENERIC_KINSHIP_WORDS:
                report.append(f"[{title}] ★要確認: Infoboxの{_label}欄に人名ではなく「{_v}」とだけ書かれていたため無視しました。"
                               f"記事を見て手動で確認してください。")
                fields[_key] = None

        if fields["father"] is None and fields["adoptive_father"] is None and not fields["other_relations"]:
            report.append(f"[{title}] Infoboxから親族関係を抽出できませんでした。"
                           f"手動で確認するか、_BIOGRAPHY_INFOBOX_TEMPLATE_NAMES にテンプレート名を追加してください。")

        father_qid = None
        if fields["father"]:
            father_qid = resolve_person_qid(fields["father"])
            time.sleep(1.0)
            if father_qid:
                father_qid_of[i] = father_qid
                commands.append([person_qid, "P22", father_qid])
                commands.append([father_qid, "P40", person_qid])
                report.append(f"[{title}] 父={fields['father']}({father_qid}) -> P22/P40を生成")
            else:
                if new_persons is not None:
                    new_persons.append({"name": fields["father"], "role": "father",
                                         "child_title": title, "child_qid": person_qid})
                    report.append(f"[{title}] 父={fields['father']} のWikidata項目が見つかりません。"
                                   f"新規作成コマンドを new_persons_all.tsv に出力しました(投入後に --family-only で再実行してください)。")
                else:
                    report.append(f"[{title}] 父={fields['father']} のWikidata項目が見つかりません"
                                   f"(Wikipedia記事・Wikidataラベル検索とも該当なし)。新規作成してから再実行してください。")

        adoptive_name = fields["adoptive_father"]
        adoptive_qid = None
        if adoptive_name:
            adoptive_qid = resolve_person_qid(adoptive_name)
            time.sleep(1.0)

        # ヒューリスティック: 養父の記載が無く、実父が先代と一致しないなら
        # 先代を養父として補完する。ただし以下の場合は補完しない:
        #   ・officeholders上は直前でも、実際のordinal(代数)が1つ違いに
        #     なっていない場合(resolve_officeholders()でQID未解決の代が
        #     スキップされており、「リスト上の前の要素」が実際の直前の代
        #     とは限らないため)
        #   ・先代と名字(最初の1文字)が異なる場合(藩主家そのものが交代した
        #     (改易・転封等)とみなし、お家の交代と養子縁組は別物であるため)
        #   ・実父はInfoboxに記載があるが、そのWikidata項目が見つからず
        #     father_qidがNoneのままの場合(実父が先代と同一人物かどうか
        #     判別できないので、誤って先代を養父とみなしてしまう恐れがある)
        # 先代のQIDは既に分かっているので、追加のAPI呼び出しは不要。
        if adoptive_name is None and i > 0:
            predecessor = officeholders[i - 1]
            is_adjacent = predecessor["ordinal"] == holder["ordinal"] - 1
            if not is_adjacent:
                report.append(f"[{title}] リスト上の直前は{predecessor['title']}ですが、"
                               f"間にWikidata項目未解決でスキップされた代があるため実際の先代とは限りません。"
                               f"養子関係の補完は行いません。手動で確認してください。")
            else:
                same_house = title[:1] == predecessor["title"][:1]
                if not same_house:
                    report.append(f"[{title}] 先代({predecessor['title']})と名字が異なるため、"
                                   f"藩主家の交代とみなし養子関係の補完は行いません。")
                elif fields["father"] and father_qid is None:
                    report.append(f"[{title}] 実父={fields['father']} のWikidata項目が見つからないため、"
                                   f"先代と同一人物かどうか判別できません。養子関係の補完は行いません。"
                                   f"実父の項目を作成してから再実行するか、手動で確認してください。")
                elif predecessor["qid"] == person_qid:
                    report.append(f"[{title}] 先代と同一人物(再任・藩知事就任など)のため、養子関係の補完は行いません。")
                elif father_qid is None:
                    report.append(f"[{title}] ★要確認: Infoboxに実父の記載が無いため、先代との関係は不明です。"
                                   f"養子関係の補完は行いません。手動で確認してください。")
                elif father_qid_of.get(i - 1) == father_qid:
                    report.append(f"[{title}] 先代({predecessor['title']})と実父が同じ(兄弟)なので、"
                                   f"養子関係の補完は行いません。")
                elif father_qid != predecessor["qid"]:
                    # 28組の実地確認で、祖父→孫の継承・別系統の同姓・兄弟(養父を共有)などを
                    # 養子と誤判定する例が見つかったため、コマンドは生成せず報告のみにした。
                    report.append(f"[{title}] ★要確認: 実父が先代({predecessor['title']})と一致しません。"
                                   f"養子の可能性がありますが、祖父→孫の継承や別系統の同姓の可能性もあるため、"
                                   f"コマンドは生成していません。記事で確認して手動で追加してください。")
                    adoptive_name = None
                    adoptive_qid = None
                if False:
                    adoptive_name = predecessor["title"]
                    adoptive_qid = predecessor["qid"]
                    report.append(f"[{title}] 実父が先代({predecessor['title']})と一致しないため、"
                                   f"先代を養父として補完しました(Infoboxに養父の明記なし・推定のため要確認)。")

        if adoptive_name:
            if adoptive_qid:
                commands.append([person_qid, "P1038", adoptive_qid, "P1039", Q_ADOPTIVE_PARENT])
                commands.append([adoptive_qid, "P1038", person_qid, "P1039", Q_ADOPTED_CHILD])
                report.append(f"[{title}] 養父={adoptive_name}({adoptive_qid}) -> P1038/P1039(養親)を生成")
            else:
                if holder["ordinal"] != 1:
                    report.append(f"[{title}] 養父={adoptive_name} のWikidata項目は見つかりませんが、"
                                   f"初代以外の養父は項目を作成しない方針のため、養子関係は生成しません。")
                elif new_persons is not None:
                    new_persons.append({"name": adoptive_name, "role": "adoptive_father",
                                         "child_title": title, "child_qid": person_qid})
                    report.append(f"[{title}] 養父={adoptive_name} のWikidata項目が見つかりません。"
                                   f"初代の養父のため、新規作成コマンドを new_persons_all.tsv に出力しました"
                                   f"(投入後に --family-only で再実行してください)。")
                else:
                    report.append(f"[{title}] 養父={adoptive_name} のWikidata項目が見つかりません"
                                   f"(Wikipedia記事・Wikidataラベル検索とも該当なし)。新規作成してから再実行してください。")

        for label, name in fields["other_relations"]:
            if fields["father"] is None and fields["adoptive_father"] is None:
                report.append(f"[{title}] ★要確認: 父・養父の代わりに「{label}：{name}」が見つかりました。"
                               f"コマンドは生成していません。関係の種類(P1039の値)を人間が判断のうえ、手動で追加してください。")

    return commands, report


def _label_without_disambiguation(name: str) -> str:
    """「松平信明 (三河吉田藩主)」のような曖昧さ回避の括弧を除いた、Wikidataラベル用の名前。"""
    return re.sub(r"\s*[（(][^）)]*[）)]\s*$", "", name).strip()


def build_new_person_commands(new_persons: list[dict]) -> list[list[str]]:
    """
    Wikidata項目が無かった父(と初代の養父)を新規作成するコマンド列を作る。
    値の位置に LAST は使わない(赤穂藩で422エラーになったため)。LASTは主語のみ。
    子の側へのP22/養子関係は、投入後に draft-family を再実行すると
    ラベル検索で新項目が見つかり、通常の経路で生成される。
    同一人物が複数の藩主の父になっている場合は、1項目にまとめて子を全員P40に入れる。
    説明文は「<子>の父」とし、ラベル+説明の組を他の項目と重複させない。
    """
    grouped: dict[tuple[str, str], list[dict]] = {}
    for np_ in new_persons:
        grouped.setdefault((np_["name"], np_["role"]), []).append(np_)
    commands: list[list[str]] = []
    for (name, role), entries in grouped.items():
        label = _label_without_disambiguation(name)
        children = [e["child_title"] for e in entries]
        relation = "父" if role == "father" else "養父"
        desc = f"{_label_without_disambiguation(children[0])}の{relation}"
        commands.append(["CREATE"])
        commands.append(["LAST", "Lja", f'"{label}"'])
        commands.append(["LAST", "Dja", f'"{desc}"'])
        commands.append(["LAST", "P31", Q_HUMAN])
        commands.append(["LAST", "P21", Q_MALE])
        for e in entries:
            if role == "father":
                commands.append(["LAST", "P40", e["child_qid"]])
            else:
                commands.append(["LAST", "P1038", e["child_qid"], "P1039", Q_ADOPTED_CHILD])
    return commands


NEW_PERSONS_ALL_PATH = "new_persons_all.tsv"


def write_new_persons_tsv(han_title: str, new_persons: list[dict]) -> str | None:
    """
    新規作成が必要な人物を <藩名>_new_persons.json に保存する(空なら空リストで上書き)。
    実際に投入するTSVは全藩分を1ファイルにまとめた new_persons_all.tsv で、
    merge_new_persons() が全藩のJSONから作り直す。JSONを毎回上書きするのは、
    項目作成後の再実行で「作成不要」になった藩の古い候補が残って、
    二重に作成されてしまうのを防ぐため。戻り値は作成が必要なときのみ new_persons_all.tsv のパス。
    """
    import json
    with open(f"{han_title}_new_persons.json", "w", encoding="utf-8") as f:
        json.dump(new_persons, f, ensure_ascii=False, indent=1)
    merge_new_persons()
    return NEW_PERSONS_ALL_PATH if new_persons else None


def merge_new_persons(out_path: str = NEW_PERSONS_ALL_PATH) -> int:
    """
    カレントフォルダの *_new_persons.json をすべて集め、同一人物(名前+役割)は1項目に
    まとめて、1つのQuickStatements用TSV(new_persons_all.tsv)に書き出す。
    戻り値は作成する人数。0人のときは空のファイルになる。
    """
    import glob
    import json
    merged: list[dict] = []
    for path in sorted(glob.glob("*_new_persons.json")):
        with open(path, encoding="utf-8") as f:
            merged += json.load(f)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(commands_to_tsv(build_new_person_commands(merged)))
    return len({(m["name"], m["role"]) for m in merged})


# ---------------------------------------------------------------------------
# 各藩主個人の項目に付与するステートメント
# ---------------------------------------------------------------------------

Q_HUMAN = "Q5"
Q_MALE = "Q6581097"


def build_person_basic_commands(person_qid: str, name_ja: str) -> list[list[str]]:
    """
    追加リスクの低い基本プロパティのみを生成する。

    P21(性別)は、江戸時代の藩主という制度上そもそも男性しか就けない
    職であることを前提に、一律で男性(Q6581097)にしている。
    P53(家系)・P97(位階)は藩や代によって例外があり得るため
    (峰山藩9代高鎮のようなケース)、ここでは意図的に含めていない。
    藩ごとの家系QIDと位階の慣習を確認したうえで別途追加すること。
    """
    return [
        [person_qid, "P31", Q_HUMAN],
        [person_qid, "P21", Q_MALE],
        [person_qid, "P1559", f'ja:"{name_ja}"'],
    ]


def build_person_position_commands(
    person_qid: str,
    position_qid: str,
    start_year: int | None,
    end_year: int | None,
    replaces_qid: str | None,
    replaced_by_qid: str | None,
) -> list[list[str]]:
    """
    各藩主の項目にP39(在職した藩主役職)を、開始・終了年、
    前任者(P1365)・後任者(P1366)の修飾子付きで追加するコマンドを組み立てる。
    """
    qualifiers: list[str] = []
    if start_year is not None:
        qualifiers += ["P580", _year_to_qs_date(start_year)]
    if end_year is not None:
        qualifiers += ["P582", _year_to_qs_date(end_year)]
    if replaces_qid is not None:
        qualifiers += ["P1365", replaces_qid]
    if replaced_by_qid is not None:
        qualifiers += ["P1366", replaced_by_qid]
    return [[person_qid, "P39", position_qid, *qualifiers]]


def build_all_person_statements(position_qid: str, officeholders: list[dict]) -> list[list[str]]:
    """
    officeholders(在職順、qid/title/start_year/end_year/ordinal込み)から、
    各人物の基本プロパティ + P39ブロックを一括生成する。
    P1365/P1366(前任者・後任者)はリスト内の前後の要素から求めるが、
    resolve_officeholders()でQID未解決の代がスキップされていることが
    あるため、単純にリスト上の前後の要素を使うのではなく、ordinal
    (本来の代数)が実際に1つ違いになっている場合のみ前任者・後任者と
    みなす(間に欠番があるときは、リスト上は隣接していても実際には
    直接の前任・後任関係ではないため、P1365/P1366を付与しない)。
    """
    commands: list[list[str]] = []
    n = len(officeholders)
    for i, holder in enumerate(officeholders):
        commands += build_person_basic_commands(holder["qid"], holder["title"])

        predecessor = officeholders[i - 1] if i > 0 else None
        replaces_qid = (
            predecessor["qid"]
            if predecessor is not None and predecessor["ordinal"] == holder["ordinal"] - 1
            else None
        )
        successor = officeholders[i + 1] if i < n - 1 else None
        replaced_by_qid = (
            successor["qid"]
            if successor is not None and successor["ordinal"] == holder["ordinal"] + 1
            else None
        )

        commands += build_person_position_commands(
            person_qid=holder["qid"],
            position_qid=position_qid,
            start_year=holder["start_year"],
            end_year=holder["end_year"],
            replaces_qid=replaces_qid,
            replaced_by_qid=replaced_by_qid,
        )
    return commands


# ---------------------------------------------------------------------------
# 共通処理:テンプレートから在職者一覧(QID込み)を取得する
# ---------------------------------------------------------------------------

def resolve_officeholders(han_title: str) -> list[dict]:
    """
    Template:○○藩主から在職者一覧を取得し、各人物のQIDまで解決する。

    各人物の辞書には、テンプレート内での出現順そのものを"ordinal"(代数)
    として持たせる。Wikidata項目が見つからず除外(スキップ)された人物が
    いても、後に続く人物のordinalは詰め直さない。詰め直してしまうと、
    スキップされた代より後の全員のP1545(系列内での順序)が実際の代数と
    ずれてしまうため。
    """
    print(f"Template:{han_title}主 を取得・パース中...")
    wikitext = get_template_wikitext(han_title)
    officeholders_raw = parse_officeholders_with_years(wikitext)
    for w in LAST_PARSE_WARNINGS:
        print(f"  !! 警告(年の解析): {w}")
    print(f"  -> {len(officeholders_raw)} 名を抽出:")
    for h in officeholders_raw:
        print(f"     {h['title']}: {h['start_year']}-{h['end_year']}")
    if not officeholders_raw:
        raise SystemExit(
            "在職者を1件も抽出できませんでした。Template:" + han_title + "主 の実際の"
            "書式を確認し、_LINK_YEAR_PATTERNS に新しいパターンを追加してください"
            "(これまでに小城藩の <small>年-年</small> 形式が確認済みです)。"
        )

    print("各在職者のQIDを解決中...")
    officeholders = []
    skipped_ordinals = []
    for ordinal, h in enumerate(officeholders_raw, start=1):
        qid = title_to_qid(h["title"])
        if qid is None:
            print(f"  !! 警告: {h['title']}(本来の代数: {ordinal}代) のWikidata項目が見つかりません。スキップします。")
            skipped_ordinals.append(ordinal)
            continue
        officeholders.append({**h, "qid": qid, "ordinal": ordinal})
        time.sleep(1.0)  # APIへの配慮(429対策でリトライも入れたが、間隔自体も広げた)
    if skipped_ordinals:
        print(f"  !! 注意: {len(skipped_ordinals)}件(代数: {', '.join(map(str, skipped_ordinals))})が"
              "スキップされました。これらの代を挟む前後の人物同士は、実際には直接の前任・後任関係とは"
              "限らないため、P1365/P1366(前任者・後任者)や養子関係の自動補完を行いません。")
    return officeholders


def load_qids_by_ordinal_from_position_tsv(path: str) -> dict[int, str]:
    """
    create-positionが出力したTSVのP1308行から、
    「系列内での順序(P1545)」→ QID のマッピングを復元する。

    add-person-statements実行時にこれを使えば、Wikidataへ
    タイトル→QID解決を再度問い合わせずに済む。11人分を毎回
    問い合わせ直すのはAPIへの負荷が無駄に大きく、429エラーの
    原因にもなっていたため、一度取得済みのQIDはファイルから
    再利用する設計にした。
    """
    ordinal_to_qid: dict[int, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 5 or fields[1] != "P1308":
                continue
            qid = fields[2]
            if "P1545" not in fields:
                continue
            ordinal_idx = fields.index("P1545") + 1
            ordinal = int(fields[ordinal_idx].strip('"'))
            ordinal_to_qid[ordinal] = qid
    return ordinal_to_qid


def resolve_officeholders_from_tsv(han_title: str, position_tsv_path: str) -> list[dict]:
    """
    Wikipediaのテンプレートを再パースして順序・タイトル・在任年を取り直す
    (これは軽いWikipedia側のAPI呼び出し1回で済む)一方、QIDだけは
    create-positionが既に出力したTSVから復元する。
    """
    print(f"Template:{han_title}主 を取得・パース中...")
    wikitext = get_template_wikitext(han_title)
    officeholders_raw = parse_officeholders_with_years(wikitext)
    for w in LAST_PARSE_WARNINGS:
        print(f"  !! 警告(年の解析): {w}")
    print(f"  -> {len(officeholders_raw)} 名を抽出")
    if not officeholders_raw:
        raise SystemExit(f"在職者を1件も抽出できませんでした: Template:{han_title}主")

    print(f"{position_tsv_path} からQIDを復元中...")
    ordinal_to_qid = load_qids_by_ordinal_from_position_tsv(position_tsv_path)

    officeholders = []
    for ordinal, h in enumerate(officeholders_raw, start=1):
        qid = ordinal_to_qid.get(ordinal)
        if qid is None:
            print(f"  !! 警告: 順序{ordinal}({h['title']})のQIDが{position_tsv_path}に見つかりません。スキップします。")
            continue
        officeholders.append({**h, "qid": qid, "ordinal": ordinal})
    return officeholders


# ---------------------------------------------------------------------------
# サブコマンド1: 「○○藩主」役職項目の新規作成
# ---------------------------------------------------------------------------

def run_create_position(han_title: str, province: str) -> None:
    print(f"[1/3] {han_title} のQIDを解決中...")
    han_qid = title_to_qid(han_title)
    if han_qid is None:
        raise SystemExit(f"{han_title} のWikidata項目が見つかりません。手動で確認してください。")
    print(f"  -> {han_qid}")

    print(f"[2/3] 在職者一覧を取得中...")
    officeholders = resolve_officeholders(han_title)

    print(f"[3/3] Template/Category項目のQIDを解決中...")
    template_qid = title_to_qid(f"Template:{han_title}主")
    category_qid = title_to_qid(f"Category:{han_title}主")
    print(f"  -> Template: {template_qid}, Category: {category_qid}")
    if template_qid is None or category_qid is None:
        print("  !! Template/Categoryの一方または両方が見つかりませんでした。")
        print("     既に存在するはずとの前提だったので、名称の揺れがないか確認してください。")

    commands = build_han_lord_position_commands(
        han_title=han_title,
        han_qid=han_qid,
        province=province,
        officeholders=officeholders,
        template_qid=template_qid,
        category_qid=category_qid,
    )

    tsv = commands_to_tsv(commands)
    out_path = f"{han_title}_position_create.tsv"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(tsv)

    print("\n生成したQuickStatements V1コマンド(先頭10行):")
    print("\n".join(tsv.splitlines()[:10]))
    print(f"\n全文を {out_path} に保存しました。")
    print("内容を目視確認したうえで、https://quickstatements.toolforge.org/ に貼り付けて投入してください。")
    print("(このスクリプトはWikidataへの書き込みを一切行いません。生成のみです。)")
    print(f"\n次のステップ: 実際に投入して発行されたQIDを控え、")
    print(f"  python {__file__.split('/')[-1]} add-person-statements {han_title} <発行されたQID>")
    print("  で各藩主個人の項目にP39等を追加できます。")


# ---------------------------------------------------------------------------
# サブコマンド2: 各藩主個人の項目にデータを追加
# ---------------------------------------------------------------------------

def run_add_person_statements(han_title: str, position_qid: str, position_tsv_path: str | None = None) -> None:
    """
    役職項目が実際に作成されQIDが判明した後の第2段階。
    以下の2つをまとめて1本のTSVに出力する:
      - 藩・Template・Categoryから役職項目への逆リンク(実QIDを値に使う)
      - 各藩主個人へのP31/P21/P1559/P39

    値の位置に"LAST"を使うとQuickStatementsでError 422になり、以降の
    LAST参照も連鎖的に無効になることが赤穂藩での実投入で判明したため、
    ここでは常に実際のQID文字列(position_qidや、これから解決するhan_qid等)
    を使う。
    """
    position_tsv_path = position_tsv_path or f"{han_title}_position_create.tsv"

    print(f"[1/3] {han_title}・Template・CategoryのQIDを解決中...")
    han_qid = title_to_qid(han_title)
    if han_qid is None:
        raise SystemExit(f"{han_title} のWikidata項目が見つかりません。手動で確認してください。")
    template_qid = title_to_qid(f"Template:{han_title}主")
    category_qid = title_to_qid(f"Category:{han_title}主")
    print(f"  -> 藩: {han_qid}, Template: {template_qid}, Category: {category_qid}")

    print(f"[2/3] 在職者一覧を取得中(QIDは {position_tsv_path} から復元)...")
    officeholders = resolve_officeholders_from_tsv(han_title, position_tsv_path)

    print(f"[3/3] コマンドを組み立て中...")
    reciprocal_commands = build_reciprocal_link_commands(position_qid, han_qid, template_qid, category_qid)
    person_commands = build_all_person_statements(position_qid, officeholders)
    commands = reciprocal_commands + person_commands

    tsv = commands_to_tsv(commands)
    out_path = f"{han_title}_person_statements.tsv"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(tsv)

    print("\n生成したQuickStatements V1コマンド(先頭10行):")
    print("\n".join(tsv.splitlines()[:10]))
    print(f"\n全文を {out_path} に保存しました。")
    print("内容を目視確認したうえで、https://quickstatements.toolforge.org/ に貼り付けて投入してください。")
    print("(このスクリプトはWikidataへの書き込みを一切行いません。生成のみです。)")
    print("\n※ P53(家系)・P97(位階)はこのコマンドには含まれていません。")
    print("  藩ごとに家系のQIDと位階の慣習(例外の有無)を確認したうえで、別途追加してください。")


# ---------------------------------------------------------------------------
# サブコマンド4: 家系関係(父・養父)のドラフト生成
# ---------------------------------------------------------------------------

def run_draft_family(han_title: str) -> None:
    print(f"[1/2] 在職者一覧を取得中...")
    officeholders = resolve_officeholders(han_title)

    print(f"[2/2] 各在職者の記事から父・養父を抽出中...")
    new_persons: list[dict] = []
    commands, report = build_family_relation_draft(officeholders, new_persons)
    new_path = write_new_persons_tsv(han_title, new_persons)

    tsv = commands_to_tsv(commands)
    tsv_path = f"{han_title}_family_draft.tsv"
    with open(tsv_path, "w", encoding="utf-8") as f:
        f.write(tsv)

    report_path = f"{han_title}_family_draft_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print("\n抽出結果:")
    print("\n".join(report))
    print(f"\nQuickStatementsドラフトを {tsv_path} に、")
    print(f"レビュー用レポートを {report_path} に保存しました。")
    print("\n【重要】これは投入前に必ず人間によるレビューが必要なドラフトです:")
    print("  - 養父の関係はすべて「養親」で統一しており、婿養子かどうかの判別は行っていません。")
    if new_path:
        print(f"  - 項目が無かった父(と初代の養父)の作成コマンドを {new_path}(全藩分を1ファイルに集約)に保存しました。")
        print(f"    QuickStatementsに投入したあと、python run_batch_prepare.py --force --family-only {han_title} を実行すると、")
        print("    新項目が見つかって子側のP22等が生成されます(反映に数分かかる場合があります)。")


# ---------------------------------------------------------------------------
# サブコマンド5: 1藩分の「QID確定前にできる作業」をまとめて実行する
# ---------------------------------------------------------------------------

def run_prepare_han(han_title: str, province: str) -> None:
    """
    1藩分の作業のうち、役職項目のQIDがまだ判明していない段階でも進められる
    部分(create-position + draft-family)をまとめて1回の実行で行う。

    在職者一覧(officeholders)はテンプレートの取得・QID解決を含む重い処理
    なので、ここで一度だけ取得し、役職項目用のコマンド生成と家系ドラフト
    生成の両方に使い回す。

    【重要】人物側のP39・逆リンク(P2388/P1423/P301)は、値の位置に
    "LAST"を使うとQuickStatementsで失敗することが赤穂藩での実投入で
    判明したため、ここには含めない。①のTSVを実際に投入し、発行された
    QIDを確認したうえで、add-person-statementsを実行すること。
    """
    print(f"[1/4] {han_title} のQIDを解決中...")
    han_qid = title_to_qid(han_title)
    if han_qid is None:
        raise SystemExit(f"{han_title} のWikidata項目が見つかりません。手動で確認してください。")
    print(f"  -> {han_qid}")

    print(f"[2/4] 在職者一覧を取得中(役職項目・家系ドラフトの両方で使い回す)...")
    officeholders = resolve_officeholders(han_title)

    print(f"[3/4] Template/Category項目のQIDを解決中...")
    template_qid = title_to_qid(f"Template:{han_title}主")
    category_qid = title_to_qid(f"Category:{han_title}主")
    print(f"  -> Template: {template_qid}, Category: {category_qid}")
    if template_qid is None or category_qid is None:
        print("  !! Template/Categoryの一方または両方が見つかりませんでした。")
        print("     既に存在するはずとの前提だったので、名称の揺れがないか確認してください。")

    position_commands = build_han_lord_position_commands(
        han_title=han_title,
        han_qid=han_qid,
        province=province,
        officeholders=officeholders,
        template_qid=template_qid,
        category_qid=category_qid,
    )
    position_tsv = commands_to_tsv(position_commands)
    position_path = f"{han_title}_position_create.tsv"
    with open(position_path, "w", encoding="utf-8") as f:
        f.write(position_tsv)

    print(f"[4/4] 父・養父関係をドラフト生成中...")
    new_persons: list[dict] = []
    family_commands, family_report = build_family_relation_draft(officeholders, new_persons)
    new_path = write_new_persons_tsv(han_title, new_persons)
    if new_path:
        print(f"  -> 新規作成が必要な父: {new_path}")
    family_tsv = commands_to_tsv(family_commands)
    family_tsv_path = f"{han_title}_family_draft.tsv"
    with open(family_tsv_path, "w", encoding="utf-8") as f:
        f.write(family_tsv)
    family_report_path = f"{han_title}_family_draft_report.txt"
    with open(family_report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(family_report))

    print("\n===== ① 役職項目の作成(まずこちらだけ投入する) =====")
    print("\n".join(position_tsv.splitlines()[:10]))
    print(f"...(全{len(position_commands)}行)")
    print(f"-> {position_path} に保存しました。")

    print("\n===== ② 父・養父関係のドラフト(①とは独立、いつ投入してもよい) =====")
    print("\n".join(family_report))
    print(f"-> コマンド: {family_tsv_path}")
    print(f"-> レポート: {family_report_path}")

    print("\n【重要】このスクリプトはWikidataへの書き込みを一切行いません。生成のみです。")
    print(f"①を実際に投入して発行されたQIDを控えたら、次はこちらを実行してください:")
    print(f"  python {__file__.split('/')[-1]} add-person-statements {han_title} <発行されたQID>")
    print("  (これで逆リンク3本と各藩主個人へのP31/P21/P1559/P39が生成されます)")
    print("※ P53(家系)・P97(位階)、および②の「★要確認」「見つかりません」の行は")
    print("  いずれのコマンドにも含まれていないので、別途対応してください。")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="edo-daimyo-genealogy: 藩主関連のWikidata項目をQuickStatements V1形式で生成する"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p0 = sub.add_parser(
        "prepare-han",
        help="1藩分の役職項目作成(TSV)と家系ドラフト生成をまとめて実行する(通常はこちらを推奨)",
    )
    p0.add_argument("han_title", help="藩のWikipedia記事タイトル(例: 小城藩)")
    p0.add_argument("province", help="旧国名(例: 肥前国)")

    p1 = sub.add_parser("create-position", help="「○○藩主」役職項目のみを新規作成する")
    p1.add_argument("han_title", help="藩のWikipedia記事タイトル(例: 小城藩)")
    p1.add_argument("province", help="旧国名(例: 肥前国)")

    p2 = sub.add_parser(
        "add-person-statements",
        help="役職項目のQIDが判明した後の第2段階(逆リンク+各藩主個人へのP39等)を生成する",
    )
    p2.add_argument("han_title", help="藩のWikipedia記事タイトル(例: 小城藩)")
    p2.add_argument("position_qid", help="役職項目のQID(例: Q123456。峰山藩ならQ141515630)")
    p2.add_argument(
        "--position-tsv",
        default=None,
        help="create-positionが出力したTSVのパス(省略時は '<藩名>_position_create.tsv' を使う)",
    )

    p3 = sub.add_parser(
        "draft-family",
        help="各藩主の記事Infoboxから父・養父の関係をドラフト生成する(要人間レビュー)",
    )
    p3.add_argument("han_title", help="藩のWikipedia記事タイトル(例: 小城藩)")

    sub.add_parser(
        "merge-new-persons",
        help="全藩の <藩名>_new_persons.json を1つの new_persons_all.tsv にまとめ直す",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "prepare-han":
        run_prepare_han(args.han_title, args.province)
    elif args.command == "create-position":
        run_create_position(args.han_title, args.province)
    elif args.command == "add-person-statements":
        run_add_person_statements(args.han_title, args.position_qid, args.position_tsv)
    elif args.command == "draft-family":
        run_draft_family(args.han_title)
    elif args.command == "merge-new-persons":
        n = merge_new_persons()
        print(f"{n}人分を {NEW_PERSONS_ALL_PATH} に書き出しました。")


if __name__ == "__main__":
    main()

