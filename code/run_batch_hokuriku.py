"""
北陸・信越(越後・越中・能登・加賀・越前・若狭・信濃)の各藩について
create_han_lord_position.py の prepare-han を一括実行する。
(run_batch_prepare.py の run_one() をそのまま使う。東北・親藩・九州・関東・四国と同じ手順。)

使い方(code/ フォルダで、ネットワーク制限の無い自分のPCで実行):
    python run_batch_hokuriku.py --check          # 【先に実行】記事・Template・Category・藩QIDを確認するだけ
    python run_batch_hokuriku.py                  # 未生成の藩だけ実行(生成済みはスキップ)
    python run_batch_hokuriku.py --force          # 生成済みも含めてやり直す
    python run_batch_hokuriku.py --family-only    # 家系ドラフトだけ作り直す
    python run_batch_hokuriku.py 村上藩 新発田藩   # 指定した藩だけ実行
    python run_batch_hokuriku.py --jobs=2         # 並列数(既定4、最大6)

結果は batch_report_hokuriku.txt と hokuriku_preflight.txt に保存(他のレポートは上書きしない)。
Wikidata/Wikipediaへの書き込みは一切行わない。

対象外(整備済み。親藩の一括投入で作成済みで position_qids.json に登録済み):
    越後: 高田藩・糸魚川藩 / 越前: 福井藩・吉江藩・大野藩・越前松岡藩
    (Wikipedia「藩の一覧」北陸・信越の節の藩から、上の6藩を除いた54藩から、後回しの6藩を除いた48藩が対象)

注意:
- HAN_LIST の第1要素は Template:○○藩主 の「○○藩」。記事名と食い違う藩は
  create_han_lord_position.py の HAN_ARTICLE_TITLES に {Template側の名前: 記事タイトル} を足す。
- 下の「--check で要確認になりやすい藩」は Template名・記事名が一覧の表記と違う可能性が高い。
  --check の「別名候補」欄(ALT_TEMPLATE_NAMES)と redirect 表示を見て HAN_LIST を直してから本実行する。
    長岡藩(記事は越後長岡藩)/ 越前勝山藩(Templateは勝山藩主かも)/ 信濃飯田藩(飯田藩主かも)/
    田野口藩(竜岡藩・龍岡藩)/ 高島藩(一覧では「諏訪藩(高島藩)」)/ 信濃中村藩(中村藩主は土佐中村藩用)/
    能登下村藩・陸奥下村藩 は別の藩 / 高井藩(尾張藩支藩)と高井野藩は別の藩
- 小藩・短期間の藩(蔵王堂・坂戸・三条・布市・西谷・七尾・高森・東郷・安居・木本・葛野・
  長峰・藤井・沢海・埴科・坂木・長沼・奥仁科・近藤 など)は Template:○○藩主 が無い可能性が高い。
  無い藩は四国の浦戸藩と同様に後回しにする(HAN_LISTから外し、READMEに記録)。
- 新田藩・支藩(大聖寺新田・三根山・黒川・三日市・沢海・小諸・埴科・高井・奥仁科 など)は、
  固有の領地・陣屋の有無と家(前田・牧野・柳沢・松平・真田・松本藩の戸田 など)を確認して、
  本藩と別の藩・役職項目で良いか判断する(同名でも家が違えば別の藩として扱う方針)。
- 記事が別の藩へのリダイレクトだったり、記事自体が無い藩は、藩QIDが引けない(藩QID=None)。
  make_han_items.py で藩項目を作り、発行QIDを han_qid_overrides.json に登録してから実行する。
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from run_batch_prepare import HERE, run_one

# (Template:○○藩主 の「○○藩」, 旧国名)  計48藩
HAN_LIST = [
    # 越後国(高田藩・糸魚川藩は親藩として整備済み)
    ("村上藩", "越後国"), ("黒川藩", "越後国"), ("三日市藩", "越後国"), ("新発田藩", "越後国"),
    ("村松藩", "越後国"), ("与板藩", "越後国"),
    ("越後長岡藩", "越後国"),   # Template:越後長岡藩主
    ("蔵王堂藩", "越後国"), ("椎谷藩", "越後国"), ("高柳藩", "越後国"),
    ("坂戸藩", "越後国"), ("三条藩", "越後国"), ("沢海藩", "越後国"), ("藤井藩", "越後国"),
    ("長峰藩", "越後国"),
    # 越中国
    ("富山藩", "越中国"), ("布市藩", "越中国"),
    # 能登国
    ("能登下村藩", "能登国"), ("西谷藩", "能登国"), ("七尾藩", "能登国"),
    # 加賀国
    ("加賀藩", "加賀国"), ("大聖寺藩", "加賀国"), ("大聖寺新田藩", "加賀国"),
    # 越前国(福井藩・大野藩・吉江藩・越前松岡藩は親藩として整備済み)
    ("丸岡藩", "越前国"), ("越前勝山藩", "越前国"), ("鯖江藩", "越前国"), ("敦賀藩", "越前国"),
    ("高森藩", "越前国"), ("木本藩", "越前国"),
    ("葛野藩", "越前国"),
    # 若狭国
    ("小浜藩", "若狭国"), 
    ("飯山藩", "信濃国"), ("須坂藩", "信濃国"), ("松代藩", "信濃国"), ("上田藩", "信濃国"),
    ("小諸藩", "信濃国"), ("岩村田藩", "信濃国"), ("松本藩", "信濃国"),
    
    ("諏訪藩", "信濃国"),     # Template:諏訪藩主(記事は高島藩。HAN_ARTICLE_TITLESで対応)
    ("高遠藩", "信濃国"), ("信濃飯田藩", "信濃国"), ("埴科藩", "信濃国"), ("坂木藩", "信濃国"),
    ("長沼藩", "信濃国"), ("高井藩", "信濃国"), ("奥仁科藩", "信濃国"), ("高井野藩", "信濃国"),
    ("信濃中村藩", "信濃国"),
]

# --check のときだけ、別名のTemplate候補も調べる {HAN_LISTの名前: [別名, ...]}
# (北陸・信越は 2026-10-14 の --check で解決済みのため空)
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
    (HERE / "hokuriku_preflight.txt").write_text(text, encoding="utf-8")
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
    (HERE / "batch_report_hokuriku.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n===== 結果 =====")
    print("\n".join(lines))
    print("\n詳細は batch_report_hokuriku.txt と <藩名>_run.log を参照してください。")


if __name__ == "__main__":
    main()
