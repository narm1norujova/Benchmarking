#!/usr/bin/env python3
import json
import sys
import time
import argparse
from difflib import SequenceMatcher


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


def safe_get(d, path):
    """Access nested dict safely using dot notation"""
    keys = path.split(".")
    for k in keys:
        if d is None or k not in d:
            return None
        d = d[k]
    return d


def evaluate(gt, pred):
    fields_to_check = [
        "seller_name",
        "fields.field_6",
        "fields.field_10.subfield_a",
        "fields.field_10.subfield_b",
        "fields.field_15",
        "fields.field_15a.subfield_a",
        "fields.field_15a.subfield_b",
        "fields.field_17",
        "fields.field_17a.subfield_a",
        "fields.field_17a.subfield_b",
        "fields.field_18.subfield_left",
        "fields.field_18.subfield_right",
        "fields.field_19",
        "fields.field_21.subfield_left",
        "fields.field_21.subfield_right",
        "fields.field_31.subfield_1_left",
        "fields.field_31.subfield_1_right",
        "fields.field_31.subfield_2",
    ]

    results = {}
    correct = 0

    for field in fields_to_check:
        gt_val = safe_get(gt, field)
        pred_val = safe_get(pred, field)

        match = compare_strings(gt_val, pred_val)
        results[field] = match
        correct += match

    accuracy = (correct / len(fields_to_check)) * 100

    return results, accuracy


def main():
    parser = argparse.ArgumentParser(description="Parser benchmark")
    parser.add_argument("--gt", required=True)
    parser.add_argument("--pred", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    start = time.time()

    gt = process_file(args.gt)
    pred = process_file(args.pred)

    field_results, overall_acc = evaluate(gt, pred)

    elapsed = time.time() - start

    report = {
        "total_fields": len(field_results),
        "overall_accuracy": f"{overall_acc:.2f} %",
        "fields": {k: f"{v*100:.2f} %" for k, v in field_results.items()},
        "time_seconds": f"{elapsed:.2f} sec",
        "price": "$0.00"
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
