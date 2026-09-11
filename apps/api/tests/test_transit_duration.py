from app.models.property import CommuteMode
from app.services.transit_duration import transit_duration_service


class Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def route_payload(collection: str, *durations: int) -> dict:
    return {
        "status": "1",
        "route": {
            collection: [{"cost": {"duration": str(value)}} for value in durations]
        },
    }


def install_routes(monkeypatch, *, walking: dict, transit: dict) -> None:
    def get(endpoint: str, **_kwargs) -> Response:
        return Response(walking if endpoint.endswith("/walking") else transit)

    monkeypatch.setattr("httpx.get", get)


def calculate():
    return transit_duration_service.calculate_living_time(
        origin_lng=113.9,
        origin_lat=22.5,
        destination_lng=113.92,
        destination_lat=22.51,
        api_key="test-key",
    )


def test_walking_only_route_is_viable(monkeypatch) -> None:
    install_routes(
        monkeypatch,
        walking=route_payload("paths", 1200),
        transit=route_payload("transits"),
    )

    result = calculate()

    assert result is not None
    assert result.minutes == 20
    assert result.mode == CommuteMode.WALKING


def test_bus_only_public_transit_route_is_viable(monkeypatch) -> None:
    install_routes(
        monkeypatch,
        walking=route_payload("paths", 2400),
        transit=route_payload("transits", 1200),
    )

    result = calculate()

    assert result is not None
    assert result.minutes == 20
    assert result.mode == CommuteMode.PUBLIC_TRANSIT


def test_metro_route_remains_valid_public_transit(monkeypatch) -> None:
    install_routes(
        monkeypatch,
        walking=route_payload("paths", 2400),
        transit={
            "status": "1",
            "route": {
                "transits": [
                    {
                        "cost": {"duration": "1801"},
                        "segments": [
                            {"bus": {"buslines": [{"type": "地铁线路"}]}}
                        ],
                    }
                ]
            },
        },
    )

    result = calculate()

    assert result is not None
    assert result.minutes == 31
    assert result.mode == CommuteMode.PUBLIC_TRANSIT


def test_shorter_walking_route_wins(monkeypatch) -> None:
    install_routes(
        monkeypatch,
        walking=route_payload("paths", 901),
        transit=route_payload("transits", 1200),
    )

    result = calculate()

    assert result is not None
    assert result.minutes == 16
    assert result.mode == CommuteMode.WALKING


def test_both_route_modes_failure_returns_unknown(monkeypatch) -> None:
    install_routes(
        monkeypatch,
        walking=route_payload("paths"),
        transit=route_payload("transits"),
    )

    assert calculate() is None


def test_calculate_minutes_remains_compatible(monkeypatch) -> None:
    install_routes(
        monkeypatch,
        walking=route_payload("paths", 1200),
        transit=route_payload("transits", 1800),
    )

    assert transit_duration_service.calculate_minutes(
        origin_lng=113.9,
        origin_lat=22.5,
        destination_lng=113.92,
        destination_lat=22.51,
        api_key="test-key",
    ) == 20
