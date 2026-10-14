"""
中国地方(因幡・伯耆・出雲・美作・石見・備前・備中・備後・安芸・周防・長門)の各藩について
create_han_lord_position.py の prepare-han を一括実行する。
(run_batch_prepare.py の run_one() をそのまま使う。東北・親藩・九州・関東・四国と同じ手順。)

使い方(code/ フォルダで、ネットワーク制限の無い自分のPCで実行):
    python run_batch_chugoku.py --check          # 【先に実行】記事・Template・Category・藩QIDを確認するだけ
    python run_batch_chugoku.py                  # 未生成の藩だけ実行(生成済みはスキップ)
    python run_batch_chugoku.py --force          # 生成済みも含めてやり直す
    python run_batch_chugoku.py --family-only    # 家系ドラフトだけ作り直す
    python run_batch_chugoku.py 岡山藩 広島藩     # 指定した藩だけ実行
    python run_batch_chugoku.py --jobs=2         # 並列数(既定4、最大6)

結果は batch_report_chugoku.txt と chugoku_preflight.txt に保存(他のレポートは上書きしない)。
Wikidata/Wikipediaへの書き込みは一切行わない。

後回し(2藩): 津山新田藩・美作宮川藩。記事が津山藩へのリダイレクトで Template:○○藩主 も無い。

対象外(整備済み。親藩の一括投入で作成済みで position_qids.json に登録済み):
    津山藩・松江藩・広瀬藩・母里藩・浜田藩・鶴田藩
    (一覧の41藩のうち、整備済み6藩と後回し2藩を除いた33藩が対象)

注意:
- 藩主役職項目は、Template:○○藩主 の「○○藩」(HAN_LISTの第1要素)から名前を作る。
  記事名と食い違う藩は create_han_lord_position.py の HAN_ARTICLE_TITLES に
  {テンプレート側の名前: 記事タイトル} を足す。
- 吉永藩は一覧では石見国の並びだが、石見国安濃郡の藩(加藤明友、1643年立藩)で合っている。
- 因幡国の「鹿奴藩(鳥取東館新田藩)」「若桜藩(鳥取西館新田藩)」は一覧の表記が実際の記事名と
  違う可能性がある。--check で Template:鳥取東館新田藩主 / Template:鳥取西館新田藩主 も調べる。
  若桜藩は一覧に2回(1601年の木下氏、1700年の鳥取西館新田藩)出てくるが、同じ記事にリンクされている。
  同じ陣屋でも家が違う新田藩は別の藩・別の役職項目にする方針なので、--check 後に分けるか判断する。
- 津山新田藩も一覧に2回(1676年・1686年)出てくる。同じ記事・Templateなら、家が違うか(森・松平)を
  生成後の家系ドラフトで確認してから、藩項目・役職項目を分けるか判断する。
- 美作宮川藩(1634年-、諸説あり)・矢橋藩(八橋藩の可能性)は、記事・Templateの有無を --check で確認。
- 広島新田藩・松江新田藩・津山新田藩・三次藩・生坂藩・鴨方藩・児島藩・徳山藩・長府藩・清末藩などの支藩は、
  固有の領地・陣屋の有無と家を確認して、本藩と別の藩・役職項目で良いか判断する。
- 長州藩は Template が「萩藩主」の可能性もある(--check の別名候補で確認)。
- 岩国藩は1868年に藩として認められた(吉川家)。立藩以前の吉川家当主を藩主に含めるかは要検討
  (常陸松岡藩と同じ論点。とりあえず Template に従う)。
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from run_batch_prepare import HERE, run_one

# 記事が他の藩へのリダイレクトで、藩QIDを引くと別の藩(本藩)に付いてしまうため、
# 藩項目を新規作成(make_han_items_chugoku.py)して han_qid_overrides.json に登録してから実行する藩。
#   松江新田藩: 記事は松江藩へのリダイレクト(藩QID=None)
#   西江原藩  : 記事は赤穂藩へのリダイレクト。藩QIDが赤穂藩(Q10856274)になってしまう
REQUIRE_OVERRIDE = ["松江新田藩", "西江原藩"]

# (Template:○○藩主 の「○○藩」, 旧国名)  計33藩
HAN_LIST = [
    # 因幡国
    ("鳥取藩", "因幡国"), ("鹿野藩", "因幡国"), ("鹿奴藩", "因幡国"), ("若桜藩", "因幡国"),
    # 伯耆国
    ("米子藩", "伯耆国"), ("倉吉藩", "伯耆国"), ("黒坂藩", "伯耆国"), ("矢橋藩", "伯耆国"),
    # 出雲国(松江藩・広瀬藩・母里藩は親藩として整備済み)
    ("松江新田藩", "出雲国"),
    # 美作国(津山藩・鶴田藩は整備済み)
    ("美作勝山藩", "美作国"),
    # 後回し: 津山新田藩・美作宮川藩(記事が津山藩へのリダイレクトで Template も無い。--check 2026-10-14)
    # 石見国(浜田藩は整備済み)
    ("吉永藩", "石見国"), ("津和野藩", "石見国"),
    # 備前国
    ("岡山藩", "備前国"), ("児島藩", "備前国"),
    # 備中国
    ("新見藩", "備中国"), ("備中松山藩", "備中国"), ("成羽藩", "備中国"), ("浅尾藩", "備中国"),
    ("足守藩", "備中国"), ("岡田藩", "備中国"), ("庭瀬藩", "備中国"), ("生坂藩", "備中国"),
    ("鴨方藩", "備中国"), ("西江原藩", "備中国"),
    # 備後国
    ("三次藩", "備後国"), ("備後福山藩", "備後国"),
    # 安芸国
    ("広島藩", "安芸国"), ("広島新田藩", "安芸国"),
    # 周防国
    ("岩国藩", "周防国"), ("徳山藩", "周防国"),
    # 長門国
    ("長州藩", "長門国"), ("長府藩", "長門国"), ("清末藩", "長門国"),
]

# --check のときだけ、別名のTemplate候補も調べる {HAN_LISTの名前: [別名, ...]}
ALT_TEMPLATE_NAMES = {
    "鹿奴藩": ["鳥取東館新田藩"],
    "若桜藩": ["鳥取西館新田藩"],
    "矢橋藩": ["八橋藩"],
    "備後福山藩": ["福山藩"],
    "長州藩": ["萩藩"],
}


def preflight(targets) -> None:
    """記事・Template・Categoryの存在とリダイレクトを確認する(読み取りのみ)。"""
    import create_han_lord_position as c

    lines = []
    ng = 0
    for i in range(0, len(targets), 12):
        chunk = targets[i:i + 12]
        titles = []
        for h, _ in chunk:
            titles += [c._han_article(h), f"Template:{h}主", f"Category:{h}主"]
            titles += [f"Template:{a}主" for a in ALT_TEMPLATE_NAMES.get(h, [])]
        data = c._jawiki_get({
            "action": "query", "titles": "|".join(titles), "format": "json",
            "formatversion": "2", "redirects": "1",
        })["query"]
        redirects = {r["from"]: r["to"] for r in data.get("redirects", [])}
        missing = {p["title"] for p in data["pages"] if p.get("missing")}
        for h, _ in chunk:
            row = []
            problems = []
            for kind, t in (("記事", c._han_article(h)), ("Template", f"Template:{h}主"),
                            ("Category", f"Category:{h}主")):
                if t in redirects:
                    row.append(f"{kind}=リダイレクト→{redirects[t]}")
                    problems.append(kind)
                elif t in missing:
                    row.append(f"{kind}=なし")
                    problems.append(kind)
                else:
                    row.append(f"{kind}=OK")
            for a in ALT_TEMPLATE_NAMES.get(h, []):
                t = f"Template:{a}主"
                state = (f"リダイレクト→{redirects[t]}" if t in redirects
                         else "なし" if t in missing else "OK")
                row.append(f"別名候補 {t}={state}")
            qid = c._han_qid(h)
            row.append(f"藩QID={qid}")
            if qid is None:
                problems.append("QID")
            flag = "OK " if not problems else "要確認"
            ng += bool(problems)
            lines.append(f"{flag}\t{h}\t" + "\t".join(row))
            time.sleep(0.5)
    lines.append(f"\n要確認: {ng}/{len(targets)}藩")
    text = "\n".join(lines)
    print(text)
    (HERE / "chugoku_preflight.txt").write_text(text, encoding="utf-8")
    print("\n「要確認」の藩は、リダイレクト先(=実際のテンプレート名/記事名)を見て")
    print("HAN_LIST と HAN_ARTICLE_TITLES を直してから本実行してください。")
    print("(Category=なし だけの藩は問題なし。役職項目に P910/P301 を付けないだけです)")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    family_only = "--family-only" in sys.argv
    jobs = 4
    for a in sys.argv[1:]:
        if a.startswith("--jobs="):
            jobs = max(1, min(6, int(a.split("=", 1)[1])))
    targets = [(h, p) for h, p in HAN_LIST if not args or h in args]
    if not targets:
        raise SystemExit("指定された藩名がリストにありません。")
    if "--check" in sys.argv:
        preflight(targets)
        return

    import json
    try:
        ov = json.loads((HERE / "han_qid_overrides.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        ov = {}
    lacking = [h for h, _ in targets if h in REQUIRE_OVERRIDE and h not in ov]
    if lacking:
        raise SystemExit(
            "次の藩は han_qid_overrides.json に藩QIDの登録が必要です(先に make_han_items_chugoku.py で"
            f"藩項目を作成): {', '.join(lacking)}\n他の藩だけ先に実行するなら、藩名を指定してください。")

    total = len(targets)
    print(f"{total}藩を {jobs} 並列で処理します。")
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        futures = [
            ex.submit(run_one, i, total, h, p, force, family_only)
            for i, (h, p) in enumerate(targets, 1)
        ]
        results = [f.result() for f in futures]

    lines = [f"{h}\t{r}" for h, r in results]
    (HERE / "batch_report_chugoku.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n===== 結果 =====")
    print("\n".join(lines))
    print("\n詳細は batch_report_chugoku.txt と <藩名>_run.log を参照してください。")


if __name__ == "__main__":
    main()
