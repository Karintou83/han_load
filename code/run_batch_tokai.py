"""
東海地方(駿河・遠江・三河・尾張・飛騨・美濃)の各藩について
create_han_lord_position.py の prepare-han を一括実行する。
(run_batch_prepare.py の run_one() をそのまま使う。東北・親藩・九州・関東・四国・中国地方と同じ手順。)

使い方(code/ フォルダで、ネットワーク制限の無い自分のPCで実行):
    python run_batch_tokai.py --check          # 【先に実行】記事・Template・Category・藩QIDを確認するだけ
    python run_batch_tokai.py                  # 未生成の藩だけ実行(生成済みはスキップ)
    python run_batch_tokai.py --force          # 生成済みも含めてやり直す
    python run_batch_tokai.py --family-only    # 家系ドラフトだけ作り直す
    python run_batch_tokai.py 岡崎藩 大垣藩     # 指定した藩だけ実行
    python run_batch_tokai.py --jobs=2         # 並列数(既定4、最大6)

結果は batch_report_tokai.txt と tokai_preflight.txt に保存(他のレポートは上書きしない)。
Wikidata/Wikipediaへの書き込みは一切行わない。

対象外:
  - 整備済み(親藩の一括投入で作成済みで position_qids.json に登録済み): 尾張藩・高須藩
  - 半原藩(三河国・1868年): 関東の手動対応で「半原藩(Q141732722)」を作成済みだが、README には
    「日本語版Wikipediaに記事が見つからない」とある。この一覧の三河国の半原藩と同じ藩か不明なので、
    HAN_LIST ではコメントアウトしてある。同じ藩なら対象外のまま、別の藩なら --check で調べてから外す。
    - --check(2026-10-14)で除外した10藩: 興国寺藩・三河水野藩・岐阜藩・金山藩(Template無し)、
    加賀野井藩・福束藩・美濃平塚藩・太田山藩(記事・Template無し)、
    大給藩(奥殿藩へのリダイレクト)・畑村藩(大垣新田藩へのリダイレクト)
  (一覧の73項目のうち、上の13項目を除いた60藩が対象)

注意:
- 藩主役職項目は、Template:○○藩主 の「○○藩」(HAN_LISTの第1要素)から名前を作る。
  記事名と食い違う藩は create_han_lord_position.py の HAN_ARTICLE_TITLES に
  {テンプレート側の名前: 記事タイトル} を足す。
- 一覧の表記は Wikipedia の記事名(リンク先)に従って HAN_LIST に書いた:
    駿府藩(静岡藩) / 三河吉田藩(吉田藩・豊橋藩) / 郡上藩(八幡藩) / 飛騨高山藩(高山藩)
  Template が別名(静岡藩主・吉田藩主・八幡藩主・高山藩主 など)の可能性があるので、
  ALT_TEMPLATE_NAMES に別名候補を入れて --check で調べる。
- 同名の藩が他の国にある、または記事名に旧国名が付く藩(一覧には旧国名なしで載っているもの)は、
  ALT_TEMPLATE_NAMES に「美濃○○藩」「駿河○○藩」などの候補を入れてある。
  --check で記事・Template がリダイレクトや「なし」になった藩は、リダイレクト先を見て
  HAN_LIST と HAN_ARTICLE_TITLES を直す。
- 犬山藩(成瀬家)・今尾藩(竹腰家)は尾張藩の附家老の家で、藩として認められたのは1868年。
  立藩以前の当主を藩主に含めるかは要検討(岩国藩・常陸松岡藩と同じ論点。とりあえず Template に従う)。
  犬山藩は一覧で「(尾張藩附家老)(1868年 - )」、今尾藩は「(尾張藩附家老)」とある。
- 大垣新田藩(大垣藩支藩・1688年-)は、固有の領地・陣屋を持つか、本藩と家が同じかを生成後の
  家系ドラフトで確認し、本藩と別の藩・役職項目で良いか判断する(新田藩は家ごとに別の藩にする方針)。
- 浜松藩・掛川藩・岡崎藩・西尾藩・大垣藩・加納藩など、藩主家が何度も入れ替わる藩は、同じ陣屋なら
  同一の藩として1つにまとめる方針なので、家系ドラフトの「問題あり」行を見て判断する。
- 美濃高松藩は「松ノ木藩」とも呼ばれる(一覧の注記)。Template名を --check で確認する。
- 尾張黒田藩・遠江久野藩・三河中島藩・三河水野藩・美濃平塚藩・美濃長谷川藩・美濃脇坂藩・美濃高松藩は
  一覧の記事名のとおり旧国名付きで書いた(他国の同名藩と区別するための記事名)。
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from run_batch_prepare import HERE, run_one

# --check(2026-10-14)で記事またはTemplateが無かったため除外した10藩(Templateが作られたら HAN_LIST に戻す):
#   興国寺藩: Template無し
#   大給藩: 記事は奥殿藩へのリダイレクト(奥殿藩に含まれる)
#   畑村藩: 記事は大垣新田藩へのリダイレクト(大垣新田藩に含まれる)
#   三河水野藩: Template無し
#   岐阜藩: Template無し
#   加賀野井藩: 記事・Template無し
#   福束藩: 記事・Template無し
#   美濃平塚藩: 記事・Template無し
#   太田山藩: 記事・Template無し
#   金山藩: Template無し

# (Template:○○藩主 の「○○藩」, 旧国名)  計60藩
HAN_LIST = [
    # 駿河国
    ("駿府藩", "駿河国"), ("沼津藩", "駿河国"), ("松長藩", "駿河国"), ("小島藩", "駿河国"),
    ("田中藩", "駿河国"), ("川成島藩", "駿河国"), 
    # 遠江国
    ("掛川藩", "遠江国"), ("浜松藩", "遠江国"), ("横須賀藩", "遠江国"), ("相良藩", "遠江国"),
    ("堀江藩", "遠江国"), ("井伊谷藩", "遠江国"), ("掛塚藩", "遠江国"), ("遠江久野藩", "遠江国"),
    # 三河国(半原藩は上の説明のとおり後回し)
    ("挙母藩", "三河国"), ("刈谷藩", "三河国"), ("重原藩", "三河国"), 
    ("岡崎藩", "三河国"), ("西大平藩", "三河国"), ("西端藩", "三河国"), ("西尾藩", "三河国"),
    ("三河吉田藩", "三河国"), ("田原藩", "三河国"),
    #("半原藩", "三河国"),
    ("作手藩", "三河国"), ("新城藩", "三河国"), ("足助藩", "三河国"),
    ("伊保藩", "三河国"), ("奥殿藩", "三河国"), ("三河中島藩", "三河国"), ("深溝藩", "三河国"),
    ("形原藩", "三河国"), ("大浜藩", "三河国"), 
    # 尾張国(尾張藩は整備済み)
    ("犬山藩", "尾張国"), ("緒川藩", "尾張国"), ("尾張黒田藩", "尾張国"), ("清洲藩", "尾張国"),
    # 飛騨国
    ("飛騨高山藩", "飛騨国"),
    # 美濃国(高須藩は整備済み)
    ("今尾藩", "美濃国"), ("郡上藩", "美濃国"), ("苗木藩", "美濃国"),
    ("大垣藩", "美濃国"), ("加納藩", "美濃国"), ("岩村藩", "美濃国"),
    ("揖斐藩", "美濃国"), ("黒野藩", "美濃国"), ("大垣新田藩", "美濃国"), 
    ("青野藩", "美濃国"), ("多良藩", "美濃国"), ("十七条藩", "美濃国"),
    ("高富藩", "美濃国"), ("関藩", "美濃国"), ("上有知藩", "美濃国"),
    ("岩滝藩", "美濃国"), ("徳野藩", "美濃国"), ("美濃高松藩", "美濃国"),
    ("清水藩", "美濃国"), ("曽根藩", "美濃国"), ("野村藩", "美濃国"), ("美濃長谷川藩", "美濃国"),
    ("美濃脇坂藩", "美濃国"),
]

# --check のときだけ、別名のTemplate候補も調べる {HAN_LISTの名前: [別名, ...]}
ALT_TEMPLATE_NAMES = {
    "駿府藩": ["静岡藩"],
    "小島藩": ["駿河小島藩"],
    "田中藩": ["駿河田中藩"],
    "相良藩": ["遠江相良藩"],
    "堀江藩": ["遠江堀江藩"],
    "刈谷藩": ["三河刈谷藩"],
    "三河吉田藩": ["吉田藩", "豊橋藩"],
    "田原藩": ["三河田原藩"],
    "飛騨高山藩": ["高山藩"],
    "郡上藩": ["八幡藩"],
    "青野藩": ["美濃青野藩"],
    "関藩": ["美濃関藩"],
    "金山藩": ["美濃金山藩"],
    "美濃高松藩": ["松ノ木藩", "高松藩 (美濃国)"],
    "清水藩": ["美濃清水藩"],
    "曽根藩": ["美濃曽根藩"],
    "野村藩": ["美濃野村藩"],
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
    (HERE / "tokai_preflight.txt").write_text(text, encoding="utf-8")
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
    (HERE / "batch_report_tokai.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n===== 結果 =====")
    print("\n".join(lines))
    print("\n詳細は batch_report_tokai.txt と <藩名>_run.log を参照してください。")


if __name__ == "__main__":
    main()
