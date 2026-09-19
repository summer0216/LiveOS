import pytest

from app.services import decision_geography_service as module
from app.services.geographic_resolution import GeographicResolutionResult


@pytest.mark.parametrize("local_grounded", [True, False])
def test_explicit_city_particle_uses_existing_contextual_resolution(
    monkeypatch, local_grounded,
):
    calls = []

    def resolve(identity, context, key):
        calls.append((identity, context))
        if identity == "北京":
            return GeographicResolutionResult(
                status="GROUNDED", geographic_identity="北京市",
                geographic_scope="CITY", lng=116.407387, lat=39.904179,
            )
        return GeographicResolutionResult(status="UNRESOLVED")

    def local(identity, context, key):
        assert (identity, context) == ("中关村", "北京市")
        return GeographicResolutionResult(
            status="GROUNDED" if local_grounded else "UNRESOLVED",
            geographic_identity="北京市中关村", geographic_scope="LOCAL",
            lng=116.321669, lat=39.985266,
        )

    monkeypatch.setattr(module.geographic_resolver, "resolve", resolve)
    monkeypatch.setattr(module.geographic_resolver, "resolve_local_area", local)
    monkeypatch.setattr(module.decision_geography_store, "save", lambda _, state: state)
    monkeypatch.setattr(module.decision_geography_service, "_current_city_context",
                        lambda *args: pytest.fail("Explicit city must own context"))
    result = module.decision_geography_service.apply(
        "fresh", intent_established=True, intent_type="work_location",
        identity="北京的中关村", identity_source="USER", api_key="key",
        current_geographic_reality=(104.06, 30.67),
    )
    assert calls == [("北京的中关村", None), ("北京", None), ("中关村", "北京市")]
    assert result.status == ("GROUNDED" if local_grounded else "UNRESOLVED")
    assert result.lng == (116.321669 if local_grounded else None)
