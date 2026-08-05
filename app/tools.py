import json
from datetime import datetime
from typing import Any

from app.data import get_order, get_orders_for_customer, validate_order_ownership

_initiated_returns: dict[str, dict] = {}
_initiated_exchanges: dict[str, dict] = {}
_applied_credits: set[str] = set()

NON_RETURNABLE_CATEGORIES = {"innerwear", "jewellery", "beauty", "fragrance", "face_masks", "gift_cards"}

_POLICY_SECTIONS = {
    "shipping": {
        "title": "Shipping",
        "keywords": ["shipping", "delivery", "dispatch", "ship", "carrier", "tracking", "transit", "parcel"],
        "section": "1",
        "content": (
            "1.1 Dispatch: Orders before 2 PM IST on business days ship same day. After 2 PM / weekends / holidays -> next business day.\n"
            "1.2 Delivery estimates: Metro 2-4 business days, Non-metro 4-7, Remote up to 10. These are estimates, not guarantees.\n"
            "1.3 Shipping charges: Free on orders 1,499+. Below 1,499 -> 99 flat. Express -> 199 flat (not available for COD).\n"
            "1.4 Partial shipments: Backordered items ship separately at no extra cost.\n"
            "1.5 Delayed orders: >3 business days past expected delivery -> eligible for 250 store credit on request. No need to cancel.\n"
            "1.6 Lost parcels: No tracking movement for 10 days or carrier marks lost -> lost-parcel claim handled by human agent (not a return). Resolution in 5 business days: free replacement or full refund.\n"
            "1.7 Address changes: Only before dispatch. After dispatch -> refuse delivery and reorder."
        ),
    },
    "returns": {
        "title": "Returns",
        "keywords": ["return", "send back", "give back", "return window", "returnable", "non-returnable"],
        "section": "2",
        "content": (
            "2.1 Return window: 30 calendar days from DELIVERY date (not order date). No exceptions after 30 days.\n"
            "2.2 Condition: Items must be unworn, unwashed, with original tags and packaging.\n"
            "2.3 Non-returnable: Innerwear/socks, jewellery, beauty/fragrance, face masks, gift cards -- for hygiene/safety.\n"
            "2.4 Final sale: Size exchange ONLY -- no refunds, no store credit. 30-day window still applies.\n"
            "2.5 Footwear: Returnable but must include original shoe box. Without box -> 300 deduction.\n"
            "2.6 Cancelled orders: No return can be raised on a cancelled order."
        ),
    },
    "refunds": {
        "title": "Refunds",
        "keywords": ["refund", "money back", "credit", "reimbursement", "payment"],
        "section": "3",
        "content": (
            "3.1 Timelines (after warehouse inspection, 2-3 business days):\n"
            "  - Credit/debit card -> original card, 5-7 business days\n"
            "  - UPI -> original UPI ID, 3-5 business days\n"
            "  - Cash on delivery -> bank transfer or store credit, 7-10 business days\n"
            "  - Store credit -> immediate\n"
            "3.2 Shipping fee refund: Only if return is due to Trendly error (wrong/damaged/defective item). Not for change-of-mind.\n"
            "3.3 COD refunds: Require bank account details collected by human agent via secure link. NEVER collect in chat.\n"
            "3.4 Partial refunds: Only returned items are refunded. Free-shipping eligibility not recalculated."
        ),
    },
    "exchanges": {
        "title": "Exchanges",
        "keywords": ["exchange", "swap", "different size", "size change", "size exchange"],
        "section": "4",
        "content": (
            "4.1 Scope: SIZE exchanges only. Not colour or style. For colour/style -> return + new order.\n"
            "4.2 Window: Same 30-day window as returns.\n"
            "4.3 Availability: If requested size unavailable -> auto-converted to refund (3).\n"
            "4.4 Limit: One exchange per item. Second exchange -> requires human approval."
        ),
    },
    "return_pickup": {
        "title": "Return Pickup",
        "keywords": ["pickup", "pick up", "reverse pickup", "self-ship", "courier", "collect"],
        "section": "5",
        "content": (
            "5.1 Free reverse pickup on serviceable pincodes. Customer schedules window; carrier tries up to 2 times.\n"
            "5.2 Non-serviceable pincodes: Customer self-ships, reimbursed up to 150 against receipt.\n"
            "5.3 After 2 failed pickups: Return is closed, must be re-raised if within 30-day window."
        ),
    },
    "damaged_wrong": {
        "title": "Damaged or Wrong Items",
        "keywords": ["damaged", "broken", "wrong item", "incorrect", "defective", "faulty"],
        "section": "6",
        "content": (
            "6.1 Reporting window: 48 hours from delivery, with photographs.\n"
            "6.2 Resolution: Free replacement or full refund (including shipping), customer's choice. "
            "Non-returnable categories ARE covered when item arrives damaged/incorrect."
        ),
    },
    "restrictions": {
        "title": "What the Assistant Must Not Do",
        "keywords": ["discount", "coupon", "waiver", "bank account", "card number"],
        "section": "7",
        "content": (
            "- No discounts, coupons, waivers, or goodwill credits not in policy\n"
            "- No collecting bank/card/CVV in chat\n"
            "- No medical, legal, or financial advice\n"
            "- No confirming/discussing another customer's orders\n"
            "- No inventing policy -- say 'I don't know' and offer human agent"
        ),
    },
}


def _today() -> datetime:
    return datetime.utcnow()


def _parse_date(date_str: str) -> datetime:
    if date_str is None:
        return None
    if "T" in date_str:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
    return datetime.strptime(date_str, "%Y-%m-%d")


def _days_since(date_str: str) -> int:
    if date_str is None:
        return -1
    return (_today() - _parse_date(date_str)).days


def _is_within_return_window(delivered_at: str) -> bool:
    if delivered_at is None:
        return False
    days = _days_since(delivered_at)
    return 0 <= days <= 30


def _is_non_returnable(category: str) -> bool:
    return category.lower() in NON_RETURNABLE_CATEGORIES


def _format_currency(amount: int) -> str:
    return f"Rs.{amount:,}"


# --- Tool implementations ---

def list_customer_orders(customer_id: str) -> str:
    orders = get_orders_for_customer(customer_id)
    if not orders:
        return json.dumps({"success": True, "count": 0, "orders": [], "message": "No orders found under this account."})

    summary = []
    for o in orders:
        summary.append({
            "order_id": o["order_id"],
            "status": o["status"],
            "placed_at": o["placed_at"],
            "total": _format_currency(o["total"]),
            "items_count": len(o.get("items", []))
        })
    return json.dumps({"success": True, "count": len(summary), "orders": summary})


def lookup_order(order_id: str, customer_id: str) -> str:

    if not validate_order_ownership(order_id, customer_id):
        return json.dumps({"success": False, "error": "Order not found under this customer's account. Please double-check the order number."})

    order = get_order(order_id)
    if order is None:
        return json.dumps({"success": False, "error": "Order not found."})

    status_descriptions = {
        "in_transit": "Your order is on its way and currently in transit.",
        "delivered": "Your order has been delivered.",
        "partially_shipped": "Part of your order has shipped. Some items are backordered and will ship separately.",
        "delayed": "Your order is delayed beyond the expected delivery date. We sincerely apologize for the inconvenience.",
        "lost_in_transit": "Your order appears to have been lost in transit. This requires immediate attention from our team.",
        "cancelled": "This order has been cancelled.",
    }

    result = {
        "success": True,
        "order_id": order["order_id"],
        "status": order["status"],
        "status_description": status_descriptions.get(order["status"], order["status"]),
        "placed_at": order["placed_at"],
        "expected_delivery": order.get("expected_delivery"),
        "delivered_at": order.get("delivered_at"),
        "carrier": order.get("carrier"),
        "tracking_number": order.get("tracking_number"),
        "payment_method": order["payment_method"],
        "shipping_city": order.get("shipping_city"),
        "total": _format_currency(order["total"]),
        "items": [],
    }

    for item in order["items"]:
        item_info = {
            "name": item["name"],
            "sku": item["sku"],
            "category": item["category"],
            "size": item["size"],
            "qty": item["qty"],
            "price": _format_currency(item["price"]),
            "final_sale": item.get("final_sale", False),
        }
        if "shipped" in item:
            item_info["shipped"] = item["shipped"]
            if not item["shipped"] and "backorder_eta" in item:
                item_info["backorder_eta"] = item["backorder_eta"]
        result["items"].append(item_info)

    if order["status"] == "delayed":
        expected = order.get("expected_delivery")
        if expected:
            days_past = _days_since(expected)
            result["days_past_expected"] = days_past
            result["eligible_for_delay_credit"] = days_past > 3
            result["delay_credit_amount"] = "Rs.250"

    if order["status"] == "cancelled":
        result["cancelled_at"] = order.get("cancelled_at")
        result["refund_status"] = order.get("refund_status")

    return json.dumps(result, default=str)


def check_return_eligibility(order_id: str, customer_id: str, sku: str) -> str:
    if not validate_order_ownership(order_id, customer_id):
        return json.dumps({"eligible": False, "reason": "Order not found under this customer's account."})

    order = get_order(order_id)
    if order is None:
        return json.dumps({"eligible": False, "reason": "Order not found."})

    if order["status"] == "cancelled":
        return json.dumps({
            "eligible": False,
            "reason": f"This order has been cancelled. Returns cannot be raised on cancelled orders. Refund status: {order.get('refund_status', 'unknown')}."
        })

    if order["status"] == "lost_in_transit":
        return json.dumps({
            "eligible": False,
            "reason": "This order is marked as lost in transit. This is a lost-parcel claim, not a return. It must be escalated to a human support agent for resolution.",
            "action_required": "escalate_to_human"
        })

    if order["status"] not in ("delivered",):
        return json.dumps({
            "eligible": False,
            "reason": f"This order has not been delivered yet (status: {order['status']}). Returns can only be raised after delivery."
        })

    item = None
    for i in order["items"]:
        if i["sku"] == sku:
            item = i
            break

    if item is None:
        available = [{"sku": i["sku"], "name": i["name"], "category": i["category"]} for i in order["items"]]
        return json.dumps({"eligible": False, "reason": f"Item with SKU {sku} not found in this order.", "available_items": available})

    if not _is_within_return_window(order["delivered_at"]):
        days = _days_since(order["delivered_at"])
        return json.dumps({
            "eligible": False,
            "reason": f"The 30-day return window has expired. This order was delivered {days} days ago. Unfortunately, returns are not accepted after 30 calendar days from delivery."
        })

    if _is_non_returnable(item["category"]):
        return json.dumps({
            "eligible": False,
            "reason": f"'{item['name']}' is in the '{item['category']}' category, which is non-returnable for hygiene and safety reasons. This applies to innerwear/socks, jewellery, beauty/fragrance, face masks, and gift cards."
        })

    if item.get("final_sale", False):
        return json.dumps({
            "eligible": False,
            "reason": f"'{item['name']}' is marked as final sale. Final sale items are not eligible for refund or store credit. However, a SIZE EXCHANGE is available within the 30-day window. Would the customer like to exchange for a different size instead?",
            "exchange_available": True
        })

    result = {
        "eligible": True,
        "order_id": order_id,
        "item": {"sku": item["sku"], "name": item["name"], "size": item["size"], "price": _format_currency(item["price"]), "category": item["category"]},
        "payment_method": order["payment_method"],
        "notes": [],
    }

    if item["category"] == "footwear":
        result["notes"].append("Footwear must be returned in its original shoe box. Returns without the box will incur a Rs.300 deduction.")

    if order["payment_method"] == "cash_on_delivery":
        result["notes"].append("This was a cash-on-delivery order. A human agent will collect bank account details through a secure link for the refund.")

    refund_timelines = {
        "credit_card": "5-7 business days to original card",
        "prepaid_card": "5-7 business days to original card",
        "debit_card": "5-7 business days to original card",
        "upi": "3-5 business days to original UPI ID",
        "cash_on_delivery": "7-10 business days via bank transfer or store credit",
        "store_credit": "Immediate as store credit",
    }
    result["refund_timeline"] = refund_timelines.get(order["payment_method"], "Please contact support for refund timeline details.")

    return json.dumps(result)


def check_exchange_eligibility(order_id: str, customer_id: str, sku: str) -> str:
    if not validate_order_ownership(order_id, customer_id):
        return json.dumps({"eligible": False, "reason": "Order not found under this customer's account."})

    order = get_order(order_id)
    if order is None:
        return json.dumps({"eligible": False, "reason": "Order not found."})

    if order["status"] == "cancelled":
        return json.dumps({"eligible": False, "reason": "This order has been cancelled. Exchanges cannot be raised on cancelled orders."})

    if order["status"] == "lost_in_transit":
        return json.dumps({"eligible": False, "reason": "This order is lost in transit and must be escalated to a human agent.", "action_required": "escalate_to_human"})

    if order["status"] not in ("delivered",):
        return json.dumps({"eligible": False, "reason": f"Order not delivered yet (status: {order['status']}). Exchanges are only available after delivery."})

    item = None
    for i in order["items"]:
        if i["sku"] == sku:
            item = i
            break

    if item is None:
        available = [{"sku": i["sku"], "name": i["name"]} for i in order["items"]]
        return json.dumps({"eligible": False, "reason": f"Item {sku} not found in this order.", "available_items": available})

    if not _is_within_return_window(order["delivered_at"]):
        days = _days_since(order["delivered_at"])
        return json.dumps({"eligible": False, "reason": f"The 30-day exchange window has expired ({days} days since delivery)."})

    if _is_non_returnable(item["category"]):
        return json.dumps({"eligible": False, "reason": f"'{item['name']}' ({item['category']}) cannot be exchanged for hygiene and safety reasons."})

    exchange_key = f"{order_id}:{sku}"
    if exchange_key in _initiated_exchanges:
        return json.dumps({"eligible": False, "reason": "This item has already been exchanged once. A second exchange requires human approval.", "action_required": "escalate_to_human"})

    result = {
        "eligible": True,
        "order_id": order_id,
        "item": {"sku": item["sku"], "name": item["name"], "current_size": item["size"], "price": _format_currency(item["price"]), "final_sale": item.get("final_sale", False)},
        "exchange_type": "size_only",
        "notes": [],
    }

    if item.get("final_sale", False):
        result["notes"].append("This is a final sale item. Only size exchange is available -- no refund or store credit.")

    if item["category"] == "footwear":
        result["notes"].append("Footwear must be returned in its original shoe box.")

    if order["payment_method"] == "cash_on_delivery" and not item.get("final_sale", False):
        result["notes"].append("Note: If the requested size is unavailable, this exchange will convert to a refund. For COD orders, a human agent will collect bank details via secure link.")

    return json.dumps(result)


def initiate_return(order_id: str, customer_id: str, sku: str, reason: str) -> str:
    eligibility = json.loads(check_return_eligibility(order_id, customer_id, sku))
    if not eligibility.get("eligible"):
        return json.dumps({"success": False, "error": eligibility.get("reason", "Item is not eligible for return.")})

    return_id = f"RET-{order_id}-{sku[-3:]}"
    _initiated_returns[return_id] = {
        "return_id": return_id, "order_id": order_id, "sku": sku,
        "customer_id": customer_id, "reason": reason,
        "status": "initiated", "created_at": _today().isoformat(),
    }

    order = get_order(order_id)
    result = {
        "success": True,
        "return_id": return_id,
        "message": "Return has been initiated successfully.",
        "next_steps": [
            "A reverse pickup will be scheduled. You'll receive an email/SMS with the pickup window.",
            "Please keep the item unworn with original tags and packaging ready.",
        ],
    }

    item = next((i for i in order["items"] if i["sku"] == sku), None)
    if item and item["category"] == "footwear":
        result["next_steps"].append("Please include the original shoe box. Returns without the box will have a Rs.300 deduction.")

    if order["payment_method"] == "cash_on_delivery":
        result["next_steps"].append("Since this was a cash-on-delivery order, a human agent will reach out with a secure link to collect your bank details for the refund.")
        result["requires_human_followup"] = True

    refund_timelines = {
        "credit_card": "5-7 business days after inspection",
        "prepaid_card": "5-7 business days after inspection",
        "debit_card": "5-7 business days after inspection",
        "upi": "3-5 business days after inspection",
        "cash_on_delivery": "7-10 business days after inspection",
        "store_credit": "Immediate after inspection",
    }
    result["refund_timeline"] = refund_timelines.get(order["payment_method"], "Contact support for details")
    result["inspection_note"] = "Warehouse inspection takes 2-3 business days after receiving the item."

    return json.dumps(result)


def initiate_exchange(order_id: str, customer_id: str, sku: str, new_size: str) -> str:
    eligibility = json.loads(check_exchange_eligibility(order_id, customer_id, sku))
    if not eligibility.get("eligible"):
        return json.dumps({"success": False, "error": eligibility.get("reason", "Item is not eligible for exchange.")})

    exchange_key = f"{order_id}:{sku}"
    exchange_id = f"EXC-{order_id}-{sku[-3:]}"

    _initiated_exchanges[exchange_key] = {
        "exchange_id": exchange_id, "order_id": order_id, "sku": sku,
        "customer_id": customer_id, "new_size": new_size,
        "status": "initiated", "created_at": _today().isoformat(),
    }

    result = {
        "success": True,
        "exchange_id": exchange_id,
        "message": f"Size exchange initiated! We'll send you the item in size {new_size}.",
        "next_steps": [
            "A reverse pickup will be scheduled for the original item.",
            "The new item will be shipped once we receive and inspect the return.",
            "If the requested size is unavailable, this will automatically convert to a refund.",
        ],
        "note": "Only size exchanges are available. For a different colour or style, please return this item and place a new order.",
    }

    order = get_order(order_id)
    item = next((i for i in order["items"] if i["sku"] == sku), None)
    if item and item.get("final_sale", False):
        result["final_sale_note"] = "This is a final sale item. If the requested size is unavailable, we unfortunately cannot issue a refund -- only an exchange is possible."

    return json.dumps(result)


def get_policy_info(topic: str) -> str:
    topic_lower = topic.lower()
    matched_sections = []

    for key, section in _POLICY_SECTIONS.items():
        if any(kw in topic_lower for kw in section["keywords"]):
            matched_sections.append(section)

    if not matched_sections:
        return json.dumps({
            "found": False,
            "message": "No policy section found for this topic. This question should be escalated to a human agent.",
            "support_hours": "9:00 AM - 9:00 PM IST, seven days a week"
        })

    return json.dumps({
        "found": True,
        "sections": [{"title": s["title"], "section_number": s["section"], "content": s["content"]} for s in matched_sections],
    })


def escalate_to_human(order_id: str, customer_id: str, reason: str, summary: str, attempted_actions: str) -> str:
    return json.dumps({
        "escalated": True,
        "escalation_id": f"ESC-{_today().strftime('%Y%m%d%H%M%S')}",
        "message": "I've escalated this to our support team. A human agent will take over shortly. Our support hours are 9:00 AM - 9:00 PM IST, seven days a week.",
        "handoff_summary": {
            "customer_id": customer_id,
            "order_id": order_id,
            "reason": reason,
            "conversation_summary": summary,
            "attempted_actions": attempted_actions,
        },
    })


def get_delayed_order_credit(order_id: str, customer_id: str) -> str:
    if not validate_order_ownership(order_id, customer_id):
        return json.dumps({"success": False, "error": "Order not found under this customer's account."})

    order = get_order(order_id)
    if order is None:
        return json.dumps({"success": False, "error": "Order not found."})

    if order["status"] != "delayed":
        expected = order.get("expected_delivery")
        if expected and _days_since(expected) > 3 and order.get("delivered_at") is None:
            pass
        else:
            return json.dumps({"success": False, "error": f"Order {order_id} is not delayed (status: {order['status']}). The Rs.250 store credit is only available for delayed orders."})

    if order_id in _applied_credits:
        return json.dumps({"success": False, "error": "A Rs.250 store credit has already been applied for this order's delay."})

    _applied_credits.add(order_id)
    return json.dumps({
        "success": True,
        "message": "A Rs.250 store credit has been applied to your account for the delay. You can use it on your next order. We apologize for the inconvenience.",
        "credit_amount": "Rs.250",
        "order_id": order_id,
    })


# --- OpenAI-compatible function schemas ---

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_order",
            "description": "Look up an order by order ID and return its full details including status, items, tracking, and payment info. Always verify customer ownership.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order ID to look up (e.g., 'TR-4521')"},
                    "customer_id": {"type": "string", "description": "The customer ID to verify ownership against"},
                },
                "required": ["order_id", "customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_return_eligibility",
            "description": "Check whether a specific item in an order is eligible for return/refund. Evaluates order status, 30-day window, item category, and final sale status. Must be called before initiating a return.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order ID"},
                    "customer_id": {"type": "string", "description": "The customer ID"},
                    "sku": {"type": "string", "description": "The SKU of the item to check (e.g., 'TR-DRS-014')"},
                },
                "required": ["order_id", "customer_id", "sku"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_exchange_eligibility",
            "description": "Check whether a specific item is eligible for size exchange. Similar to return eligibility but also allows final-sale items. Checks the one-exchange-per-item limit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order ID"},
                    "customer_id": {"type": "string", "description": "The customer ID"},
                    "sku": {"type": "string", "description": "The SKU of the item to check"},
                },
                "required": ["order_id", "customer_id", "sku"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "initiate_return",
            "description": "Initiate a return for an item after eligibility has been confirmed. Only call this AFTER check_return_eligibility returns eligible=true AND the customer has confirmed they want to proceed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order ID"},
                    "customer_id": {"type": "string", "description": "The customer ID"},
                    "sku": {"type": "string", "description": "The SKU of the item to return"},
                    "reason": {"type": "string", "description": "The customer's reason for return (e.g., 'doesn't fit', 'changed mind', 'wrong item')"},
                },
                "required": ["order_id", "customer_id", "sku", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "initiate_exchange",
            "description": "Initiate a size exchange for an item after eligibility has been confirmed. Only SIZE exchanges are supported (not colour or style). Call after check_exchange_eligibility returns eligible=true and customer confirms.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order ID"},
                    "customer_id": {"type": "string", "description": "The customer ID"},
                    "sku": {"type": "string", "description": "The SKU of the item to exchange"},
                    "new_size": {"type": "string", "description": "The new size the customer wants (e.g., 'L', '42', 'M')"},
                },
                "required": ["order_id", "customer_id", "sku", "new_size"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_policy_info",
            "description": "Look up Trendly's shipping and returns policy by topic. Use this to answer policy questions with exact policy text. Topics: shipping, returns, refunds, exchanges, pickup, damaged items, restrictions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "enum": ["shipping", "returns", "refunds", "exchanges", "return_pickup", "damaged_wrong", "restrictions"],
                        "description": "The topic section to look up.",
                    },
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": "Escalate the conversation to a human support agent. Use when: 1) The issue is a lost-parcel claim, 2) A second exchange is needed on the same item, 3) The customer needs COD refund bank details collected, 4) The policy document doesn't cover the customer's question, 5) The customer explicitly asks for a human agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The relevant order ID, or 'N/A' if no order is involved"},
                    "customer_id": {"type": "string", "description": "The customer ID"},
                    "reason": {"type": "string", "description": "Brief reason for escalation"},
                    "summary": {"type": "string", "description": "Summary of the conversation and what the customer needs"},
                    "attempted_actions": {"type": "string", "description": "What the AI agent already checked or attempted before escalating"},
                },
                "required": ["order_id", "customer_id", "reason", "summary", "attempted_actions"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_customer_orders",
            "description": "List all orders belonging to the customer. Call this whenever the customer asks for a list of their orders or how many orders they have.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "The customer ID to retrieve orders for"},
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_delayed_order_credit",
            "description": "Apply the Rs.250 store credit for a delayed order (per policy 1.5). Only valid for orders delayed more than 3 business days past expected delivery.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The delayed order ID"},
                    "customer_id": {"type": "string", "description": "The customer ID"},
                },
                "required": ["order_id", "customer_id"],
            },
        },
    },
]


TOOL_REGISTRY: dict[str, callable] = {
    "list_customer_orders": list_customer_orders,
    "lookup_order": lookup_order,
    "check_return_eligibility": check_return_eligibility,
    "check_exchange_eligibility": check_exchange_eligibility,
    "initiate_return": initiate_return,
    "initiate_exchange": initiate_exchange,
    "get_policy_info": get_policy_info,
    "escalate_to_human": escalate_to_human,
    "get_delayed_order_credit": get_delayed_order_credit,
}


def execute_tool(name: str, arguments: dict) -> str:
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        return fn(**arguments)
    except TypeError as e:
        return json.dumps({"error": f"Invalid arguments for {name}: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Tool execution failed: {str(e)}"})
