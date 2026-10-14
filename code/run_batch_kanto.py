"""
関東(上野・下野・常陸・上総・下総・武蔵・安房・相模・甲斐)の各藩について
create_han_lord_position.py の prepare-han を一括実行する。
(run_batch_prepare.py の run_one() をそのまま使う。東北・親藩・九州と同じ手順。)

使い方(code/ フォルダで、ネットワーク制限の無い自分のPCで実行):
    python run_batch_kanto.py --check          # 【先に実行】記事・Template・Categoryの有無を確認するだけ
    python run_batch_kanto.py                  # 未生成の藩だけ実行(生成済みはスキップ)
    python run_batch_kanto.py --force          # 生成済みも含めてやり直す
    python run_batch_kanto.py --family-only    # 家系ドラフトだけ作り直す
    python run_batch_kanto.py 沼田藩 安中藩     # 指定した藩だけ実行
    python run_batch_kanto.py --jobs=2         # 並列数(既定4、最大6)

結果は batch_report_kanto.txt と kanto_preflight.txt に保存(他のレポートは上書きしない)。
Wikidata/Wikipediaへの書き込みは一切行わない。

対象外(整備済み): 前橋藩・館林藩・吉井藩・水戸藩・常陸府中藩・常陸宍戸藩・関宿藩・川越藩
(親藩の一括投入で作成済み。position_qids.json に登録済み)。

注意:
- 藩主役職項目は、Template:○○藩主 の「○○藩」(HAN_LISTの第1要素)から名前を作る。
  記事名と食い違う藩は create_han_lord_position.py の HAN_ARTICLE_TITLES に
  {テンプレート側の名前: 記事タイトル} を足す。
- 同名の藩が複数ある場合(北条藩=安房/常陸、山川藩、上田藩、豊岡藩、松山藩、飯田藩など)は、
  --check で記事が曖昧さ回避ページになっていないか、Templateの名前が何かを必ず確認する。
  リストの名前は、関東の藩一覧(ウィキペディア)のリンク先タイトルをそのまま使っている。
- Template:○○藩主 が無い藩(1〜数代で終わる小藩、明治初期の立藩など)は、--check の結果を見て
  HAN_LISTから外すか、先にTemplateを作ってから実行する。
- 旗本の時期がある藩(喜多見藩など)は、東北の矢島藩・黒石藩と同様に、藩主として扱う期間だけを
  役職項目の在職にし、READMEに個別メモを残す。
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from run_batch_prepare import HERE, run_one

# (Template:○○藩主 の「○○藩」, 旧国名)  計137藩
HAN_LIST = [
    # 後回し(Template:○○藩主 が無い10藩): 茂木藩・下野山川藩・松川藩・請西藩・守谷藩・舟戸藩・八幡山藩・船形藩・深見藩・甲府新田藩
    # 野本藩・東方藩は、藩項目を新規作成して han_qid_overrides.json に登録するまで失敗する(make_han_items.py 参照)
    # 除外(--check の結果): 矢田藩=吉井藩へのリダイレクト(吉井藩は整備済み)、高坂藩=掛塚藩へのリダイレクトでTemplateも無い
    # 上野国
    ("沼田藩", "上野国"), ("安中藩", "上野国"), ("高崎藩", "上野国"),
    ("伊勢崎藩", "上野国"), ("七日市藩", "上野国"), ("小幡藩", "上野国"),
    ("総社藩", "上野国"), ("那波藩", "上野国"), ("板鼻藩", "上野国"),
    ("上野豊岡藩", "上野国"), ("大胡藩", "上野国"),
    ("白井藩", "上野国"), ("青柳藩", "上野国"), ("上里見藩", "上野国"),
    ("篠塚藩", "上野国"), ("阿保藩", "上野国"),
    # 下野国
    ("大田原藩", "下野国"), ("黒羽藩", "下野国"), ("喜連川藩", "下野国"),
    ("烏山藩", "下野国"), ("宇都宮藩", "下野国"), ("壬生藩", "下野国"),
    ("佐野藩", "下野国"), ("那須藩", "下野国"), ("高徳藩", "下野国"),
    ("板橋藩", "下野国"), ("鹿沼藩", "下野国"), 
    ("真岡藩", "下野国"), ("下野上田藩", "下野国"), 
    ("足利藩", "下野国"), ("榎本藩", "下野国"), ("下野富田藩", "下野国"),
    ("皆川藩", "下野国"), ("小山藩", "下野国"), ("吹上藩", "下野国"),
    ("西方藩", "下野国"), ("大宮藩", "下野国"),
    # 常陸国
    ("笠間藩", "常陸国"), ("常陸松岡藩", "常陸国"), ("下館藩", "常陸国"),
    ("下妻藩", "常陸国"), ("土浦藩", "常陸国"), ("谷田部藩", "常陸国"),
    ("牛久藩", "常陸国"), ("麻生藩", "常陸国"), ("額田藩", "常陸国"),
    ("保内藩", "常陸国"), ("真壁藩", "常陸国"),
    ("片野藩", "常陸国"), ("柿岡藩", "常陸国"), ("常陸北条藩", "常陸国"),
    ("志筑藩", "常陸国"), ("玉取藩", "常陸国"), ("小張藩", "常陸国"),
    ("常陸古渡藩", "常陸国"), ("江戸崎藩", "常陸国"), ("龍ヶ崎藩", "常陸国"),
    # 上総国
    ("飯野藩", "上総国"), ("佐貫藩", "上総国"),
    ("一宮藩", "上総国"), ("久留里藩", "上総国"), ("大多喜藩", "上総国"),
    ("五井藩", "上総国"), ("松尾藩", "上総国"), ("大網藩", "上総国"),
    ("百首藩", "上総国"), ("小久保藩", "上総国"), ("上総苅谷藩", "上総国"),
    ("姉崎藩", "上総国"), ("鶴牧藩", "上総国"), ("桜井藩", "上総国"),
    ("大多喜新田藩", "上総国"), ("勝浦藩", "上総国"), ("菊間藩", "上総国"),
    ("潤井戸藩", "上総国"), ("鶴舞藩", "上総国"), ("高滝藩", "上総国"),
    ("上総八幡藩", "上総国"),
    # 下総国
    ("結城藩", "下総国"), ("古河藩", "下総国"), ("高岡藩", "下総国"),
    ("小見川藩", "下総国"), ("佐倉藩", "下総国"), ("多古藩", "下総国"),
    ("生実藩", "下総国"), ("下総山川藩", "下総国"), ("大輪藩", "下総国"),
    ("下総山崎藩", "下総国"), ("矢作藩", "下総国"),
    ("下総飯田藩", "下総国"), ("臼井藩", "下総国"), ("岩富藩", "下総国"),
    ("曾我野藩", "下総国"), ("栗原藩", "下総国"), 
    ("下総三浦藩", "下総国"),
    # 武蔵国
    ("忍藩", "武蔵国"), ("岩槻藩", "武蔵国"), ("本庄藩", "武蔵国"),
    ("岡部藩", "武蔵国"), ("深谷藩", "武蔵国"),
    ("東方藩", "武蔵国"), ("騎西藩", "武蔵国"), ("武蔵松山藩", "武蔵国"),
    ("野本藩", "武蔵国"), ("久喜藩", "武蔵国"),
    ("石戸藩", "武蔵国"), ("武蔵小室藩", "武蔵国"), ("原市藩", "武蔵国"),
    ("鳩ヶ谷藩", "武蔵国"), ("喜多見藩", "武蔵国"), ("六浦藩", "武蔵国"),
    ("赤沼藩", "武蔵国"),
    # 安房国
    ("安房勝山藩", "安房国"), ("館山藩", "安房国"), ("長尾藩", "安房国"),
    ("北条藩", "安房国"), ("東条藩", "安房国"), ("花房藩", "安房国"),
    ("安房三枝藩", "安房国"), 
    # 相模国
    ("玉縄藩", "相模国"), ("小田原藩", "相模国"), ("荻野山中藩", "相模国"),
    
    # 甲斐国
    ("甲府藩", "甲斐国"), ("谷村藩", "甲斐国"), ("徳美藩", "甲斐国"),
    
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
    (HERE / "kanto_preflight.txt").write_text(text, encoding="utf-8")
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
    (HERE / "batch_report_kanto.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n===== 結果 =====")
    print("\n".join(lines))
    print("\n詳細は batch_report_kanto.txt と <藩名>_run.log を参照してください。")


if __name__ == "__main__":
    main()
