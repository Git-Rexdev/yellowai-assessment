import json
import os
from typing import Optional

_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "orders.json")

with open(_DATA_PATH, "r", encoding="utf-8") as f:
    _raw = json.load(f)

_customers: dict[str, dict] = {c["customer_id"]: c for c in _raw["customers"]}
_orders: dict[str, dict] = {o["order_id"]: o for o in _raw["orders"]}


def get_customer(customer_id: str) -> Optional[dict]:
    return _customers.get(customer_id)


def get_order(order_id: str) -> Optional[dict]:
    order = _orders.get(order_id)
    if order is None:
        return None
    return {k: v for k, v in order.items() if not k.startswith("_")}


def get_orders_for_customer(customer_id: str) -> list[dict]:
    return [
        {k: v for k, v in o.items() if not k.startswith("_")}
        for o in _orders.values()
        if o["customer_id"] == customer_id
    ]


def validate_order_ownership(order_id: str, customer_id: str) -> bool:
    order = _orders.get(order_id)
    if order is None:
        return False
    return order["customer_id"] == customer_id


def list_customer_ids() -> list[str]:
    return list(_customers.keys())


def get_all_customers() -> list[dict]:
    return list(_customers.values())
