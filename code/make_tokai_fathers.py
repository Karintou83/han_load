"""東海の family_review に必要な父(新規人物)だけを new_persons_all.tsv から抜き出す。
tokai_stage2_family_status.txt の「父の項目なし: [子] 父=○○」から (子, 父) を取り、
new_persons_all.tsv の CREATE ブロック(Lja=父名, Dja=「子の父」)と突き合わせる。
他地域の父は含めない(関東などは未作成のまま new_persons_all.tsv に残っている)。"""
import re, sys
status = open("tokai_stage2_family_status.txt", encoding="utf-8").read().splitlines()
pairs = []
for l in status:
    m = re.match(r"\s+父の項目なし: \[(.+?)\] (?:養)?父=(.+?) のWikidata項目", l)
    if m:
        pairs.append((m.group(1), m.group(2), "養父" in l.split("父=")[0]))
blocks = []; cur = None
for l in open("new_persons_all.tsv", encoding="utf-8").read().splitlines():
    if l == "CREATE":
        cur = []; blocks.append(cur)
    elif cur is not None and l.strip():
        cur.append(l)
def lja(b): return re.match(r'LAST\tLja\t"(.*)"', b[0]).group(1)
def dja(b):
    m = re.match(r'LAST\tDja\t"(.*)"', b[1]); return m.group(1) if m else ""
out = {}; unmatched = []; skipped = []
for child, father, adopt in pairs:
    if "または" in father:
        skipped.append((child, father)); continue
    base = re.sub(r" \(.*\)$", "", child)
    hit = [b for b in blocks if lja(b) == father and dja(b) in (child + "の父", base + "の父", child + "の養父", base + "の養父")]
    if not hit:
        hit = [b for b in blocks if lja(b) == father and base in dja(b)]
    if not hit and any((lja(x), dja(x)) in out for x in blocks if lja(x) == father): continue  # 同じ父の別の子
    if not hit: hit = [b for b in blocks if lja(b) == father]  # 他地域の子の父として登録済み(共通の父)
    if not hit: unmatched.append((child, father)); continue
    out.setdefault((lja(hit[0]), dja(hit[0])), hit[0])
with open("tokai_new_fathers.tsv", "w", encoding="utf-8") as f:
    for b in out.values():
        f.write("CREATE\n"); seen = set()
        for l in b:
            if l not in seen: f.write(l + "\n"); seen.add(l)
print("pairs", len(pairs), "人物", len(out), "未一致", unmatched, "スキップ", skipped)
for (n, d) in out: print(n, "|", d)
