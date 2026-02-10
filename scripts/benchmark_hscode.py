#!/usr/bin/env python3
import argparse
import json
import re
import sys
import time
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

_DIGITS_RE = re.compile(r"\D+")


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object at top-level")
    return data


def norm_text(s: Any) -> Optional[str]:
    if s is None:
        return None
    return str(s).strip()


def compare_strings(y: Any, pred: Any, threshold: float = 0.85) -> int:
    y_s = norm_text(y)
    p_s = norm_text(pred)
    if y_s == p_s:
        return 1
    if y_s is None or p_s is None:
        return 0
    sim = SequenceMatcher(None, y_s, p_s).ratio()
    return 1 if sim >= threshold else 0


def normalize_hs(code: Any) -> str:
    """
    Rules:
    - hs code must be digits only (we strip non-digits)
    - we keep the cleaned digits string
    """
    if code is None:
        return ""
    s = str(code).strip()
    s = _DIGITS_RE.sub("", s)
    return s


def is_valid_hs_10(code_digits: str) -> bool:
    return len(code_digits) == 10 and code_digits.isdigit()


def is_valid_hs_6plus(code_digits: str) -> bool:
    return len(code_digits) >= 6 and code_digits[:6].isdigit()


def prefix_match(gt_digits: str, pred_digits: str, k: int) -> int:
    """
    1 if first k digits match exactly (and both have >= k digits), else 0
    """
    if len(gt_digits) < k or len(pred_digits) < k:
        return 0
    return 1 if gt_digits[:k] == pred_digits[:k] else 0


def evaluate(gt: Dict[str, Any], pred: Dict[str, Any], *, min_sim: float) -> Dict[str, Any]:
    gt_items: List[Dict[str, Any]] = gt.get("items", []) or []
    pr_items: List[Dict[str, Any]] = pred.get("items", []) or []

    n_gt = len(gt_items)
    n_pr = len(pr_items)
    n = max(n_gt, 1)

    # Seller + item_name matches (based on index alignment)
    seller_match = compare_strings(gt.get("seller_name"), pred.get("seller_name"), threshold=min_sim)

    items_to_compare = min(n_gt, n_pr)
    item_name_matches = 0

    # HS validity counters
    gt_valid_10 = 0
    gt_valid_6 = 0
    pr_valid_10 = 0
    pr_valid_6 = 0

    # Prefix accuracies 1..10 over GT items (index-aligned)
    prefix_hits = {k: 0 for k in range(1, 11)}

    for i in range(n_gt):
        g = gt_items[i] or {}
        g_hs = normalize_hs(g.get("hs_code"))
        if is_valid_hs_10(g_hs):
            gt_valid_10 += 1
        if is_valid_hs_6plus(g_hs):
            gt_valid_6 += 1

        if i < n_pr:
            p = pr_items[i] or {}
            # item_name match (only where we have pred item)
            item_name_matches += compare_strings(g.get("item_name"), p.get("item_name"), threshold=min_sim)

            p_hs = normalize_hs(p.get("hs_code"))
            if is_valid_hs_10(p_hs):
                pr_valid_10 += 1
            if is_valid_hs_6plus(p_hs):
                pr_valid_6 += 1

            for k in range(1, 11):
                prefix_hits[k] += prefix_match(g_hs, p_hs, k)

    # Convert to percentages
    gt_10_pct = (gt_valid_10 / n_gt * 100.0) if n_gt else 0.0
    gt_6_pct = (gt_valid_6 / n_gt * 100.0) if n_gt else 0.0
    pr_10_pct = (pr_valid_10 / n_gt * 100.0) if n_gt else 0.0  # normalized by GT count like your screenshot
    pr_6_pct = (pr_valid_6 / n_gt * 100.0) if n_gt else 0.0

    acc = {k: (prefix_hits[k] / n_gt * 100.0) if n_gt else 0.0 for k in range(1, 11)}

    # Item name match % over GT items (index-aligned portion contributes; missing preds count as 0)
    item_name_pct = (item_name_matches / n_gt * 100.0) if n_gt else 0.0
    seller_pct = seller_match * 100.0

    return {
        "n_items": n_gt,
        "seller_name_match": seller_pct,
        "item_name_match_table": item_name_pct,

        "y_10_match_table": gt_10_pct,
        "y_6_match_table": gt_6_pct,
        "pred_10_match_table": pr_10_pct,
        "pred_6_match_table": pr_6_pct,

        "accuracy_10": acc[10],
        "accuracy_6": acc[6],
        "metadata": {f"accuracy_{k}": acc[k] for k in range(1, 11)},
    }


def main():
    ap = argparse.ArgumentParser(description="Benchmark HS code generation (prefix accuracy 1..10)")
    ap.add_argument("--gt", required=True, help="Ground truth JSON file")
    ap.add_argument("--pred", required=True, help="Prediction JSON file")
    ap.add_argument("--out", required=True, help="Output report JSON file")
    ap.add_argument("--min-sim", type=float, default=0.85, help="SequenceMatcher threshold for seller/item names")
    ap.add_argument("--price", default="$0.00", help="Optional price string to write in report (default: $0.00)")
    args = ap.parse_args()

    t0 = time.time()

    try:
        gt = load_json(args.gt)
        pr = load_json(args.pred)

        res = evaluate(gt, pr, min_sim=args.min_sim)

        elapsed = time.time() - t0

        report = {
            "n_items": res["n_items"],

            # + seller/item benchmarks (you asked to include these)
            "seller_name_match_table": f"{res['seller_name_match']:.2f} %",
            "item_name_match_table": f"{res['item_name_match_table']:.2f} %",

            # like your screenshot
            "y_10_match_table": f"{res['y_10_match_table']:.2f} %",
            "y_6_match_table": f"{res['y_6_match_table']:.2f} %",
            "pred_10_match_table": f"{res['pred_10_match_table']:.2f} %",
            "pred_6_match_table": f"{res['pred_6_match_table']:.2f} %",
            "accuracy_10": f"{res['accuracy_10']:.2f} %",
            "accuracy_6": f"{res['accuracy_6']:.2f} %",

            "metadata": {k: f"{v:.2f} %" for k, v in res["metadata"].items()},
            "time_seconds": f"{elapsed:.2f} sec",
            "price": args.price,
        }

        # Terminal summary (simple)
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
