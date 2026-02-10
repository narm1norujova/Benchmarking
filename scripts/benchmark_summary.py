#!/usr/bin/env python3
import argparse
import json
import re
import sys
import time
from difflib import SequenceMatcher
from typing import Any, Dict, List, Tuple

_DIGITS_RE = re.compile(r"\D+")


def process_file(file_path: str) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{file_path}: expected JSON object at top-level")
    return data


def compare_strings(y: Any, pred: Any, threshold: float = 0.85) -> int:
    if y == pred:
        return 1
    if y is None or pred is None:
        return 0
    sim = SequenceMatcher(None, str(y).strip(), str(pred).strip()).ratio()
    return 1 if sim >= threshold else 0


def normalize_hs(code: Any) -> str:
    if code is None:
        return ""
    return _DIGITS_RE.sub("", str(code).strip())


def is_valid_hs10(code_digits: str) -> bool:
    return len(code_digits) == 10 and code_digits.isdigit()


def extract_pairs(obj: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Expected:
    {
      "seller_name": "...",
      "items": [
        { "3816000009": "some summary text" }
      ]
    }
    Returns list of (hs_code_digits, summary_text)
    """
    pairs: List[Tuple[str, str]] = []
    items = obj.get("items", []) or []
    for it in items:
        if isinstance(it, dict) and len(it) == 1:
            (k, v), = it.items()
            hs = normalize_hs(k)
            txt = "" if v is None else str(v)
            pairs.append((hs, txt))
        elif isinstance(it, dict):
            for k, v in it.items():
                hs = normalize_hs(k)
                txt = "" if v is None else str(v)
                pairs.append((hs, txt))
        else:
            pairs.append(("", ""))
    return pairs


def evaluate(gt: Dict[str, Any], pred: Dict[str, Any], *, min_sim: float) -> Dict[str, Any]:
    seller_match = compare_strings(gt.get("seller_name"), pred.get("seller_name"), threshold=min_sim)

    gt_pairs = extract_pairs(gt)
    pr_pairs = extract_pairs(pred)

    n_gt = len(gt_pairs)
    n_pr = len(pr_pairs)
    n = max(n_gt, 1)

    items_to_compare = min(n_gt, n_pr)

    # HS validity (pred)
    pr_valid_hs10 = sum(1 for hs, _ in pr_pairs if is_valid_hs10(hs))

    # Exact hs match + summary match (index-aligned)
    hs_exact = 0
    summary_match = 0

    for i in range(items_to_compare):
        g_hs, g_txt = gt_pairs[i]
        p_hs, p_txt = pr_pairs[i]

        hs_exact += 1 if g_hs and p_hs and g_hs == p_hs else 0
        summary_match += compare_strings(g_txt, p_txt, threshold=min_sim)

    item_count_match = 1 if n_gt == n_pr else 0

    # Percentages (normalized by GT count)
    return {
        "n_items": n_gt,
        "seller_pct": seller_match * 100.0,
        "hs_pct": (hs_exact / n_gt * 100.0) if n_gt else 0.0,
        "summary_pct": (summary_match / n_gt * 100.0) if n_gt else 0.0,
        "item_count_pct": item_count_match * 100.0,
        "missing_items": max(0, n_gt - n_pr),
        "extra_items": max(0, n_pr - n_gt),
        "pred_hs10_valid_pct": (pr_valid_hs10 / n_gt * 100.0) if n_gt else 0.0,
    }


def main():
    ap = argparse.ArgumentParser(description="Benchmark summary JSON")
    ap.add_argument("--gt", required=True)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-sim", type=float, default=0.85)
    ap.add_argument("--price", default="$0.00")
    args = ap.parse_args()

    t0 = time.time()

    try:
        gt = process_file(args.gt)
        pr = process_file(args.pred)

        res = evaluate(gt, pr, min_sim=args.min_sim)
        elapsed = time.time() - t0

        # IMPORTANT: report shape exactly like you asked
        report = {
            "n_items": res["n_items"],
            "seller_name": f"{res['seller_pct']:.2f} %",
            "hs_code": f"{res['hs_pct']:.2f} %",
            "summary": f"{res['summary_pct']:.2f} %",
            "item_count": f"{res['item_count_pct']:.2f} %",
            "missing_items": res["missing_items"],
            "extra_items": res["extra_items"],
            "time_seconds": f"{elapsed:.2f} sec",
            "price": args.price,
        }

        print(json.dumps(report, ensure_ascii=False, indent=2))

        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
