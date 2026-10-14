"""
<藩名>_position_create.tsv の整合性チェック(ネットワーク不要・読み取りのみ)。

使い方(code/ フォルダで):
    python audit_position_tsv.py 小倉藩 福岡藩 ...   # 藩名を指定
    python audit_position_tsv.py --kyushu            # run_batch_kyushu.py のHAN_LIST全藩

確認する内容:
  1. CREATEが1つ、ラベル=<藩名>主、必須ステートメント(P31/P279/P2389/P17/P2348)がある
  2. P1308の件数が、_run.log の「N 名を抽出」と一致する(QID未解決でスキップされた人が居ない)
  3. 代数(P1545)が1..Nの連番
  4. 開始年≦終了年、前代との年の重なり・空白(重なり>0年、空白>2年、開始年の逆行)
  5. 同じQIDが複数回出る(再任なら正常。要目視)
  6. Template(P1424)・Category(P910)の有無
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def year(v):
    m = re.match(r"\+(\d+)-", v or "")
    return int(m.group(1)) if m else None


def audit(han):
    path = HERE / f"{han}_position_create.tsv"
    if not path.exists():
        return ["TSVがありません"], []
    rows = [l.split("\t") for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    problems, notes = [], []
    if sum(1 for r in rows if r[0] == "CREATE") != 1:
        problems.append("CREATEが1つではありません")
    d = {r[1]: r[2] for r in rows if len(r) >= 3 and r[0] == "LAST"}
    if d.get("Lja") != f'"{han}主"':
        problems.append(f"ラベルが想定外: {d.get('Lja')}")
    for p in ("P31", "P279", "P2389", "P17", "P2348"):
        if p not in d:
            problems.append(f"{p}がありません")
    for p, name in (("P1424", "Template"), ("P910", "Category")):
        if p not in d:
            notes.append(f"{name}の関連付け({p})なし")
    holders = []
    for r in rows:
        if len(r) >= 3 and r[0] == "LAST" and r[1] == "P1308":
            q = dict(zip(r[3::2], r[4::2]))
            holders.append((r[2], int(q["P1545"].strip('"')) if "P1545" in q else None,
                            year(q.get("P580")), year(q.get("P582"))))
    log = HERE / f"{han}_run.log"
    m = re.search(r"(\d+) 名を抽出", log.read_text(encoding="utf-8")) if log.exists() else None
    if m and int(m.group(1)) != len(holders):
        problems.append(f"Templateの{m.group(1)}名に対しP1308が{len(holders)}件(QID未解決でスキップされた人がいる)")
    if not holders:
        problems.append("P1308が0件")
    prev = None
    seen = {}
    for i, (q, ordn, s, e) in enumerate(holders, 1):
        if ordn != i:
            problems.append(f"代数が連番ではない: {i}番目の行がP1545={ordn}")
        seen.setdefault(q, []).append(ordn)
        if s is not None and e is not None and s > e:
            problems.append(f"{ordn}代 {q}: 開始{s} > 終了{e}")
        if s is None or e is None:
            notes.append(f"{ordn}代 {q}: 開始/終了年の片方がない")
        if prev and s is not None and prev[1] is not None:
            if s < prev[0]:
                problems.append(f"{ordn}代 {q}: 開始{s}が前代の開始{prev[0]}より前")
            elif s < prev[1]:
                notes.append(f"{ordn}代 {q}: 前代({prev[1]}終了)と{prev[1]-s}年重なる")
            elif s - prev[1] > 2:
                notes.append(f"{ordn}代 {q}: 前代の終了{prev[1]}から開始{s}まで{s-prev[1]}年空く")
        prev = (s if s is not None else (prev[0] if prev else 0), e)
    for q, os_ in seen.items():
        if len(os_) > 1:
            notes.append(f"{q} が{os_}代に重複(再任なら正常)")
    return problems, notes


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--kyushu" in sys.argv:
        from run_batch_kyushu import HAN_LIST
        args = [h for h, _ in HAN_LIST]
    for han in args:
        p, n = audit(han)
        print(f"{'要修正' if p else ('注意  ' if n else 'OK    ')}\t{han}")
        for x in p:
            print(f"      ✗ {x}")
        for x in n:
            print(f"      ・{x}")


if __name__ == "__main__":
    main()
