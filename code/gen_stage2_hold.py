"""第2段階(中国地方): 役職QID確定後に、次のTSVを作る(ネットワーク不要)。
  hold_stage2_recip.tsv   … 藩項目のP2388、CategoryのP301(逆リンク)
  hold_stage2_p39.tsv     … 各藩主個人のP39(P580/P582、連続する代のみP1365/P1366)
  hold_stage2_family_ok.tsv     … 家系ドラフトのうち「問題なし」の藩の分(投入してよい)
  hold_stage2_family_review.tsv … 家系ドラフトのうち要確認を含む藩の分(確認後に投入)
  hold_stage2_family_status.txt … 藩ごとの判定理由
使い方(code/ フォルダで): python gen_stage2_hold.py
対象は position_qids_hold.json の藩。gen_stage2_shinpan.py と同じ方針(TemplateのP1423は出さない)。

家系ドラフトの「問題なし」の基準(_family_draft_report.txt を見て判定):
  - 「見つかりません」(父の項目が無く、一部のコマンドが未生成)が無い
  - ★要確認の行が、すべて「コマンドは生成していません」「補完は行いません」の種類
    (「実父が先代と一致しません」は P22 を生成しつつ養子関係が不明なので、問題ありとする)
"""
import re, json
H = re.compile(r'^LAST\tP1308\t(Q\d+)\tP1545\t"(\d+)"(?:\tP580\t\+(\d{4})-00-00T00:00:00Z/9)?(?:\tP582\t\+(\d{4})-00-00T00:00:00Z/9)?\s*$')
def date(y): return f"+{y}-00-00T00:00:00Z/9"
pos = json.load(open("position_qids_hold.json", encoding="utf-8"))
recip, p39, manual, fam_ok, fam_rev, status = [], [], [], [], [], []
seen = set()
# 改称による後継関係(同じ根拠地。藩項目は共有し、藩主役職項目だけ別): 旧 -> 新。
# 両方の役職QIDが position_qids_hold.json に揃っているときだけ P1366/P1365 を出す。
SUCCESSION = {}
def add(lst, cols):
    k = "\t".join(cols)
    if k in seen: return
    seen.add(k); lst.append(k)
def judge(han):
    rep = open(f"{han}_family_draft_report.txt", encoding="utf-8").read().replace("\r\n", "\n").split("\n")
    why = []
    for l in rep:
        if "見つかりません" in l and "項目を作成しない方針" in l: continue  # 初代以外の養父は項目不要(養子関係は生成されないだけ)
        if "見つかりません" in l: why.append("父の項目なし: " + l[:60])
        elif "★要確認" in l and "コマンドは生成していません" not in l and "補完は行いません" not in l:
            why.append("要確認: " + l[:70])
    return why
for han, pq in pos.items():
    t = open(f"{han}_position_create.tsv", encoding="utf-8").read().replace("\r\n", "\n")
    han_q = re.search(r"\tP2389\t(Q\d+)", t).group(1)
    cat = re.search(r"\tP910\t(Q\d+)", t)
    add(recip, [han_q, "P2388", pq])
    if cat: add(recip, [cat.group(1), "P301", pq])
    hold = sorted(((m[1], int(m[2]), m[3], m[4]) for m in map(H.match, t.split("\n")) if m), key=lambda x: x[1])
    done = set()
    for i, (q, o, s, e) in enumerate(hold):
        cols = [q, "P39", pq]
        if s: cols += ["P580", date(s)]
        if e: cols += ["P582", date(e)]
        if i > 0 and hold[i-1][1] == o - 1: cols += ["P1365", hold[i-1][0]]
        if i < len(hold)-1 and hold[i+1][1] == o + 1: cols += ["P1366", hold[i+1][0]]
        add(manual if q in done else p39, cols)
        done.add(q)
    why = judge(han)
    status.append(f"{'要確認' if why else '問題なし'}\t{han}" + "".join("\n    " + w for w in why))
    for l in open(f"{han}_family_draft.tsv", encoding="utf-8").read().replace("\r\n", "\n").split("\n"):
        if l.strip(): add(fam_rev if why else fam_ok, l.rstrip().split("\t"))
for old, new in SUCCESSION.items():
    if old in pos and new in pos:
        add(recip, [pos[old], "P1366", pos[new]])
        add(recip, [pos[new], "P1365", pos[old]])
    else:
        print(f"注意: 後継関係 {old}→{new} は役職QIDが揃っていないため未生成")
for name, lst in (("recip", recip), ("p39", p39), ("p39_manual", manual), ("family_ok", fam_ok), ("family_review", fam_rev)):
    open(f"hold_stage2_{name}.tsv", "w", encoding="utf-8", newline="\n").write("\n".join(lst) + ("\n" if lst else ""))
    print(name, len(lst))
open("hold_stage2_family_status.txt", "w", encoding="utf-8").write("\n".join(status) + "\n")
print("\n".join(status))
