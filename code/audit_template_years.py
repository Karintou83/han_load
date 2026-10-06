"""
Template:○○藩主 の <small>...</small> のうち、現行パーサが取り込めていないものを洗い出す監査スクリプト。

使い方(ネットワーク接続のあるPCで):
    python audit_template_years.py 棚倉藩 白河藩 ...      # 藩名を指定
    python audit_template_years.py --all                 # *_run.log のある全藩

出力: 藩ごとに
  - Template内の「[[人物]]<small>…</small>」の件数
  - パーサが返した件数(複数期間は期間ごとに数える)
  - 解釈できなかった <small> の内容
  - <small> が付かない [[人物]] リンクの有無(年の記述形式が違う可能性)
件数が合わない藩・警告が出た藩だけ「要確認」と表示します。Wikidataへの書き込みは行いません。
"""
import glob
import re
import sys

import create_han_lord_position as c


def audit(han: str) -> bool:
    try:
        wikitext = c.get_template_wikitext(han)
    except Exception as e:  # テンプレートが無い藩(下手渡藩など)
        print(f"{han}: 取得失敗 ({e})")
        return False
    small = c._SMALL_RE.findall(wikitext)
    parsed = c.parse_officeholders_with_years(wikitext)
    warns = list(c.LAST_PARSE_WARNINGS)
    n_periods = 0
    for _, body in small:
        ps = c._parse_periods(body)
        n_periods += len(ps) if ps else 0
    ok = bool(parsed) and not warns and len(parsed) == n_periods
    multi = [(t, b.strip()) for t, b in small if (c._parse_periods(b) or []) and len(c._parse_periods(b)) > 1]
    single = [(t, b.strip()) for t, b in small if re.fullmatch(r"\s*\d{3,4}\s*", re.sub(r"<[^>]+>", "", b))]
    print(f"{han}: <small>{len(small)}件 / 抽出{len(parsed)}件 {'OK' if ok else '★要確認'}")
    for w in warns:
        print(f"   警告: {w}")
    for t, b in single:
        print(f"   単年: [[{t}]] {b}")
    for t, b in multi:
        print(f"   複数期間: [[{t}]] {b}")
    return ok


def main() -> None:
    args = sys.argv[1:]
    if args == ["--all"]:
        args = sorted({f[:-len("_run.log")] for f in glob.glob("*_run.log")})
    if not args:
        raise SystemExit(__doc__)
    bad = [h for h in args if not audit(h)]
    print(f"\n要確認: {len(bad)}藩 {bad}")


if __name__ == "__main__":
    main()
