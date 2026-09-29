import json

from app.services.living_meaning_service import LivingMeaningService


def test_observed_reality_rejects_precision_only_unknown_and_selects_another():
    observation = "晚上去看了，关窗以后还是能明显听到路上的车声。"
    basis = {
        "HOME_IDENTITY": "融科·昆仑巢",
        "WORK_IDENTITY": "融科资讯中心",
        "WORK_COMMUTE": "1min WALKING",
        "GROCERY_WALK": "7min WALKING",
        "RENT_REALITY": "6300 CNY/month",
        "BUDGET_REALITY": "6000 CNY/month",
        "INDOOR_SOUND_OBSERVATION": observation,
    }
    meaning = "通勤与日常采购便利，但租金超预算且夜间关窗后仍能听到车声。"
    judgment = "这是以预算压力和夜间安静程度换取短通勤的生活选择。"
    precision_question = "关窗后夜间室内噪音实测是多少分贝？"
    replacement_question = "住所的实际起居空间能否满足日常使用？"

    class Intelligence:
        def __init__(self):
            self.calls = []

        def generate_json(self, prompt, **_kwargs):
            self.calls.append(prompt)
            assert observation in prompt
            if "Judge whether this proposed Unknown" in prompt:
                is_precision = precision_question in prompt
                return json.dumps({
                    "question_reference": precision_question if is_precision else replacement_question,
                    "judgment_reference": judgment,
                    "current_reality_sufficient": is_precision,
                    "material_decision_change": not is_precision,
                    "single_observable_fact": True,
                    "impact_without_unsupported_bridge": True,
                    "sufficient_dimension": "室内噪音" if is_precision else "",
                    "plausible_answer_a": "" if is_precision else "起居空间足够",
                    "impact_a": "" if is_precision else "便利与成本权衡仍成立",
                    "plausible_answer_b": "" if is_precision else "起居空间不足",
                    "impact_b": "" if is_precision else "居住限制改变当前权衡",
                    "reason": (
                        "已知关窗后夜间仍明显听到车声；精确数值不改变这一权衡。"
                        if is_precision else "空间是否够用会改变对这套住所的生活判断。"
                    ),
                }, ensure_ascii=False)
            rejected = "Excluded dimensions and reasons:" in prompt
            question = replacement_question if rejected else precision_question
            return json.dumps({
                "unknown_fact": "LIVING_SPACE" if rejected else "EXACT_SOUND_MEASUREMENT",
                "question": question,
                "why_it_matters": (
                    "空间是否够用会改变居住限制与便利的权衡。"
                    if rejected else "精确数值可能改变安静程度的判断。"
                ),
                "meaning_reference": meaning,
                "judgment_reference": judgment,
                "grounding": [
                    {"fact": "INDOOR_SOUND_OBSERVATION", "value": observation},
                    {"fact": "WORK_COMMUTE", "value": "1min WALKING"},
                ],
            }, ensure_ascii=False)

    intelligence = Intelligence()
    service = LivingMeaningService(intelligence=intelligence)
    result = service._generate_meaningful_unknown(basis, meaning, judgment)

    assert basis["INDOOR_SOUND_OBSERVATION"] == observation
    assert result == (replacement_question, "空间是否够用会改变居住限制与便利的权衡。")
    assert len(intelligence.calls) == 4
    assert precision_question in intelligence.calls[1]
    assert precision_question in intelligence.calls[2]


def test_invalid_unknown_proposal_retries_without_forcing_an_unknown():
    basis = {"HOME_IDENTITY": "龙湖时代天街", "LAYOUT_REQUIREMENT": "两室一厅"}
    meaning = "所需户型已明确，实际户型未知。"
    judgment = "实际户型是否满足要求仍待确认。"
    question = "这套住所实际是几室几厅？"

    class Intelligence:
        def __init__(self, *, no_candidate=False):
            self.proposals = 0
            self.no_candidate = no_candidate

        def generate_json(self, prompt, **_kwargs):
            if "Judge whether this proposed Unknown" in prompt:
                return json.dumps({
                    "question_reference": question,
                    "judgment_reference": judgment,
                    "current_reality_sufficient": False,
                    "material_decision_change": True,
                    "single_observable_fact": True,
                    "impact_without_unsupported_bridge": True,
                    "sufficient_dimension": "",
                    "plausible_answer_a": "两室一厅",
                    "impact_a": "满足所需户型",
                    "plausible_answer_b": "一室一厅",
                    "impact_b": "不满足所需户型",
                    "reason": "实际户型决定明确要求是否满足。",
                }, ensure_ascii=False)
            self.proposals += 1
            if self.no_candidate:
                return "null"
            if self.proposals == 1:
                return "{invalid json"
            return json.dumps({
                "unknown_fact": "ACTUAL_LAYOUT",
                "question": question,
                "why_it_matters": "实际户型决定明确要求是否满足。",
                "meaning_reference": meaning,
                "judgment_reference": judgment,
                "grounding": [
                    {"fact": "HOME_IDENTITY", "value": "龙湖时代天街"},
                    {"fact": "LAYOUT_REQUIREMENT", "value": "两室一厅"},
                ],
            }, ensure_ascii=False)

    intelligence = Intelligence()
    service = LivingMeaningService(intelligence=intelligence)
    assert service._generate_meaningful_unknown(basis, meaning, judgment) == (
        question, "实际户型决定明确要求是否满足。",
    )
    assert intelligence.proposals == 2

    no_candidate = Intelligence(no_candidate=True)
    assert LivingMeaningService(intelligence=no_candidate)._generate_meaningful_unknown(
        basis, meaning, judgment,
    ) is None
    assert no_candidate.proposals == 1
