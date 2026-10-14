"""第2段階(親藩・東北以外): 役職QID確定後に、次の3種類のTSVを作る。
  shinpan_stage2_recip.tsv  … 藩項目のP2388、CategoryのP301(逆リンク)
  shinpan_stage2_p39.tsv    … 各藩主個人のP39(P580/P582、連続する代のみP1365/P1366)
  shinpan_stage2_family.tsv … 家系ドラフト(P22/P40/P1038等)。<藩>_family_draft.tsv をまとめて重複除去
使い方(code/ フォルダで): python gen_stage2_shinpan.py
対象は position_qids.json のうち TARGETS に挙げた藩。ネットワークは使わない。
※ 東北分(gen_stage2.py)の方針に合わせ、TemplateのP1423は出さない。
※ 同じ人物が同じ役職に再任した場合(福井の松平昌親など)、2回目のP39を同じ値でQuickStatementsに
   投入すると、1つのステートメントに開始年・終了年・前任者などが2個ずつ混ざってしまう
   (天童藩主の再任分で確認)。そこで2回目以降は shinpan_stage2_p39_manual.tsv に分け、
   Wikidata上で「P39を追加」して手作業で入力する。
※ 津山藩主(Q141529989)は2026-09-22に作成済みで、在職者は13人(森衆利を含まない)。
   TSV側は14人(森衆利を5代として含む)なので、衆利を除いて詰め直した13人でP39を作る。
"""
import re, json
TARGETS = ("尾張 紀州 水戸 高須 西条 高松 常陸府中 常陸宍戸 吉井 福井 松江 津山 明石 川越 前橋 糸魚川 "
           "広瀬 母里 吉江 高田 大野 越前松岡 館林 浜田 鶴田 伊予松山 今治 桑名 長島 関宿").split()
H = re.compile(r'^LAST\tP1308\t(Q\d+)\tP1545\t"(\d+)"(?:\tP580\t\+(\d{4})-00-00T00:00:00Z/9)?(?:\tP582\t\+(\d{4})-00-00T00:00:00Z/9)?\s*$')
def date(y): return f"+{y}-00-00T00:00:00Z/9"
pos = json.load(open("position_qids.json", encoding="utf-8"))
recip, p39, fam, manual = [], [], [], []
SKIP = {"津山": {"Q11540311"}}
seen = set()
def add(lst, cols):
    k = "\t".join(cols)
    if k in seen: return
    seen.add(k); lst.append(k)
for d in TARGETS:
    han = d + "藩"; pq = pos[han]
    t = open(f"{han}_position_create.tsv", encoding="utf-8").read().replace("\r\n", "\n")
    han_q = re.search(r"\tP2389\t(Q\d+)", t).group(1)
    cat = re.search(r"\tP910\t(Q\d+)", t)
    add(recip, [han_q, "P2388", pq])
    if cat: add(recip, [cat.group(1), "P301", pq])
    hold = sorted(((m[1], int(m[2]), m[3], m[4]) for m in map(H.match, t.split("\n")) if m), key=lambda x: x[1])
    if d in SKIP:
        hold = [h for h in hold if h[0] not in SKIP[d]]
        hold = [(q, i + 1, s, e) for i, (q, o, s, e) in enumerate(hold)]
    done = set()
    for i, (q, o, s, e) in enumerate(hold):
        cols = [q, "P39", pq]
        if s: cols += ["P580", date(s)]
        if e: cols += ["P582", date(e)]
        if i > 0 and hold[i-1][1] == o - 1: cols += ["P1365", hold[i-1][0]]
        if i < len(hold)-1 and hold[i+1][1] == o + 1: cols += ["P1366", hold[i+1][0]]
        if q in done: add(manual, cols)
        else: add(p39, cols)
        done.add(q)
    for l in open(f"{han}_family_draft.tsv", encoding="utf-8").read().replace("\r\n", "\n").split("\n"):
        if l.strip(): add(fam, l.rstrip().split("\t"))
for name, lst in (("recip", recip), ("p39", p39), ("p39_manual", manual), ("family", fam)):
    open(f"shinpan_stage2_{name}.tsv", "w", encoding="utf-8", newline="\n").write("\n".join(lst) + "\n")
    print(name, len(lst))
