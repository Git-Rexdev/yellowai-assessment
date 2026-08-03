import pytest
import json
from app.tools import (
    lookup_order,
    check_return_eligibility,
    check_exchange_eligibility,
    initiate_return,
    initiate_exchange,
    get_policy_info,
    escalate_to_human,
    get_delayed_order_credit,
)

def test_lookup_cross_customer_access():
    result = json.loads(lookup_order("TR-4530", "C-100"))
    assert not result["success"]
    assert "not found under this customer's account" in result["error"]

def test_tr4521_in_transit():
    result = json.loads(lookup_order("TR-4521", "C-100"))
    assert result["success"]
    assert result["status"] == "in_transit"

    ret_el = json.loads(check_return_eligibility("TR-4521", "C-100", "TR-DRS-014"))
    assert not ret_el["eligible"]
    assert "not been delivered yet" in ret_el["reason"]

def test_tr4522_mixed_items():
    apparel_el = json.loads(check_return_eligibility("TR-4522", "C-101", "TR-TSH-002"))
    assert apparel_el["eligible"]

    socks_el = json.loads(check_return_eligibility("TR-4522", "C-101", "TR-SOK-031"))
    assert not socks_el["eligible"]
    assert "innerwear/socks" in socks_el["reason"] or "hygiene" in socks_el["reason"]

def test_tr4523_expired_window():
    ret_el = json.loads(check_return_eligibility("TR-4523", "C-102", "TR-JKT-008"))
    assert not ret_el["eligible"]
    assert "expired" in ret_el["reason"] or "30 days" in ret_el["reason"]

def test_tr4524_partially_shipped():
    result = json.loads(lookup_order("TR-4524", "C-100"))
    assert result["success"]
    assert result["status"] == "partially_shipped"
    belt_item = next(i for i in result["items"] if i["sku"] == "TR-BLT-005")
    assert not belt_item["shipped"]
    assert "backorder_eta" in belt_item

    ret_el = json.loads(check_return_eligibility("TR-4524", "C-100", "TR-JNS-021"))
    assert not ret_el["eligible"]
    assert "not been delivered yet" in ret_el["reason"]

def test_tr4525_delayed_credit():
    result = json.loads(lookup_order("TR-4525", "C-103"))
    assert result["success"]
    assert result["status"] == "delayed"
    assert result.get("eligible_for_delay_credit")

    credit_res = json.loads(get_delayed_order_credit("TR-4525", "C-103"))
    assert credit_res["success"]
    assert "250" in credit_res["message"]

    credit_res2 = json.loads(get_delayed_order_credit("TR-4525", "C-103"))
    assert not credit_res2["success"]
    assert "already been applied" in credit_res2["error"]

def test_tr4526_lost_in_transit():
    ret_el = json.loads(check_return_eligibility("TR-4526", "C-101", "TR-BAG-011"))
    assert not ret_el["eligible"]
    assert ret_el["action_required"] == "escalate_to_human"

def test_tr4527_jewellery():
    ret_el = json.loads(check_return_eligibility("TR-4527", "C-102", "TR-EAR-042"))
    assert not ret_el["eligible"]
    assert "jewellery" in ret_el["reason"]
    assert "expired" not in ret_el["reason"]

def test_tr4528_final_sale():
    ret_el = json.loads(check_return_eligibility("TR-4528", "C-103", "TR-SHR-009"))
    assert not ret_el["eligible"]
    assert "final sale" in ret_el["reason"].lower()
    assert ret_el.get("exchange_available")

    exc_el = json.loads(check_exchange_eligibility("TR-4528", "C-103", "TR-SHR-009"))
    assert exc_el["eligible"]

def test_tr4529_cancelled():
    result = json.loads(lookup_order("TR-4529", "C-100"))
    assert result["success"]
    assert result["status"] == "cancelled"
    assert "refund_status" in result

    ret_el = json.loads(check_return_eligibility("TR-4529", "C-100", "TR-SCF-027"))
    assert not ret_el["eligible"]
    assert "cancelled" in ret_el["reason"]

def test_tr4530_happy_path_and_exchange_limit():
    ret_el = json.loads(check_return_eligibility("TR-4530", "C-101", "TR-KRT-033"))
    assert ret_el["eligible"]

    ret_init = json.loads(initiate_return("TR-4530", "C-101", "TR-KRT-033", "doesn't fit"))
    assert ret_init["success"]
    assert "return_id" in ret_init

    exc_el = json.loads(check_exchange_eligibility("TR-4530", "C-101", "TR-KRT-033"))
    assert exc_el["eligible"]

    exc_init = json.loads(initiate_exchange("TR-4530", "C-101", "TR-KRT-033", "M"))
    assert exc_init["success"]

    exc_el2 = json.loads(check_exchange_eligibility("TR-4530", "C-101", "TR-KRT-033"))
    assert not exc_el2["eligible"]
    assert exc_el2["action_required"] == "escalate_to_human"

def test_policy_lookup():
    pol_ret = json.loads(get_policy_info("returns"))
    assert pol_ret["found"]
    pol_bad = json.loads(get_policy_info("random_unknown_topic"))
    assert not pol_bad["found"]

def test_escalation():
    esc = json.loads(escalate_to_human("TR-4530", "C-101", "unhappy", "customer unhappy", "none"))
    assert esc["escalated"]
    assert "escalation_id" in esc
    assert esc["handoff_summary"]["reason"] == "unhappy"
