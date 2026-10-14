"""
近畿(伊勢・伊賀・志摩・近江・山城・大和・紀伊・和泉・河内・摂津・丹波・丹後・播磨・但馬・淡路)の各藩について
create_han_lord_position.py の prepare-han を一括実行する。
(run_batch_prepare.py の run_one() をそのまま使う。東北・親藩・九州・関東・四国・中国・北陸と同じ手順。)

使い方(code/ フォルダで、ネットワーク制限の無い自分のPCで実行):
    python run_batch_kinki.py --check          # 【先に実行】記事・Template・Category・藩QIDを確認するだけ
    python run_batch_kinki.py                  # 未生成の藩だけ実行(生成済みはスキップ)
    python run_batch_kinki.py --force          # 生成済みも含めてやり直す
    python run_batch_kinki.py --family-only    # 家系ドラフトだけ作り直す
    python run_batch_kinki.py 彦根藩 津藩       # 指定した藩だけ実行
    python run_batch_kinki.py --jobs=2         # 並列数(既定4、最大6)

結果は batch_report_kinki.txt と kinki_preflight.txt に保存(他のレポートは上書きしない)。
Wikidata/Wikipediaへの書き込みは一切行わない。

対象外:
    整備済み(親藩の一括投入で作成済みで position_qids.json に登録済み): 長島藩・桑名藩・紀州藩・明石藩
    整備済み(赤穂藩は既に生成・投入済み / 峰山藩は本作業の起点で手作業により整備済み): 赤穂藩・峰山藩
    一覧の「淡路国」の節にある 今治藩・姫路藩・徳島藩: 淡路を領した他国の藩の再掲。
        今治藩・徳島藩は四国で整備済み、姫路藩は播磨国の節のものを1回だけ対象にする。
    (Wikipedia「藩の一覧」近畿の節の112件 - 整備済み6藩 - 再掲3件 = 以下の103藩。--check 後に Template が無い8藩を後回しにして95藩を対象にする。さらに朝日山藩・大森藩を当面見送り、93藩)

注意:
- HAN_LIST の第1要素は Template:○○藩主 の「○○藩」。記事名と食い違う藩は
  create_han_lord_position.py の HAN_ARTICLE_TITLES に {Template側の名前: 記事タイトル} を足す。
- 一覧の表記が「国名+藩名」(伊勢亀山藩・丹波亀山藩・伊勢西条藩・近江高島藩 など)の藩は、
  Templateが国名なしの名前(亀山藩主・西条藩主 など)の可能性がある。ただし
  Template:西条藩主 は伊予の西条藩(整備済み)、新庄藩・田辺藩・新宮藩・上野藩・亀山藩・長岡藩・松山藩・
  中島藩・小室藩・宮川藩・高島藩・柏原藩・五条藩 なども他の地域と同名なので、--check の
  「別名候補」欄とリダイレクト表示で、Templateが近畿の藩のものか必ず確かめる(別の地域の藩の
  Templateに紐づけると誤った役職項目になる)。
- 改称がある藩(仁正寺藩=西大路藩、竹原藩=八知藩、伯太藩=大庭寺藩、丹後田辺藩=舞鶴藩、津藩=安濃津藩、
  淡路洲本藩=洲本藩、紀州藩=和歌山藩 など)は、改称しただけで根拠地が同じなら藩項目は共有し、
  藩主の役職項目は改称後を別項目にして旧役職の後継とする方針(請西藩→桜井藩と同じ)。--check 後に判断する。
- 新田藩・支藩(彦根新田藩・姫路新田藩・久居藩・三草藩・芝村藩・戒重藩 など)は、固有の領地・陣屋の有無と
  家を確認して、本藩と別の藩・役職項目で良いか判断する(同名でも家が違えば別の藩として扱う方針)。
- 小藩・短期間の藩(佐和山・大津・近江小室・井生・雲出・伊勢林・伊勢岩手・八田・南林崎・朝日山・御牧・
  岸田・谷川・吉見・大坂・味舌・清富・八木・竹田 など)は Template:○○藩主 が無い可能性が高い。
  無い藩は四国の浦戸藩と同様に後回しにする(HAN_LISTから外し、READMEに記録)。
- 紀伊田辺藩・紀伊新宮藩は紀州藩の附家老の家で、藩として認められたのは1868年。立藩以前の当主を
  藩主に含めるかは要検討(常陸松岡藩・岩国藩と同じ論点。とりあえず Template に従う)。
- 一覧で「（1600年 - ）」のように立藩年だけ書かれた藩でも、実際の藩主の在任が1600年より前に終わる人は
  MIN_HOLDER_END_YEAR により自動で数えない。
- 記事が別の藩へのリダイレクトだったり、記事自体が無い藩は、藩QIDが引けない(藩QID=None)。
  make_han_items.py で藩項目を作り、発行QIDを han_qid_overrides.json に登録してから実行する。

--check の結果と対応(2026-10-14): 103藩中 OK 59 / 要確認 44
- Category=なし だけの要確認(28藩)は問題なし(役職項目に P910/P301 を付けないだけ):
    伊勢上野・雲出・松坂・伊勢岩手・田丸・伊賀上野・長浜・朽木・近江高島・大津・伏見・御牧・櫛羅・興留・
    田原本・御所・大和五条・谷川・西代・大坂・茨木・味舌・八上・平福・清富・村岡・八木・淡路洲本
- 記事が別の藩へのリダイレクトだが、藩QIDは引けている(久居藩→津藩、彦根新田藩→彦根藩、山城長岡藩→高槻藩):
    リダイレクト元に別のWikidata項目(Q109570669 / Q12626275 / Q12589487)がある。ラベルが当該藩であることを目視確認する。
- 名前の対応を直した(HAN_LIST / HAN_ARTICLE_TITLES):
    伊勢林藩 → 林藩(Template:林藩主=OK、記事「伊勢林藩」は林藩へのリダイレクト)
    摂津中島藩 → 中島藩(Template:中島藩主=OK、記事は摂津中島藩。HAN_ARTICLE_TITLES で対応。
        Template:中島藩主 の藩主が摂津中島藩のものか目視確認すること)
    丹波柏原藩(Template:丹波柏原藩主=OK): 記事は柏原藩へのリダイレクトなので、HAN_ARTICLE_TITLES で記事を「柏原藩」に対応
- 藩項目を新規作成する藩(記事が山形藩へのリダイレクトで藩QID=None。Templateはある): 朝日山藩・大森藩
    → make_han_items_kinki.py で new_han_items_kinki.tsv を作り、投入後に発行QIDを han_qid_overrides.json に登録してから実行する。
- Template:○○藩主 が無いため後回しにした8藩(HAN_LIST から外した):
    南林崎藩(記事は伊勢西条藩へのリダイレクト)・竹原藩(記事なし。八知藩のTemplateもなし)・井生藩(記事なし)・
    佐和山藩・戒重藩(記事は芝村藩へのリダイレクト)・岸田藩(記事なし)・吉見藩・竹田藩
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from run_batch_prepare import HERE, run_one

# (Template:○○藩主 の「○○藩」, 旧国名)
HAN_LIST = [
    # 伊勢国(長島藩・桑名藩は親藩として整備済み)
    ("菰野藩", "伊勢国"), ("伊勢亀山藩", "伊勢国"), ("神戸藩", "伊勢国"), ("津藩", "伊勢国"),
    ("久居藩", "伊勢国"), ("八田藩", "伊勢国"), ("伊勢西条藩", "伊勢国"), ("伊勢上野藩", "伊勢国"), ("林藩", "伊勢国"), ("雲出藩", "伊勢国"), ("松坂藩", "伊勢国"),
    
    ("伊勢岩手藩", "伊勢国"), ("田丸藩", "伊勢国"), 
    ("伊賀上野藩", "伊賀国"), ("鳥羽藩", "志摩国"),
    # 近江国(朝日山藩・大森藩は記事が山形藩へのリダイレクトで藩項目が無いため、当面見送り。後で make_han_items_kinki.py で対応)
    ("近江宮川藩", "近江国"), ("長浜藩", "近江国"), ("彦根藩", "近江国"),
    ("彦根新田藩", "近江国"), ("大溝藩", "近江国"), ("朽木藩", "近江国"), ("堅田藩", "近江国"),
    ("山上藩", "近江国"), ("三上藩", "近江国"), ("仁正寺藩", "近江国"),
    ("膳所藩", "近江国"), ("水口藩", "近江国"), ("近江高島藩", "近江国"),
    ("大津藩", "近江国"), ("近江小室藩", "近江国"),
    # 山城国
    ("淀藩", "山城国"), ("山城長岡藩", "山城国"), ("伏見藩", "山城国"), ("御牧藩", "山城国"),
    # 大和国
    ("柳生藩", "大和国"), ("郡山藩", "大和国"), ("小泉藩", "大和国"), ("柳本藩", "大和国"),
    ("芝村藩", "大和国"), ("櫛羅藩", "大和国"), ("宇陀松山藩", "大和国"),
    ("高取藩", "大和国"), ("興留藩", "大和国"), ("竜田藩", "大和国"), ("田原本藩", "大和国"),
    ("大和新庄藩", "大和国"), ("御所藩", "大和国"), ("大和五条藩", "大和国"),
    # 紀伊国(紀州藩は親藩として整備済み。田辺・新宮は紀州藩の附家老の家)
    ("紀伊田辺藩", "紀伊国"), ("紀伊新宮藩", "紀伊国"),
    # 和泉国
    ("陶器藩", "和泉国"), ("伯太藩", "和泉国"), ("岸和田藩", "和泉国"), ("谷川藩", "和泉国"),
    
    ("丹南藩", "河内国"), ("狭山藩", "河内国"), ("西代藩", "河内国"),
    # 摂津国
    ("三田藩", "摂津国"), ("高槻藩", "摂津国"), ("麻田藩", "摂津国"), ("尼崎藩", "摂津国"),
    ("大坂藩", "摂津国"), ("茨木藩", "摂津国"), ("中島藩", "摂津国"), ("味舌藩", "摂津国"),
    # 丹波国
    ("福知山藩", "丹波国"), ("綾部藩", "丹波国"), ("山家藩", "丹波国"), ("丹波柏原藩", "丹波国"),
    ("篠山藩", "丹波国"), ("園部藩", "丹波国"), ("丹波亀山藩", "丹波国"), ("八上藩", "丹波国"),
    # 丹後国(峰山藩は整備済み)
    ("宮津藩", "丹後国"), ("丹後田辺藩", "丹後国"),
    # 播磨国(明石藩は親藩、赤穂藩は投入済み)
    ("山崎藩", "播磨国"), ("安志藩", "播磨国"), ("三日月藩", "播磨国"), ("林田藩", "播磨国"),
    ("三草藩", "播磨国"), ("龍野藩", "播磨国"), ("小野藩", "播磨国"), ("姫路藩", "播磨国"),
    ("福本藩", "播磨国"), ("播磨新宮藩", "播磨国"), ("姫路新田藩", "播磨国"), ("平福藩", "播磨国"),
    # 但馬国
    ("清富藩", "但馬国"), ("出石藩", "但馬国"), ("豊岡藩", "但馬国"), ("村岡藩", "但馬国"),
    ("八木藩", "但馬国"), 
    ("淡路洲本藩", "淡路国"),
]

# --check のときだけ、別名のTemplate候補も調べる {HAN_LISTの名前: [別名, ...]}
ALT_TEMPLATE_NAMES = {
    "伊勢亀山藩": ["亀山藩"],
    "神戸藩": ["伊勢神戸藩"],
    "津藩": ["安濃津藩"],
    "伊勢西条藩": ["西条藩"],       # ※ Template:西条藩主 は伊予の西条藩(整備済み)の可能性が高い。紐づけない
    "伊勢上野藩": ["上野藩"],
    "伊勢林藩": ["林藩"],
    "伊勢岩手藩": ["岩手藩"],
    "竹原藩": ["八知藩"],
    "伊賀上野藩": ["上野藩"],
    "近江宮川藩": ["宮川藩"],
    "仁正寺藩": ["西大路藩"],
    "近江高島藩": ["高島藩"],
    "近江小室藩": ["小室藩"],
    "山城長岡藩": ["長岡藩"],
    "郡山藩": ["大和郡山藩"],
    "竜田藩": ["龍田藩"],
    "宇陀松山藩": ["松山藩"],
    "大和新庄藩": ["新庄藩"],
    "大和五条藩": ["五条藩"],
    "紀伊田辺藩": ["田辺藩"],
    "紀伊新宮藩": ["新宮藩"],
    "伯太藩": ["大庭寺藩"],
    "摂津中島藩": ["中島藩"],
    "丹波柏原藩": ["柏原藩"],
    "丹波亀山藩": ["亀山藩"],
    "丹後田辺藩": ["田辺藩", "舞鶴藩"],
    "播磨新宮藩": ["新宮藩"],
    "淡路洲本藩": ["洲本藩"],
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
    (HERE / "kinki_preflight.txt").write_text(text, encoding="utf-8")
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
    (HERE / "batch_report_kinki.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n===== 結果 =====")
    print("\n".join(lines))
    print("\n詳細は batch_report_kinki.txt と <藩名>_run.log を参照してください。")


if __name__ == "__main__":
    main()
