#!/usr/bin/env python3
import argparse
import json
import time
from difflib import SequenceMatcher
import os
from datetime import datetime


def process_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_strings(y, pred, threshold=0.85):
    if y == pred:
        return 1
    if y is None or pred is None:
        return 0
    similarity = SequenceMatcher(None, str(y), str(pred)).ratio()
    return 1 if similarity >= threshold else 0


def build_path_map(obj):

    result = {}
    for f in obj.get("files", []):
        path = str(f.get("path", "")).strip()
        ftype = str(f.get("type", "")).strip()
        if path:
            result[path] = ftype
    return result


def evaluate(gt, pred):
    gt_map = build_path_map(gt)
    pred_map = build_path_map(pred)

    gt_paths = set(gt_map.keys())
    pred_paths = set(pred_map.keys())

    common_paths = gt_paths & pred_paths
    missing = gt_paths - pred_paths
    extra = pred_paths - gt_paths

    correct = 0
    per_type_stats = {}

    for path in common_paths:
        gt_type = gt_map[path]
        pred_type = pred_map[path]

        per_type_stats.setdefault(gt_type, {"total": 0, "correct": 0})
        per_type_stats[gt_type]["total"] += 1

        match = compare_strings(gt_type, pred_type)
        correct += match
        per_type_stats[gt_type]["correct"] += match

    n_items = len(gt_map)
    accuracy = (correct / n_items * 100) if n_items else 0

    per_type_accuracy = {
        t: f"{(v['correct'] / v['total'] * 100):.2f} %"
        for t, v in per_type_stats.items()
    }

    return {
        "n_items": n_items,
        "accuracy": f"{accuracy:.2f} %",
        "correct": correct,
        "missing_items": len(missing),
        "extra_items": len(extra),
        "per_type": per_type_accuracy,
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark classification")
    parser.add_argument("--gt", required=True)
    parser.add_argument("--pred", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    start = time.time()

    gt = process_file(args.gt)
    pred = process_file(args.pred)

    report = evaluate(gt, pred)

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.out is None:
        os.makedirs("reports", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.out = f"reports/report_classification_{ts}.json"
    else:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
