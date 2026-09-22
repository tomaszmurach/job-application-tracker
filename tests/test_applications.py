from datetime import datetime
from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_check(client: AsyncClient) -> None:
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_create_application(
    client: AsyncClient, application_data: dict[str, str | None]
) -> None:
    response = await client.post("/applications", json=application_data)
    assert response.status_code == 201
    data = response.json()
    assert {key: data[key] for key in application_data} == application_data
    assert isinstance(data["id"], int)
    assert isinstance(datetime.fromisoformat(data["applied_at"]), datetime)


async def test_get_application_by_id(
    client: AsyncClient, created_application: dict[str, Any]
) -> None:
    response = await client.get(f"/applications/{created_application['id']}")
    assert response.status_code == 200
    assert response.json() == created_application


async def test_get_nonexistent_application(client: AsyncClient) -> None:
    response = await client.get("/applications/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Application not found"}


async def test_list_and_filter_applications(
    client: AsyncClient, application_data: dict[str, str | None]
) -> None:
    for application_status in ["Applied", "Interview", "Interview"]:
        response = await client.post(
            "/applications", json={**application_data, "status": application_status}
        )
        assert response.status_code == 201

    response = await client.get("/applications")
    assert response.status_code == 200
    assert len(response.json()) == 3

    response = await client.get("/applications", params={"status": "Interview"})
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert all(item["status"] == "Interview" for item in response.json())

    response = await client.get("/applications", params={"status": "Offer"})
    assert response.status_code == 200
    assert response.json() == []


async def test_empty_collection(client: AsyncClient) -> None:
    response = await client.get("/applications")
    assert response.status_code == 200
    assert response.json() == []


async def test_update_preserves_omitted_fields(
    client: AsyncClient, created_application: dict[str, Any]
) -> None:
    url = f"/applications/{created_application['id']}"
    response = await client.patch(url, json={"status": "Interview"})
    expected = {**created_application, "status": "Interview"}
    assert response.status_code == 200
    assert response.json() == expected
    response = await client.get(url)
    assert response.status_code == 200
    assert response.json() == expected


async def test_empty_patch_preserves_application(
    client: AsyncClient, created_application: dict[str, Any]
) -> None:
    response = await client.patch(
        f"/applications/{created_application['id']}", json={}
    )
    assert response.status_code == 200
    assert response.json() == created_application


async def test_patch_clears_notes(
    client: AsyncClient, created_application: dict[str, Any]
) -> None:
    url = f"/applications/{created_application['id']}"
    response = await client.patch(url, json={"notes": None})
    expected = {**created_application, "notes": None}
    assert response.status_code == 200
    assert response.json() == expected
    response = await client.get(url)
    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.parametrize("field", ["company", "position", "status"])
async def test_patch_rejects_explicit_null(
    client: AsyncClient, created_application: dict[str, Any], field: str
) -> None:
    url = f"/applications/{created_application['id']}"
    response = await client.patch(url, json={field: None})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", field]
    response = await client.get(url)
    assert response.status_code == 200
    assert response.json() == created_application


async def test_patch_nonexistent_application(client: AsyncClient) -> None:
    response = await client.patch("/applications/999", json={"status": "Interview"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Application not found"}


async def test_delete_application(
    client: AsyncClient, created_application: dict[str, Any]
) -> None:
    url = f"/applications/{created_application['id']}"
    response = await client.delete(url)
    assert response.status_code == 204
    assert response.content == b""
    response = await client.get(url)
    assert response.status_code == 404
    assert response.json() == {"detail": "Application not found"}


async def test_delete_nonexistent_application(client: AsyncClient) -> None:
    response = await client.delete("/applications/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Application not found"}


async def test_invalid_status_filter(client: AsyncClient) -> None:
    response = await client.get("/applications", params={"status": "Banana"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "status"]


@pytest.mark.parametrize("method", ["post", "patch"])
async def test_invalid_status(
    client: AsyncClient,
    application_data: dict[str, str | None],
    created_application: dict[str, Any],
    method: str,
) -> None:
    url = "/applications"
    if method == "patch":
        url += f"/{created_application['id']}"
    response = await client.request(
        method, url, json={**application_data, "status": "Banana"}
    )
    assert response.status_code == 422


@pytest.mark.parametrize("method", ["post", "patch"])
@pytest.mark.parametrize("field", ["company", "position"])
@pytest.mark.parametrize("value", ["", " \t\n "])
async def test_blank_required_text(
    client: AsyncClient,
    application_data: dict[str, str | None],
    created_application: dict[str, Any],
    method: str,
    field: str,
    value: str,
) -> None:
    url = "/applications"
    if method == "patch":
        url += f"/{created_application['id']}"
    response = await client.request(
        method, url, json={**application_data, field: value}
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", field]


async def test_text_trimming_preserves_notes(
    client: AsyncClient, application_data: dict[str, str | None]
) -> None:
    payload = {
        **application_data,
        "company": "  Example Company  ",
        "position": "  Developer  ",
        "notes": "  Keep this spacing.\n",
    }
    response = await client.post("/applications", json=payload)
    assert response.status_code == 201
    created = response.json()
    assert created["company"] == "Example Company"
    assert created["position"] == "Developer"
    assert created["notes"] == payload["notes"]

    response = await client.patch(
        f"/applications/{created['id']}",
        json={"company": "  New Company  ", "position": "  Engineer  "},
    )
    assert response.status_code == 200
    assert response.json()["company"] == "New Company"
    assert response.json()["position"] == "Engineer"
    assert response.json()["notes"] == payload["notes"]
