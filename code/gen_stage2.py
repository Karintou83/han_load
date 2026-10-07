"""第2段階: 役職QID確定後に、P39(個人側の逆リンク)+family_draft を1ファイルにまとめる。
使い方: python gen_stage2.py pos_qids.json [出力ファイル]
pos_qids.json は {"弘前藩": "Q141657919", ...} 形式。
在職者・年・代数は <藩>_position_create.tsv のP1308行から復元する。
P39には P580/P582 と、代数が連続する場合のみ P1365/P1366 を付ける。
"""
import re, sys, json, glob
EXCLUDE = {"赤穂藩", "佐倉藩", "鹿島藩", "小城藩", "津山藩"}
H = re.compile(r'^LAST\tP1308\t(Q\d+)\tP1545\t"(\d+)"(?:\tP580\t\+(\d{4})-00-00T00:00:00Z/9)?(?:\tP582\t\+(\d{4})-00-00T00:00:00Z/9)?\s*$')
def date(y): return f"+{y}-00-00T00:00:00Z/9"
pos = json.load(open(sys.argv[1], encoding="utf-8"))
out_path = sys.argv[2] if len(sys.argv) > 2 else "stage2_all.tsv"
seen = set(); lines = []; stats = {"p39": 0, "family": 0, "dup": 0}
def emit(cols):
    key = "\t".join(cols)
    if key in seen:
        stats["dup"] += 1; return
    seen.add(key); lines.append(key)
for han, pq in pos.items():
    f = f"{han}_position_create.tsv"
    hold = []
    for l in open(f, encoding="utf-8").read().replace("\r\n", "\n").split("\n"):
        m = H.match(l)
        if m: hold.append((m[1], int(m[2]), m[3], m[4]))
    hold.sort(key=lambda x: x[1])
    for i, (q, o, s, e) in enumerate(hold):
        cols = [q, "P39", pq]
        if s: cols += ["P580", date(s)]
        if e: cols += ["P582", date(e)]
        if i > 0 and hold[i-1][1] == o - 1: cols += ["P1365", hold[i-1][0]]
        if i < len(hold)-1 and hold[i+1][1] == o + 1: cols += ["P1366", hold[i+1][0]]
        emit(cols); stats["p39"] += 1
for f in sorted(glob.glob("*_family_draft.tsv")):
    if f.split("_")[0] in EXCLUDE: continue
    for l in open(f, encoding="utf-8").read().replace("\r\n", "\n").split("\n"):
        if l.strip():
            emit(l.rstrip().split("\t")); stats["family"] += 1
open(out_path, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
print(stats, len(lines), "lines ->", out_path)
