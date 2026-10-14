"""
徳川家康から系図がつながる親藩(東北以外)について、create_han_lord_position.py の
prepare-han を一括実行する。run_batch_prepare.py の run_one() をそのまま使う。

使い方(code/ フォルダで、ネットワーク制限の無い自分のPCで実行):
    python run_batch_shinpan.py                 # 未生成の藩だけ実行(生成済みはスキップ)
    python run_batch_shinpan.py --force         # 生成済みも含めてやり直す
    python run_batch_shinpan.py --family-only   # 家系ドラフトだけ作り直す
    python run_batch_shinpan.py 福井藩 松江藩    # 指定した藩だけ実行
    python run_batch_shinpan.py --jobs=2        # 並列数(既定4、最大6)

結果は batch_report_shinpan.txt に保存(batch_report.txt は上書きしない)。

注意:
- 藩の記事タイトル・テンプレート名(Template:○○藩主)は推定を含む。失敗した藩は
  <藩名>_run.log を見て、タイトルを直して再実行すること。
- テンプレートには譜代・外様の藩主も含まれるが、藩主役職項目は全藩主を対象に作る
  (東北と同じ扱い)。
- 対象の絞り込み根拠は 親藩リスト_東北以外.md を参照。
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from run_batch_prepare import HERE, run_one

# (藩の記事タイトル, 旧国名)
HAN_LIST = [
    # 御三家
    ("尾張藩", "尾張国"), ("紀州藩", "紀伊国"), ("水戸藩", "常陸国"),
    # 御三家の連枝
    ("高須藩", "美濃国"), ("西条藩", "伊予国"), ("高松藩", "讃岐国"),
    ("常陸府中藩", "常陸国"), ("常陸宍戸藩", "常陸国"),
    # 鷹司松平家(紀州徳川家の御連枝扱い。松姫を介して家康とつながる)
    ("吉井藩", "上野国"),
    # 越前松平家
    ("福井藩", "越前国"), ("松江藩", "出雲国"), ("津山藩", "美作国"),
    ("明石藩", "播磨国"), ("川越藩", "武蔵国"), ("前橋藩", "上野国"),
    ("糸魚川藩", "越後国"), ("広瀬藩", "出雲国"), ("母里藩", "出雲国"),
    ("吉江藩", "越前国"), ("高田藩", "越後国"), ("大野藩", "越前国"),
    ("越前松岡藩", "越前国"),
    # 越智松平家
    ("館林藩", "上野国"), ("浜田藩", "石見国"), ("鶴田藩", "美作国"),
    # 久松松平家(家康の異父弟・定勝の系統)
    ("伊予松山藩", "伊予国"), ("今治藩", "伊予国"), ("桑名藩", "伊勢国"),
    ("長島藩", "伊勢国"), ("関宿藩", "下総国"),
]


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

    total = len(targets)
    print(f"{total}藩を {jobs} 並列で処理します。")
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        futures = [
            ex.submit(run_one, i, total, h, p, force, family_only)
            for i, (h, p) in enumerate(targets, 1)
        ]
        results = [f.result() for f in futures]

    lines = [f"{h}\t{r}" for h, r in results]
    (HERE / "batch_report_shinpan.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n===== 結果 =====")
    print("\n".join(lines))
    print("\n詳細は batch_report_shinpan.txt と <藩名>_run.log を参照してください。")


if __name__ == "__main__":
    main()
