import json

import pytest

from app.services.decision_signal_intelligence import decision_signal_intelligence
from app.services.profile_intelligence import profile_intelligence


@pytest.mark.parametrize("message", [
    "打算去北京中关村工作，预算6000，通勤30分钟",
    "我要去北京的中关村工作，预算6000，通勤30分钟",
])
def test_equivalent_work_expressions_keep_explicit_geography(monkeypatch, message):
    payload = {
        "decision_intent": {"established": True, "type": "work_location"},
        "decision_geography": {
            "identity": "北京中关村", "city": "北京", "locality": "中关村", "source": "USER",
        },
        "work_location": None,
    }
    monkeypatch.setattr("app.services.decision_signal_intelligence.ai_client.generate_json",
                        lambda *args, **kwargs: json.dumps(payload))
    signal = decision_signal_intelligence.analyze(message)
    assert signal.identity == "北京的中关村"
    assert signal.intent_established and signal.identity_source == "USER"
    profile = profile_intelligence._build_analysis(json.dumps(payload), message)
    assert profile.patch.work_location == "北京的中关村"


@pytest.mark.parametrize("identity,source", [
    ("上海的中关村", "USER"),
    ("北京的融科资讯中心", "USER"),
    ("北京的中关村", "INFERRED"),
])
def test_normalization_cannot_add_city_place_or_promote_inference(identity, source):
    signal = profile_intelligence._build_decision_geography({
        "decision_intent": {"established": True, "type": "work_location"},
        "decision_geography": {"identity": identity, "source": source},
    }, "打算去北京中关村工作，预算6000，通勤30分钟")
    assert not signal.intent_established


def test_planning_to_search_for_a_job_does_not_establish_work():
    analysis = profile_intelligence._build_analysis("{}", "打算去北京找工作")
    assert analysis.patch.work_location is None
