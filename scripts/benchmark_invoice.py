#!/usr/bin/env python3
import json
import sys
import time
from difflib import SequenceMatcher
import argparse
import os
from datetime import datetime


def process_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_strings(y, pred, threshold=0.7):
    if y == pred:
        return 1
    if y is None or pred is None:
        return 0
    similarity = SequenceMatcher(None, str(y), str(pred)).ratio()
    return 1 if similarity >= threshold else 0


def compare_numbers(y, pred, tolerance=0.001):
    if y == pred:
        return 1
    try:
        y_f = float(y) if y is not None else 0.0
        p_f = float(pred) if pred is not None else 0.0
        if y_f == 0.0 and p_f == 0.0:
            return 1
        denom = max(abs(y_f), abs(p_f), 1e-9)
        rel_diff = abs(y_f - p_f) / denom
        return 1 if rel_diff <= tolerance else 0
    except Exception:
        return 0


def evaluate(y, pred):
    y_items = y.get("items", []) or []
    pred_items = pred.get("items", []) or []

    if len(y_items) != len(pred_items):
        print(f"Item count mismatch: Expected {len(y_items)}, Predicted {len(pred_items)}")

    items_to_compare = min(len(y_items), len(pred_items))

    item_name_matches = 0
    quantity_matches = 0
    unit_price_matches = 0
    total_price_matches = 0

    for i in range(items_to_compare):
        y_item = y_items[i] or {}
        p_item = pred_items[i] or {}

        item_name_matches += compare_strings(y_item.get("item_name"), p_item.get("item_name"))
        quantity_matches += compare_numbers(y_item.get("quantity"), p_item.get("quantity"))
        unit_price_matches += compare_numbers(y_item.get("unit_price"), p_item.get("unit_price"))
        total_price_matches += compare_numbers(y_item.get("total_price"), p_item.get("total_price"))

    return {
        "seller_name": compare_strings(y.get("seller_name"), pred.get("seller_name")),
        "sum_total_quantity": compare_numbers(y.get("sum_total_quantity"), pred.get("sum_total_quantity")),
        "sum_total_price": compare_numbers(y.get("sum_total_price"), pred.get("sum_total_price")),
        "currency": compare_strings(y.get("currency"), pred.get("currency")),
        "n_items": len(y_items),
        "item_count_match": int(len(y_items) == len(pred_items)),
        "missing_items": max(0, len(y_items) - len(pred_items)),
        "extra_items": max(0, len(pred_items) - len(y_items)),
        "items": {
            "item_name": item_name_matches,
            "quantity": quantity_matches,
            "unit_price": unit_price_matches,
            "total_price": total_price_matches,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark invoice processing")
    parser.add_argument("--gt", required=True, help="Ground truth JSON file")
    parser.add_argument("--pred", required=True, help="Prediction JSON file")
    parser.add_argument("--out", default=None, help="Output report JSON file (optional)")
    args = parser.parse_args()

    start_time = time.time()

    try:
        y = process_file(args.gt)
        pred = process_file(args.pred)

        print(f"Ground truth file: {args.gt}")
        print(f"Prediction file: {args.pred}")

        res = evaluate(y, pred)
        n = max(res["n_items"], 1)

        overall_components = [
            res["seller_name"],
            res["sum_total_price"],
            res["currency"],
            res["item_count_match"],
            res["items"]["item_name"] / n,
            res["items"]["quantity"] / n,
            res["items"]["unit_price"] / n,
            res["items"]["total_price"] / n,
        ]
        overall_score = (sum(overall_components) / 8.0) * 100.0

        elapsed = time.time() - start_time

        result = {
            "seller_name": f"{res['seller_name'] * 100:.2f} %",
            "sum_total_quantity": f"{res['sum_total_quantity'] * 100:.2f} %",
            "sum_total_price": f"{res['sum_total_price'] * 100:.2f} %",
            "currency": f"{res['currency'] * 100:.2f} %",
            "n_items": float(res["n_items"]),
            "item_count_match": f"{res['item_count_match'] * 100:.2f} %",
            "missing_items": f"{(res['missing_items'] / n) * 100:.2f} %",
            "extra_items": f"{(res['extra_items'] / n) * 100:.2f} %",
            "items": {
                "item_name": f"{(res['items']['item_name'] / n) * 100:.2f} %",
                "quantity": f"{(res['items']['quantity'] / n) * 100:.2f} %",
                "unit_price": f"{(res['items']['unit_price'] / n) * 100:.2f} %",
                "total_price": f"{(res['items']['total_price'] / n) * 100:.2f} %",
            },
            "time_seconds": f"{elapsed:.2f} seconds",
            "price": "$0.02",
        }

        print("\n" + "=" * 50)
        print("INVOICE PROCESSING BENCHMARK RESULTS")
        print("=" * 50)

        print(f"\nSeller Name: {result['seller_name']}")
        print(f"Sum Total Quantity: {result['sum_total_quantity']}")
        print(f"Sum Total Price: {result['sum_total_price']}")
        print(f"Currency: {result['currency']}")
        print(f"n_items: {result['n_items']}")
        print(f"Item Count Match: {result['item_count_match']}")
        print(f"Missing Items: {result['missing_items']}")
        print(f"Extra Items: {result['extra_items']}")

        print("\nItems:")
        print(f"  item_name: {result['items']['item_name']}")
        print(f"  quantity: {result['items']['quantity']}")
        print(f"  unit_price: {result['items']['unit_price']}")
        print(f"  total_price: {result['items']['total_price']}")

        print(f"\nOverall Score: {overall_score:.2f} %")
        print(f"Time: {result['time_seconds']}")
        print(f"Price: {result['price']}")
        print("=" * 50)

        if args.out is None:
            os.makedirs("reports", exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            args.out = f"reports/report_invoice_{ts}.json"
        else:
            os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)


        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\nDetailed report saved to: {args.out}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
