"""
四国(讃岐・阿波・伊予・土佐)の各藩について
create_han_lord_position.py の prepare-han を一括実行する。
(run_batch_prepare.py の run_one() をそのまま使う。東北・親藩・九州・関東と同じ手順。)

使い方(code/ フォルダで、ネットワーク制限の無い自分のPCで実行):
    python run_batch_shikoku.py --check          # 【先に実行】記事・Template・Category・藩QIDを確認するだけ
    python run_batch_shikoku.py                  # 未生成の藩だけ実行(生成済みはスキップ)
    python run_batch_shikoku.py --force          # 生成済みも含めてやり直す
    python run_batch_shikoku.py --family-only    # 家系ドラフトだけ作り直す
    python run_batch_shikoku.py 丸亀藩 大洲藩     # 指定した藩だけ実行
    python run_batch_shikoku.py --jobs=2         # 並列数(既定4、最大6)

結果は batch_report_shikoku.txt と shikoku_preflight.txt に保存(他のレポートは上書きしない)。
Wikidata/Wikipediaへの書き込みは一切行わない。

対象外(整備済み。親藩の一括投入で作成済みで position_qids.json に登録済み):
    高松藩・西条藩・伊予松山藩・今治藩
    (四国19藩のうち、上の4藩を除いた15藩から、Templateの無い浦戸藩を後回しにした14藩が対象)

注意:
- 藩主役職項目は、Template:○○藩主 の「○○藩」(HAN_LISTの第1要素)から名前を作る。
  記事名と食い違う藩は create_han_lord_position.py の HAN_ARTICLE_TITLES に
  {テンプレート側の名前: 記事タイトル} を足す。
- Template名が記事名と違う藩(2026-10-14 の --check で確認済み): Template:富田藩主 = 阿波富田藩、
  Template:中村藩主 = 土佐中村藩。HAN_LIST は Template側の名前で書き、
  HAN_ARTICLE_TITLES で記事タイトルに対応づけてある。役職項目のラベルは Template に合わせて
  「富田藩主」「中村藩主」になる(説明文に旧国名が入る)ので、必要なら投入前にラベルを直す。
- 土佐中村藩は 1601-1629年(山内康豊・政豊)と 1656-1689年(山内忠直〜豊明)の2期がある。
  同じ陣屋なら同一の藩とみなす方針なので、藩項目・役職項目は1つにまとめ、
  READMEに個別メモを残す(家が同じ山内氏の分家かどうかは本家との関係を含めて要確認)。
- 松山新田藩・土佐新田藩・新谷藩・阿波富田藩・多度津藩などの支藩は、固有の領地・陣屋の有無と
  家(久松松平・山内・加藤・蜂須賀・京極)を確認して、本藩と別の藩・役職項目で良いか判断する。
- 浦戸藩は Template:浦戸藩主 が無いため後回し(Template作成後に HAN_LIST へ追加する)。
- 松山新田藩は記事に対応するWikidata項目(sitelink)が無く藩QIDが引けない。
  make_han_items_shikoku.py で藩項目を作り、発行QIDを han_qid_overrides.json に登録してから実行する。
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from run_batch_prepare import HERE, run_one

# (Template:○○藩主 の「○○藩」, 旧国名)  計14藩
HAN_LIST = [
    # 讃岐国(高松藩は親藩として整備済み)
    ("丸亀藩", "讃岐国"), ("多度津藩", "讃岐国"),
    # 阿波国
    ("徳島藩", "阿波国"), ("富田藩", "阿波国"),   # Template:富田藩主(記事は阿波富田藩)
    # 伊予国(西条藩・今治藩・伊予松山藩は親藩として整備済み)
    ("川之江藩", "伊予国"), ("小松藩", "伊予国"),
    ("松山新田藩", "伊予国"), ("大洲藩", "伊予国"), ("新谷藩", "伊予国"),
    ("伊予吉田藩", "伊予国"), ("宇和島藩", "伊予国"),
    # 土佐国
    ("土佐藩", "土佐国"), ("土佐新田藩", "土佐国"),
    ("中村藩", "土佐国"),   # Template:中村藩主(記事は土佐中村藩)
    # 後回し: 浦戸藩(Template:浦戸藩主 が無い。後で作成してから追加する)
]

# --check のときだけ、別名のTemplate候補も調べる {HAN_LISTの名前: [別名, ...]}
# (四国は 2026-10-14 の --check で解決済みのため空)
ALT_TEMPLATE_NAMES = {}


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
    (HERE / "shikoku_preflight.txt").write_text(text, encoding="utf-8")
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

    total = len(targets)
    print(f"{total}藩を {jobs} 並列で処理します。")
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        futures = [
            ex.submit(run_one, i, total, h, p, force, family_only)
            for i, (h, p) in enumerate(targets, 1)
        ]
        results = [f.result() for f in futures]

    lines = [f"{h}\t{r}" for h, r in results]
    (HERE / "batch_report_shikoku.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n===== 結果 =====")
    print("\n".join(lines))
    print("\n詳細は batch_report_shikoku.txt と <藩名>_run.log を参照してください。")


if __name__ == "__main__":
    main()
