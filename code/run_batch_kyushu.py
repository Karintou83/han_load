"""
九州の各藩について create_han_lord_position.py の prepare-han を一括実行する。
(run_batch_prepare.py の run_one() をそのまま使う。東北・親藩と同じ手順。)

使い方(code/ フォルダで、ネットワーク制限の無い自分のPCで実行):
    python run_batch_kyushu.py --check          # 【先に実行】記事・Template・Categoryの有無を確認するだけ
    python run_batch_kyushu.py                  # 未生成の藩だけ実行(生成済みはスキップ)
    python run_batch_kyushu.py --force          # 生成済みも含めてやり直す
    python run_batch_kyushu.py --family-only    # 家系ドラフトだけ作り直す
    python run_batch_kyushu.py 福岡藩 唐津藩     # 指定した藩だけ実行
    python run_batch_kyushu.py --jobs=2         # 並列数(既定4、最大6)

結果は batch_report_kyushu.txt と kyushu_preflight.txt に保存(他のレポートは上書きしない)。
Wikidata/Wikipediaへの書き込みは一切行わない。

対象外: 小城藩・鹿島藩(整備済み)。
注意:
- 藩主役職項目は、Template:○○藩主 の「○○藩」(HAN_LISTの第1要素)から名前を作る。
  記事名と食い違う藩は create_han_lord_position.py の HAN_ARTICLE_TITLES に
  {テンプレート側の名前: 記事タイトル} を足す(豊後高田藩は設定済み)。
- Template:○○藩主 が無い藩(日田藩・岡藩・豊後高松藩などは要注意)は、--check の結果を見て
  HAN_LISTを直すか、先にTemplateを作ってから実行する。
- 下手渡藩(三池藩の立花家が移った東北の藩)は Template:下手渡藩主 が未作成。三池藩の後に別途対応する。
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from run_batch_prepare import HERE, run_one

# (Template:○○藩主 の「○○藩」, 旧国名)
# 高瀬藩は記事が肥後新田藩へのリダイレクトのため、肥後新田藩として登録(--check で要確認)
HAN_LIST = [
    # 豊前国
    ("小倉藩", "豊前国"), ("千束藩", "豊前国"), ("中津藩", "豊前国"),
    # 竜王藩は高田藩 (豊後国)へのリダイレクトで、Template:竜王藩主 も無いため除外(豊後高田藩に含まれる)
    # 豊後国(高田藩のテンプレートは「豊後高田藩主」)
    ("杵築藩", "豊後国"), ("豊後高田藩", "豊後国"), ("日出藩", "豊後国"), ("日田藩", "豊後国"),
    ("森藩", "豊後国"), ("府内藩", "豊後国"), ("臼杵藩", "豊後国"), ("佐伯藩", "豊後国"),
    ("岡藩", "豊後国"), ("豊後高松藩", "豊後国"),
    # 筑前国
    ("東蓮寺藩", "筑前国"), ("福岡藩", "筑前国"), ("秋月藩", "筑前国"),
    # 筑後国
    ("松崎藩", "筑後国"), ("久留米藩", "筑後国"), ("柳河藩", "筑後国"), ("三池藩", "筑後国"),
    # 肥前国(小城藩・鹿島藩は整備済みのため除外)
    ("唐津藩", "肥前国"), ("平戸藩", "肥前国"), ("平戸新田藩", "肥前国"), ("蓮池藩", "肥前国"),
    ("佐賀藩", "肥前国"), ("大村藩", "肥前国"), ("島原藩", "肥前国"), ("福江藩", "肥前国"),
    # 富江藩は福江藩へのリダイレクトで Template:富江藩主 も無いため除外(別途対応)
    # 対馬国
    ("対馬府中藩", "対馬国"),
    # 肥後国
    ("肥後新田藩", "肥後国"), ("熊本藩", "肥後国"), ("宇土藩", "肥後国"), ("人吉藩", "肥後国"),
    ("富岡藩", "肥後国"),
    # 日向国
    ("延岡藩", "日向国"), ("高鍋藩", "日向国"), ("佐土原藩", "日向国"), ("飫肥藩", "日向国"),
    # 薩摩国
    ("薩摩藩", "薩摩国"),
]


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
            qid = c.title_to_qid(c._han_article(h))
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
    (HERE / "kyushu_preflight.txt").write_text(text, encoding="utf-8")
    print("\n「要確認」の藩は、リダイレクト先(=実際のテンプレート名/記事名)を見て")
    print("HAN_LIST と HAN_ARTICLE_TITLES を直してから本実行してください。")


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

    total = len(targets)
    print(f"{total}藩を {jobs} 並列で処理します。")
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        futures = [
            ex.submit(run_one, i, total, h, p, force, family_only)
            for i, (h, p) in enumerate(targets, 1)
        ]
        results = [f.result() for f in futures]

    lines = [f"{h}\t{r}" for h, r in results]
    (HERE / "batch_report_kyushu.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n===== 結果 =====")
    print("\n".join(lines))
    print("\n詳細は batch_report_kyushu.txt と <藩名>_run.log を参照してください。")


if __name__ == "__main__":
    main()
