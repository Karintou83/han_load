"""
北海道・東北の各藩について create_han_lord_position.py の prepare-han を一括実行する。

使い方(code/ フォルダで実行):
    python run_batch_prepare.py            # 未生成の藩だけ実行(生成済みはスキップ)
    python run_batch_prepare.py --force    # 生成済みも含めて全藩やり直す
    python run_batch_prepare.py --family-only   # 家系ドラフト(family_draft)だけ全藩作り直す
    python run_batch_prepare.py 弘前藩 盛岡藩   # 指定した藩だけ実行

このスクリプトもWikidata/Wikipediaへの書き込みは一切行わない。
各藩でエラーが出ても止まらず次の藩へ進み、最後に成功/失敗の一覧を batch_report.txt に保存する。
(ネットワーク制限の無い自分のPCで実行すること。1藩あたり数十秒〜数分かかる。)
"""
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "create_han_lord_position.py"

# (藩の記事タイトル, 旧国名)。旧国名は説明文「<旧国名><藩名>を治めた藩主」にのみ使われる。
# 白河新田藩は記事が無いため対象外。
HAN_LIST = [
    ("松前藩", "渡島国"),
    # 陸奥国
    ("斗南藩", "陸奥国"), ("七戸藩", "陸奥国"), ("弘前藩", "陸奥国"),
    #("黒石藩", "陸奥国"), 
    ("八戸藩", "陸奥国"),
    # 陸中国
    ("盛岡藩", "陸中国"), ("一関藩", "陸中国"),
    # 陸前国
    #("仙台藩", "陸前国"), 
    ("岩沼藩", "陸前国"), ("中津山藩", "陸前国"),
    # 羽後国
    ("久保田藩", "羽後国"), ("岩崎藩", "羽後国"), ("亀田藩", "羽後国"),
    ("本荘藩", "羽後国"), #("矢島藩", "羽後国"), 
    ("久保田新田藩", "羽後国"),
    # 羽前国
    ("庄内藩", "羽前国"), ("出羽松山藩", "羽前国"), ("新庄藩", "羽前国"),
    ("山形藩", "羽前国"), ("上山藩", "羽前国"), ("天童藩", "羽前国"),
    ("長瀞藩", "羽前国"), 
    #("米沢藩", "羽前国"), 
    ("米沢新田藩", "羽前国"),
    ("大山藩", "羽前国"), ("左沢藩", "羽前国"), ("仁賀保藩", "羽後国"),
    ("出羽丸岡藩", "羽前国"), ("村山藩", "羽前国"), ("高畠藩", "羽前国"),
    # 磐城国
    ("相馬中村藩", "磐城国"), ("三春藩", "磐城国"), ("守山藩", "磐城国"),
    ("磐城平藩", "磐城国"), ("棚倉藩", "磐城国"), #("湯長谷藩", "磐城国"),
    ("泉藩", "磐城国"), ("白河藩", "磐城国"), ("浅川藩", "磐城国"), ("窪田藩", "磐城国"),
    # 岩代国
    ("福島藩", "岩代国"), ("二本松藩", "岩代国"), ("梁川藩", "岩代国"),
    ("桑折藩", "岩代国"), #("下手渡藩", "岩代国"), 
    ("陸奥下村藩", "岩代国"),
    ("会津藩", "岩代国"), ("大久保藩", "岩代国"), ("石川藩", "岩代国"),
]


def run_one(i, total, han, prov, force, family_only=False):
    out = HERE / f"{han}_position_create.tsv"
    out2 = HERE / f"{han}_family_draft_report.txt"  # 最後に書かれるファイル。両方あれば完了とみなす
    if not family_only and out.exists() and out2.exists() and not force:
        print(f"[{i}/{total}] {han}: 生成済みのためスキップ", flush=True)
        return han, "スキップ(生成済み)"
    print(f"[{i}/{total}] {han} ({prov}) 開始", flush=True)
    t0 = time.time()
    # Windowsの標準文字コード(cp932)だと「兕」などの珍しい漢字を表示する際にエラーになるため、
    # 子プロセスをUTF-8モードで動かす。
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)] + (["draft-family", han] if family_only else ["prepare-han", han, prov]),
        cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env,
    )
    log = HERE / f"{han}_run.log"
    log.write_text(proc.stdout + "\n--- stderr ---\n" + proc.stderr, encoding="utf-8")
    sec = int(time.time() - t0)
    if proc.returncode == 0:
        print(f"[{i}/{total}] {han}: 成功 ({sec}秒)", flush=True)
        return han, f"成功 ({sec}秒)"
    last = (proc.stderr.strip().splitlines() or ["不明なエラー"])[-1]
    print(f"[{i}/{total}] {han}: 失敗: {last}", flush=True)
    return han, f"失敗: {last}(詳細は {log.name})"


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    family_only = "--family-only" in sys.argv  # 家系ドラフトだけ作り直す(役職項目TSVは触らない)
    jobs = 4  # 同時に処理する藩の数。--jobs=N で変更可(Wikimediaへの配慮から最大6)
    for a in sys.argv[1:]:
        if a.startswith("--jobs="):
            jobs = max(1, min(6, int(a.split("=", 1)[1])))
    targets = [(h, p) for h, p in HAN_LIST if not args or h in args]
    if not targets:
        raise SystemExit("指定された藩名がリストにありません。")

    total = len(targets)
    print(f"{total}藩を {jobs} 並列で処理します。")
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        futures = [
            ex.submit(run_one, i, total, h, p, force, family_only) for i, (h, p) in enumerate(targets, 1)
        ]
        results = [f.result() for f in futures]

    lines = [f"{h}\t{r}" for h, r in results]
    (HERE / "batch_report.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n===== 結果 =====")
    print("\n".join(lines))
    print("\n詳細は batch_report.txt と <藩名>_run.log を参照してください。")


if __name__ == "__main__":
    main()
