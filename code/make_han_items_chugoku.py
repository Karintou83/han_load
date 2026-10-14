"""
中国地方で、Wikidataに独立した藩項目が無い藩の「藩」項目を新規作成する
QuickStatements V1 TSVを作る。Wikidataへの書き込みは行わない。

対象(--check 2026-10-14 の結果):
  松江新田藩: 記事は松江藩へのリダイレクト。藩QID=None
  西江原藩  : 記事は赤穂藩へのリダイレクト。藩QIDが赤穂藩(Q10856274)になってしまうため別項目が必要

使い方(code/ フォルダで):
    python make_han_items_chugoku.py     # new_han_items_chugoku.tsv を生成

投入前に必ず確認すること:
  - Wikidataで「松江新田藩」「西江原藩」を検索し、すでに項目が存在しないか確認する(重複作成を避ける)。
    存在するなら新規作成せず、そのQIDを han_qid_overrides.json に登録するだけでよい。
  - 西江原藩はQ10856274(赤穂藩)とは別の藩として作る。Template:西江原藩主 の藩主家
    (浅野氏の分家か)と陣屋の有無を確認し、赤穂藩と別の藩にしてよいか判断する。
  - 松江新田藩は固有の陣屋を持たない分家藩(松江藩の支藩)。松山新田藩と同じ扱い。
  - 試し打ちとして1藩だけ先に投入する。

投入後の手順:
  1. new_han_items_chugoku.tsv をQuickStatementsで実行。
  2. 発行されたQIDを han_qid_overrides.json に登録する
       {"...": "...", "松江新田藩": "Q...", "西江原藩": "Q..."}
  3. python run_batch_chugoku.py 松江新田藩 西江原藩   で役職項目TSVを生成。
"""
# (藩名, 旧国, 説明文, 追加ステートメント[列のリスト])
NEW_HAN = [
    ("松江新田藩", "出雲国", "出雲国の藩", []),
    ("西江原藩", "備中国", "備中国の藩", []),
]


def main():
    lines = []
    for name, prov, desc, extra in NEW_HAN:
        lines.append(["CREATE"])
        lines.append(["LAST", "Lja", f'"{name}"'])
        lines.append(["LAST", "Dja", f'"{desc}"'])
        lines.append(["LAST", "P17", "Q17"])
        lines.append(["LAST", "P2348", "Q184963"])
        for e in extra:
            lines.append(["LAST"] + e)
    with open("new_han_items_chugoku.tsv", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join("\t".join(l) for l in lines) + "\n")
    print("\n".join("\t".join(l) for l in lines))
    print("\nnew_han_items_chugoku.tsv を生成しました。重複を確認してから投入してください。")


if __name__ == "__main__":
    main()
