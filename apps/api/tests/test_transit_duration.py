from app.services.transit_duration import transit_duration_service


class Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def test_transit_duration_converts_seconds_to_minutes(monkeypatch) -> None:
    monkeypatch.setattr(
        "httpx.get",
        lambda *_args, **_kwargs: Response(
            {
                "status": "1",
                "route": {
                    "transits": [
                        {
                            "cost": {"duration": "1801"},
                            "segments": [
                                {
                                    "bus": {
                                        "buslines": [{"type": "地铁线路"}]
                                    }
                                }
                            ],
                        }
                    ]
                },
            }
        ),
    )

    assert transit_duration_service.calculate_minutes(
        origin_lng=113.9,
        origin_lat=22.5,
        destination_lng=113.92,
        destination_lat=22.51,
        api_key="test-key",
    ) == 31


def test_transit_duration_returns_none_without_valid_route(monkeypatch) -> None:
    monkeypatch.setattr(
        "httpx.get",
        lambda *_args, **_kwargs: Response({"status": "1", "route": {"transits": []}}),
    )

    assert transit_duration_service.calculate_minutes(
        origin_lng=113.9,
        origin_lat=22.5,
        destination_lng=113.92,
        destination_lat=22.51,
        api_key="test-key",
    ) is None


def test_transit_duration_rejects_bus_only_route(monkeypatch) -> None:
    monkeypatch.setattr(
        "httpx.get",
        lambda *_args, **_kwargs: Response(
            {
                "status": "1",
                "route": {
                    "transits": [
                        {
                            "cost": {"duration": "1200"},
                            "segments": [
                                {
                                    "bus": {
                                        "buslines": [{"type": "普通公交线路"}]
                                    }
                                }
                            ],
                        }
                    ]
                },
            }
        ),
    )

    assert transit_duration_service.calculate_minutes(
        origin_lng=113.9,
        origin_lat=22.5,
        destination_lng=113.92,
        destination_lat=22.51,
        api_key="test-key",
    ) is None
