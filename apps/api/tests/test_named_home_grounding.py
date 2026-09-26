from app.models.property import GeographicPrecision
from app.services.geographic_resolution import geographic_resolver


def test_named_home_prefers_provider_place_over_internal_unit(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "status": "1",
                "count": "1",
                "geocodes": [{
                    "formatted_address": "四川省成都市郫都区龙湖·时代天街",
                    "province": "四川省",
                    "city": "成都市",
                    "district": "郫都区",
                    "location": "103.920730,30.753792",
                    "level": "住宅区",
                }],
            }

    monkeypatch.setattr("httpx.get", lambda *_args, **_kwargs: Response())

    result = geographic_resolver.resolve("龙湖时代天街", "成都市", "server-key")

    assert result.status == "GROUNDED"
    assert result.geographic_identity == "四川省成都市郫都区龙湖·时代天街"
    assert result.geographic_precision == GeographicPrecision.PLACE
    assert (result.lng, result.lat) == (103.920730, 30.753792)
