"""
edo-daimyo-genealogy: 御三卿(田安・一橋・清水)の「○○徳川家当主」役職項目を生成するスクリプト

create_han_lord_position.py(藩主用)の御三卿版。藩主版との違いは次の5点で、
HTTP取得・QID解決・家系ドラフトなどの共通処理は create_han_lord_position.py をそのまま使う。

  1. 各当主には「何代目か」(P1545)に加えて在任期間(P580/P582、年のみ)を付ける。
     年の取得元は、(a) テンプレート内の <small>年-年</small>(藩主版と同じ書式の場合)、
     (b) --years で渡すTSV、の順。どちらも無い当主は年なしになり、記入用の
     <家名>_years_template.tsv を出力する。御三卿としての在任は1871年で区切るため、
     最後の当主の終了年は1871年に丸める(--last で区切った場合も、区切らない場合も)。
  2. 「藩」ではなく「○○徳川家」の項目に役職項目をぶら下げる(P2389 / 逆方向P2388)。
  3. 役職項目のラベルは「○○徳川家当主」(藩主版は「○○藩主」)。P279(近世大名)は付けない
     (御三卿の当主は大名ではないため)。
  4. 御三卿は1871年で区切る。--last で指定した当主までを在職者とし、それ以降の当主は含めない。
     役職項目には廃止時点として P576(1871年)を付ける。
  5. 当主不在の期間(前の当主の終了年より後に始まる当主)を挟む「先代→当主」には養子関係を作らない
     (家系ドラフトから取り除き、レポートに理由を書く)。

【重要】Wikidataへの書き込みは一切行わない。QuickStatements V1形式のTSVを出力するだけ。
値の位置に"LAST"を使うとError 422になる制約(赤穂藩で確認)があるため、藩主版と同じく
2段階構成にしている。

実行方法(code/ フォルダで実行):
    # 第1段階: 役職項目の作成TSV + 家系ドラフト(QID確定前にできる作業)
    python create_gosankyo_position.py prepare 田安徳川家
    python create_gosankyo_position.py prepare 一橋徳川家
    python create_gosankyo_position.py prepare 清水徳川家
    #   -> <家名>_position_create.tsv をQuickStatementsに投入し、発行されたQIDを控える

    # 第2段階: 発行されたQIDを使って、逆リンク+各当主個人のP31/P21/P1559/P39(P1545付き)を生成
    python create_gosankyo_position.py person-statements 田安徳川家 Q123456

テンプレートは Template:○○徳川家、カテゴリは Category:○○徳川家当主(既定値)。
御三卿としての当主は1871年で区切る(家そのものはその後も続くため、テンプレートには
1871年以降の当主も載っている)。区切りは --last で「御三卿として最後の当主」を指定する:
    python create_gosankyo_position.py prepare 田安徳川家 --last 徳川達孝     # 人名で指定
    python create_gosankyo_position.py prepare 田安徳川家 --last 7            # 代数で指定
人名(記事タイトル)と在任年をTSVに直接書いて渡す場合(Wikipediaのテンプレートは読まない):
    python create_gosankyo_position.py prepare 田安徳川家 --from-tsv 田安徳川家_input.tsv
    (TSVの列: 代数 / 記事タイトル / 開始年 / 終了年。代数は1から連番。#で始まる行は無視。
     当主不在の期間は人物ではないので行にしない。同じ人物が再び当主になる場合(再襲)は、
     同じ代数で2行書く(例: 9代 徳川慶喜 を2行)。次の人物は代数+1になる)
prepare 済みで、在任年だけ後から足す場合(ネットワーク不要。QIDは <家名>_holders.json から復元):
    python create_gosankyo_position.py apply-years 田安徳川家 田安徳川家_input.tsv
    (holders.json と <家名>_position_create.tsv を在任年入りで作り直す。代数と記事タイトルが
     holders.json と一致しない行があれば中断する)
在任年がテンプレートに無い場合は、<家名>_years_template.tsv に年を記入し、--years で渡す:
    python create_gosankyo_position.py prepare 田安徳川家 --last 7 --years 田安徳川家_years_template.tsv
    (TSVの列: 代数 / 人名 / 開始年 / 終了年。人名は確認用で、照合には代数を使う。#で始まる行は無視)
テンプレートの当主欄(group)の見出しが「当主」でない場合は --group で指定する。
別のテンプレートを使う場合は --template を指定する。
テンプレートを使わず、代数順の人名を直接渡す場合(ここで渡した順番がそのまま1代目、2代目...になる):
    python create_gosankyo_position.py prepare 田安徳川家 --names 田安宗武 田安治察 徳川斉匡 ...
テンプレート内の人物以外のリンク(関連項目など)が混ざった場合は --exclude で除外する。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time

import create_han_lord_position as base

GOSANKYO = ["田安徳川家", "一橋徳川家", "清水徳川家"]
GOSANKYO_END_YEAR = 1871  # 御三卿としての当主はここで区切る(家自体はその後も続く)


# ---------------------------------------------------------------------------
# テンプレートから「代数順の人物リスト」だけを抽出する(在任年は読まない)
# ---------------------------------------------------------------------------

# navboxの見出し・グループ名・装飾のパラメータ行。ここに含まれるリンクは当主ではないので読み飛ばす。
_NON_LIST_PARAM_RE = re.compile(
    r"^\s*\|\s*(?:title|name|above|below|group\d*|image|state|style|titlestyle|"
    r"groupstyle|liststyle|navbar|bodyclass)\s*=", re.IGNORECASE)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
_NAMESPACE_RE = re.compile(r"^(?:Category|カテゴリ|File|ファイル|Image|画像|Template|テンプレート|Wikipedia|WP|Help|ヘルプ|Portal|プロジェクト):", re.IGNORECASE)


_PARAM_START_RE = re.compile(r"^\s*\|\s*([A-Za-z_]+\d*)\s*=(.*)$")


def split_navbox_params(wikitext: str) -> dict[str, str]:
    """行頭の |name = ... で始まるnavboxパラメータを {name: 複数行の値} に分ける。"""
    params: dict[str, str] = {}
    current: str | None = None
    for line in _COMMENT_RE.sub("", wikitext).splitlines():
        m = _PARAM_START_RE.match(line)
        if m:
            current = m.group(1).lower()
            params[current] = m.group(2)
        elif current is not None:
            params[current] += "\n" + line
    return params


def extract_group_section(wikitext: str, group_label: str) -> str | None:
    """
    navboxの groupN の値に group_label(例: "当主")を含む行を探し、対応する listN の本文を返す。
    見つからなければ None(呼び出し側がテンプレート全体にフォールバックし、警告する)。
    """
    params = split_navbox_params(wikitext)
    for key, value in params.items():
        m = re.fullmatch(r"group(\d+)", key)
        if m and group_label in value:
            return params.get(f"list{m.group(1)}")
    return None


def truncate_at_last(titles: list[str], last: str) -> list[str]:
    """
    last(人名 or 代数の数字)までを残し、それ以降を捨てる。
    人名が複数回出る場合は、最後に出た位置までを残す(再任後の就任を含めるため)。
    """
    if last.isdigit():
        n = int(last)
        if not 1 <= n <= len(titles):
            raise SystemExit(f"--last {n} は範囲外です(抽出できたのは {len(titles)} 名)。")
        return titles[:n]
    idx = [i for i, t in enumerate(titles) if t == last]
    if not idx:
        raise SystemExit(f"--last {last} が抽出結果の中に見つかりません。")
    return titles[: idx[-1] + 1]


def extract_ordered_titles(wikitext: str, exclude: set[str]) -> list[str]:
    """
    wikitext中の [[リンク]] を出現順に返す。出現順がそのまま代数になる。

    除外するもの: HTMLコメント、見出し行(title=/group=等)、名前空間付きリンク、
    exclude に指定されたタイトル。重複(同じ人物が2回載っている=再任など)は
    落とさずそのまま残す(落とすと以降の代数がずれるため)。呼び出し側が警告を出す。
    """
    text = _COMMENT_RE.sub("", wikitext)
    titles: list[str] = []
    for line in text.splitlines():
        if _NON_LIST_PARAM_RE.match(line):
            continue
        for m in _LINK_RE.finditer(line):
            title = m.group(1).strip()
            if _NAMESPACE_RE.match(title) or title in exclude:
                continue
            titles.append(title)
    return titles


def default_template_title(family: str) -> str:
    return f"Template:{family}"  # テンプレートは「○○徳川家」(カテゴリだけが「○○徳川家当主」)


def load_years_file(path: str) -> dict[int, tuple[int | None, int | None]]:
    """TSV(代数<TAB>人名<TAB>開始年<TAB>終了年)を {代数: (開始年, 終了年)} に読む。空欄はNone。"""
    years: dict[int, tuple[int | None, int | None]] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            cols = line.split("\t")
            if not cols[0].strip().isdigit():
                continue  # ヘッダ行
            def to_year(i: int) -> int | None:
                v = cols[i].strip() if len(cols) > i else ""
                return int(v) if v.isdigit() else None
            years[int(cols[0])] = (to_year(2), to_year(3))
    return years


def load_input_tsv(path: str) -> list[dict]:
    """
    --from-tsv / apply-years 用。代数/記事タイトル/開始年/終了年のTSVを行ごとに読む。
    戻り値: [{"ordinal", "title", "start_year", "end_year"}, ...](ファイルの行順)。

    代数は1から始め、前の行+1にする。ただし前の行と同じ人物が再び当主になる場合(再襲)に限り、
    前の行と同じ代数を許す(例: 9代の徳川慶喜が2行)。それ以外で連番が崩れていたら、
    ずれた代数のままP1545に入ってしまうのを防ぐため中断する。
    """
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            cols = line.rstrip("\n").split("\t")
            if not line.strip() or line.lstrip().startswith("#") or not cols[0].strip().isdigit():
                continue
            ordinal = int(cols[0])
            title = cols[1].strip() if len(cols) > 1 else ""
            if not title:
                raise SystemExit(f"{path}: {ordinal}代の記事タイトルが空です。")
            prev = rows[-1] if rows else None
            expected = (prev["ordinal"] + 1) if prev else 1
            if ordinal != expected and not (prev and ordinal == prev["ordinal"] and title == prev["title"]):
                raise SystemExit(f"{path}: 代数が連番ではありません({ordinal}代の行。期待は {expected}代。"
                                 "同じ人物の再襲なら、同じ代数・同じ記事タイトルで書いてください)。")
            def to_year(i: int) -> int | None:
                v = cols[i].strip() if len(cols) > i else ""
                return int(v) if v.isdigit() else None
            rows.append({"ordinal": ordinal, "title": title,
                         "start_year": to_year(2), "end_year": to_year(3)})
    return rows


def years_from_template(section: str, titles: list[str]) -> dict[int, tuple[int | None, int | None]]:
    """
    当主欄に <small>年-年</small> があれば、代数順に年を取り出す(藩主版のパーサを流用)。
    人名の並びが抽出済みの titles と完全に一致する場合のみ採用する(再任で1人が複数期間を持つ等、
    対応がずれる可能性があるときは、誤った年を付けるより付けない方を選ぶ)。
    """
    parsed = base.parse_officeholders_with_years(section)
    for w in base.LAST_PARSE_WARNINGS:
        print(f"  !! 警告(年の解析): {w}")
    if not parsed:
        return {}
    if [p["title"] for p in parsed][:len(titles)] != titles or len(parsed) < len(titles):
        print("  !! テンプレート内の年と人名の並びが対応しないため、テンプレートの年は使いません(--years で渡してください)。")
        return {}
    return {i: (p["start_year"], p["end_year"]) for i, p in enumerate(parsed[:len(titles)], start=1)}


def apply_end_cutoff(holders: list[dict]) -> None:
    """
    御三卿としての在任は GOSANKYO_END_YEAR で区切る。最後の当主の終了年が空、または
    それ以降なら GOSANKYO_END_YEAR に丸める。それ以外の当主の終了年が区切り年を
    超えている場合は、データの誤りの可能性があるので警告だけ出す(書き換えない)。
    """
    if not holders:
        return
    last = holders[-1]
    if last["end_year"] is None or last["end_year"] > GOSANKYO_END_YEAR:
        print(f"  -> 最後の当主 {last['title']} の終了年を {last['end_year']} -> {GOSANKYO_END_YEAR} に丸めました(御三卿としての区切り)。")
        last["end_year"] = GOSANKYO_END_YEAR
    for h in holders[:-1]:
        if h["end_year"] is not None and h["end_year"] > GOSANKYO_END_YEAR:
            print(f"  !! 警告: {h['title']} の終了年 {h['end_year']} が{GOSANKYO_END_YEAR}年より後です。確認してください。")


def mark_vacancies(holders: list[dict]) -> None:
    """
    直前の当主の終了年より後に開始している当主に vacancy_before=True を付ける(当主不在の期間を挟む)。
    御三卿は当主不在の期間があり、その前後の当主は先代からの継承ではないため、
    先代との養子関係を作ってはいけない(drop_vacancy_adoptions で取り除く)。
    """
    for i, h in enumerate(holders):
        prev = holders[i - 1] if i > 0 else None
        h["vacancy_before"] = bool(
            prev and prev.get("row", prev["ordinal"]) == h.get("row", h["ordinal"]) - 1
            and prev["end_year"] is not None and h["start_year"] is not None
            and h["start_year"] > prev["end_year"])


def drop_vacancy_adoptions(holders: list[dict], commands: list[list[str]],
                           report: list[str]) -> tuple[list[list[str]], list[str]]:
    """
    当主不在の期間を挟む「先代→当主」の組について、家系ドラフトから養子関係(P1038/P1039)と、
    先代との関係を述べたレポート行(★要確認など)を取り除き、不在期間による除外であることを書き添える。
    実父(P22/P40)は影響を受けない。同一人物の再襲(先代=本人)は対象外。
    """
    drop_pairs: set[frozenset] = set()
    notes: dict[str, tuple[dict, dict]] = {}
    for i, h in enumerate(holders):
        if i > 0 and h.get("vacancy_before") and holders[i - 1]["qid"] != h["qid"]:
            drop_pairs.add(frozenset((h["qid"], holders[i - 1]["qid"])))
            notes[h["title"]] = (holders[i - 1], h)
    if not notes:
        return commands, report
    new_cmds = [c for c in commands
                if not (len(c) >= 3 and c[1] == "P1038" and frozenset((c[0], c[2])) in drop_pairs)]
    new_report: list[str] = []
    done: set[str] = set()
    for line in report:
        hit = next((t for t, (prev, _) in notes.items()
                    if line.startswith(f"[{t}]") and ("先代(" in line or f"養父={prev['title']}" in line)), None)
        if hit is None:
            new_report.append(line)
            continue
        if hit not in done:
            done.add(hit)
            prev, cur = notes[hit]
            new_report.append(f"[{hit}] 当主不在の期間({prev['end_year']}〜{cur['start_year']}年)を挟むため、"
                              f"先代({prev['title']})との養子関係は生成しません(先代からの継承ではない)。")
    return new_cmds, new_report


def write_years_template(family: str, holders: list[dict]) -> str:
    path = f"{family}_years_template.tsv"
    lines = ["# 代数\t人名\t開始年\t終了年(御三卿としての在任。年のみ。--years で渡す)"]
    for h in holders:
        a = "" if h["start_year"] is None else str(h["start_year"])
        b = "" if h["end_year"] is None else str(h["end_year"])
        lines.append(f"{h['ordinal']}\t{h['title']}\t{a}\t{b}")
    _save(path, "\n".join(lines) + "\n")
    return path


def resolve_holders(family: str, titles: list[str],
                    years: dict[int, tuple[int | None, int | None]] | None = None,
                    ordinals: list[int] | None = None) -> list[dict]:
    """
    人物タイトル(代数順)をQIDに解決する。

    ordinal は、ordinals が渡されればそれ(再襲で同じ代数が重なる場合用)、無ければ titles 上の
    位置そのもの(1始まり)。年は titles 上の位置(row)で引く。QIDが見つからずスキップした代があっても
    詰め直さない(詰めると以降の全員のP1545が実際の代数とずれるため。藩主版と同じ方針)。
    """
    overrides = base._load_qid_overrides()
    holders: list[dict] = []
    skipped: list[int] = []
    for row, title in enumerate(titles, start=1):
        ordinal = ordinals[row - 1] if ordinals else row
        qid = overrides.get(title) or base.title_to_qid(title)
        if qid is None:
            print(f"  !! 警告: {title}(本来の代数: {ordinal}代)のWikidata項目が見つかりません。スキップします。")
            skipped.append(ordinal)
            continue
        start, end = (years or {}).get(row, (None, None))
        holders.append({"title": title, "qid": qid, "ordinal": ordinal, "row": row,
                        "start_year": start, "end_year": end})
        time.sleep(1.0)
    if skipped:
        print(f"  !! 注意: 代数 {', '.join(map(str, skipped))} がスキップされました。"
              "前後の人物は直接の前任・後任とは限らないため、P1365/P1366や養子関係の自動補完は行いません。")
    return holders


# ---------------------------------------------------------------------------
# QuickStatements V1コマンド生成
# ---------------------------------------------------------------------------

def build_position_commands(
    family: str,
    holders: list[dict],
    family_qid: str | None,
    template_qid: str | None,
    category_qid: str | None,
) -> list[list[str]]:
    """
    「○○徳川家当主」役職項目をCREATEするコマンド列。藩主版と同じく、LASTは主語(1列目)にのみ使う。
    各当主は P1308(在職者) + 修飾子 P1545(何代目)・P580/P582(在任の開始・終了年。取れた側のみ)。
    """
    cmds: list[list[str]] = [
        ["CREATE"],
        ["LAST", "Lja", f'"{family}当主"'],
        ["LAST", "Dja", f'"御三卿の一つ、{family}の当主(1871年まで)"'],
        ["LAST", "P31", base.Q_HISTORICAL_POSITION],
        ["LAST", "P17", base.Q_JAPAN],
        ["LAST", "P2348", base.Q_EDO_PERIOD],
        ["LAST", "P576", base._year_to_qs_date(GOSANKYO_END_YEAR)],  # 御三卿の廃止(家自体は存続)
    ]
    if family_qid:
        cmds.append(["LAST", "P2389", family_qid])
    if template_qid:
        cmds.append(["LAST", "P1424", template_qid])
    if category_qid:
        cmds.append(["LAST", "P910", category_qid])
    for h in holders:
        cmds.append(["LAST", "P1308", h["qid"],
                     *base.build_officeholder_qualifiers(h["ordinal"], h["start_year"], h["end_year"])])
    return cmds


def build_person_commands(position_qid: str, holders: list[dict]) -> list[list[str]]:
    """
    各当主個人に P31/P21/P1559 と、P39(当主役職) + P1545(何代目) + P580/P582(在任年) + P1365/P1366(前代・次代)を付ける。
    P1365/P1366は ordinal がちょうど1つ違いの場合のみ付ける(欠番を挟む場合は付けない)。
    同じ人物が複数回載っている場合、基本プロパティは1回だけ、P39は代ごとに別ステートメントにする。
    """
    cmds: list[list[str]] = []
    seen: set[str] = set()
    for i, h in enumerate(holders):
        if h["qid"] not in seen:
            seen.add(h["qid"])
            cmds += base.build_person_basic_commands(h["qid"], base._label_without_disambiguation(h["title"]))
        prev_h = holders[i - 1] if i > 0 else None
        next_h = holders[i + 1] if i < len(holders) - 1 else None
        quals = base.build_officeholder_qualifiers(h["ordinal"], h["start_year"], h["end_year"])
        if prev_h and prev_h["ordinal"] == h["ordinal"] - 1:
            quals += ["P1365", prev_h["qid"]]
        if next_h and next_h["ordinal"] == h["ordinal"] + 1:
            quals += ["P1366", next_h["qid"]]
        cmds.append([h["qid"], "P39", position_qid, *quals])
    return cmds


# ---------------------------------------------------------------------------
# サブコマンド
# ---------------------------------------------------------------------------

def _save(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def run_prepare(args: argparse.Namespace) -> None:
    family = args.family
    template_title = args.template or default_template_title(family)
    exclude = set(args.exclude or []) | {family, "御三卿", "徳川将軍家", "徳川氏"}

    print(f"[1/4] {family} のQIDを解決中...")
    family_qid = None if args.no_link_family else base.title_to_qid(family)
    if not args.no_link_family and family_qid is None:
        print(f"  !! {family} のWikidata項目が見つかりません。P2389(家との紐付け)なしで続行します。")
    print(f"  -> {family_qid}")

    template_years: dict[int, tuple[int | None, int | None]] = {}
    ordinals: list[int] | None = None
    if args.from_tsv:
        rows = load_input_tsv(args.from_tsv)
        titles = [r["title"] for r in rows]
        ordinals = [r["ordinal"] for r in rows]
        template_years = {i: (r["start_year"], r["end_year"]) for i, r in enumerate(rows, start=1)}
        print(f"[2/4] {args.from_tsv} から {len(titles)} 名の人名と在任年を読み込みました(テンプレートは読みません)。")
    elif args.names:
        titles = list(args.names)
        print(f"[2/4] --names で指定された {len(titles)} 名を代数順として使います。")
    else:
        print(f"[2/4] {template_title} を取得・パース中...")
        wikitext = base.get_wikitext(template_title)
        section = extract_group_section(wikitext, args.group)
        if section is None:
            print(f"  !! 当主欄(group に「{args.group}」を含む行)が見つかりません。"
                  "テンプレート全体からリンクを拾うため、当主以外が混ざります。--group か --exclude を調整してください。")
            section = wikitext
        titles = extract_ordered_titles(section, exclude)
        template_years = years_from_template(section, titles)
    if not titles:
        raise SystemExit("当主を1名も抽出できませんでした。--template か --names で指定してください。")
    if args.last:
        before = len(titles)
        titles = truncate_at_last(titles, args.last)
        if ordinals:
            ordinals = ordinals[:len(titles)]
        print(f"  -> --last {args.last} までに絞り込み: {before}名 -> {len(titles)}名(以降は御三卿の当主として扱いません)")
    else:
        print(f"  !! --last が未指定です。{GOSANKYO_END_YEAR}年以降の当主も含めて全員を在職者にします。")
        print(f"     御三卿としての当主は{GOSANKYO_END_YEAR}年で区切る方針なので、最後の当主を --last で指定してください。")
    print("  -> 抽出結果(この順番がそのまま代数になります。必ず目視で確認してください):")
    for i, t in enumerate(titles, start=1):
        print(f"     {ordinals[i - 1] if ordinals else i}代: {t}")
    dups = sorted({t for t in titles if titles.count(t) > 1})
    if dups:
        print(f"  !! 同じ人物が複数回出ています(再任か、関連項目リンクの混入か確認): {', '.join(dups)}")

    print("[3/4] 各当主のQIDとTemplate/Category項目を解決中...")
    years = dict(template_years)
    if args.years:
        years.update(load_years_file(args.years))  # --years はテンプレートの年より優先
        print(f"  -> {args.years} から {len(load_years_file(args.years))} 代分の在任年を読み込みました。")
    holders = resolve_holders(family, titles, years, ordinals)
    apply_end_cutoff(holders)
    mark_vacancies(holders)
    missing = [h for h in holders if h["start_year"] is None or h["end_year"] is None]
    if missing:
        stub = write_years_template(family, holders)
        print(f"  !! 在任年が揃っていない当主が {len(missing)} 名います: "
              + ", ".join(f"{h['ordinal']}代{h['title']}" for h in missing))
        print(f"     {stub} に記入して --years で渡し直してください(年なしのままでも投入はできます)。")
    else:
        print("  -> 全員の在任年が揃っています。")
    template_qid = base.title_to_qid(template_title)
    category_title = args.category or f"Category:{family}当主"
    category_qid = base.title_to_qid(category_title)
    print(f"  -> Template: {template_qid}, Category: {category_qid}")
    if template_qid is None or category_qid is None:
        print("  !! Template/Categoryの一方または両方が見つかりませんでした。名称を確認し、--template/--category で指定してください。")

    cmds = build_position_commands(family, holders, family_qid, template_qid, category_qid)
    tsv = base.commands_to_tsv(cmds)
    position_path = f"{family}_position_create.tsv"
    _save(position_path, tsv)
    _save(f"{family}_holders.json", json.dumps(
        {"family": family, "family_qid": family_qid, "template_qid": template_qid,
         "category_qid": category_qid, "holders": holders}, ensure_ascii=False, indent=1))

    if not args.skip_family:
        print("[4/4] 父・養父関係をドラフト生成中...")
        new_persons: list[dict] = []
        fam_cmds, report = base.build_family_relation_draft(holders, new_persons)
        fam_cmds, report = drop_vacancy_adoptions(holders, fam_cmds, report)
        new_path = base.write_new_persons_tsv(family, new_persons)
        _save(f"{family}_family_draft.tsv", base.commands_to_tsv(fam_cmds))
        _save(f"{family}_family_draft_report.txt", "\n".join(report))
        print("\n".join(report))
        if new_path:
            print(f"  -> 項目が無かった父の作成コマンド: {new_path}")
    else:
        print("[4/4] --skip-family のため家系ドラフトは生成しません。")

    print("\n===== ① 役職項目の作成(まずこちらだけ投入する) =====")
    print("\n".join(tsv.splitlines()[:10]))
    print(f"...(全{len(cmds)}行) -> {position_path}")
    print("\n【重要】このスクリプトはWikidataへの書き込みを一切行いません。")
    print("①を投入して発行されたQIDを控えたら、次を実行してください:")
    print(f"  python {sys.argv[0].split('/')[-1]} person-statements {family} <発行されたQID>")
    if not args.skip_family:
        print("※ 家系ドラフトは藩主用のヒューリスティック(先代を養父とみなす等)を流用しています。")
        print("  御三卿は当主不在の期間や他家からの入嗣があるため、レポートを必ず人間がレビューしてください。")


def run_apply_years(args: argparse.Namespace) -> None:
    """prepare 済みの <家名>_holders.json に在任年を書き足し、役職項目作成TSVを作り直す(ネットワーク不要)。"""
    family = args.family
    path = f"{family}_holders.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    holders = data["holders"]
    rows = load_input_tsv(args.years_tsv)
    for h in holders:
        row = h.get("row", h["ordinal"])  # 古い holders.json(rowなし)は代数=行番号として扱う
        want = rows[row - 1] if 1 <= row <= len(rows) else None
        if want is None or want["title"] != h["title"] or want["ordinal"] != h["ordinal"]:
            raise SystemExit(f"{row}行目({h['ordinal']}代 {h['title']})が TSV と一致しません"
                             f"(TSV: {want and (str(want['ordinal']) + '代 ' + want['title'])})。"
                             "TSVを直すか、prepareをやり直してください。")
        h["row"] = row
        h["start_year"], h["end_year"] = want["start_year"], want["end_year"]
    if len(rows) > len(holders):
        print(f"  !! TSVには {len(rows)} 行ありますが、holders.json は {len(holders)} 名です(QID未解決でスキップされた代がある場合は正常)。")
    apply_end_cutoff(holders)
    mark_vacancies(holders)
    missing = [h for h in holders if h["start_year"] is None or h["end_year"] is None]
    if missing:
        print("  !! 在任年が揃っていない当主: " + ", ".join(f"{h['ordinal']}代{h['title']}" for h in missing))
    _save(path, json.dumps(data, ensure_ascii=False, indent=1))
    cmds = build_position_commands(family, holders, data.get("family_qid"),
                                   data.get("template_qid"), data.get("category_qid"))
    out = f"{family}_position_create.tsv"
    _save(out, base.commands_to_tsv(cmds))
    print(f"{path} を更新し、{out} を在任年入りで作り直しました({len(cmds)}行)。")
    print("\n".join(l for l in base.commands_to_tsv(cmds).splitlines() if "\tP1308\t" in l))


def run_person_statements(args: argparse.Namespace) -> None:
    family = args.family
    path = f"{family}_holders.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    holders = data["holders"]
    cmds: list[list[str]] = []
    if data.get("family_qid"):
        cmds.append([data["family_qid"], "P2388", args.position_qid])
    if data.get("template_qid"):
        cmds.append([data["template_qid"], "P1423", args.position_qid])
    if data.get("category_qid"):
        cmds.append([data["category_qid"], "P301", args.position_qid])
    cmds += build_person_commands(args.position_qid, holders)
    out = f"{family}_person_statements.tsv"
    _save(out, base.commands_to_tsv(cmds))
    print(f"{len(cmds)}行を {out} に保存しました(QIDは {path} から復元。ネットワーク不要)。")
    print("内容を目視確認して、数件だけ試し打ちしてから QuickStatements に投入してください。")
    print("※ P53(家系)・P97(位階)は含まれていません。別途確認して追加してください。")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="御三卿の当主役職項目をQuickStatements V1形式で生成する")
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("prepare", help="役職項目作成TSV + 家系ドラフトを生成する")
    p1.add_argument("family", choices=GOSANKYO, help="家名(田安徳川家/一橋徳川家/清水徳川家)")
    p1.add_argument("--template", help="Templateのタイトル(省略時 Template:<家名>)")
    p1.add_argument("--category", help="Categoryのタイトル(省略時 Category:<家名>当主)")
    p1.add_argument("--group", default="当主", help="navboxの当主欄の見出し(省略時「当主」)")
    p1.add_argument("--years", help="在任年のTSV(代数/人名/開始年/終了年)。テンプレートに年が無いときに使う")
    p1.add_argument("--last", help="御三卿として最後の当主(人名、または代数の数字)。以降は在職者に含めない")
    p1.add_argument("--from-tsv", help="代数/記事タイトル/開始年/終了年を直接書いたTSV(テンプレートは読まない)")
    p1.add_argument("--names", nargs="+", help="Templateを使わず、代数順の人名を直接指定する")
    p1.add_argument("--exclude", nargs="+", help="Template内の当主ではないリンクを除外する")
    p1.add_argument("--no-link-family", action="store_true", help="役職項目に P2389(○○徳川家)を付けない")
    p1.add_argument("--skip-family", action="store_true", help="家系ドラフトを生成しない")

    p3 = sub.add_parser("apply-years", help="prepare済みのholders.jsonに在任年を足し、役職項目作成TSVを作り直す(ネットワーク不要)")
    p3.add_argument("family", choices=GOSANKYO)
    p3.add_argument("years_tsv", help="代数/記事タイトル/開始年/終了年のTSV")

    p2 = sub.add_parser("person-statements", help="第2段階: 逆リンク+各当主個人のP39等を生成する")
    p2.add_argument("family", choices=GOSANKYO)
    p2.add_argument("position_qid", help="第1段階で発行された役職項目のQID")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "prepare":
        run_prepare(args)
    elif args.command == "apply-years":
        run_apply_years(args)
    else:
        run_person_statements(args)


if __name__ == "__main__":
    main()
