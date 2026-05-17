from app.constants.messages import (
    CAMPAIGN_CREATED,
    CAMPAIGN_UPDATED,
    CAMPAIGN_DELETED,
)


def test_create_campaign(client):
    response = client.post("/campaigns/", json={
        "name": "Payment Reminder Nov",
        "campaign_type": "payment_reminder",
        "company_name": "NexusAI",
        "max_retries": 3,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["message"] == CAMPAIGN_CREATED
    assert data["data"]["name"] == "Payment Reminder Nov"
    assert data["data"]["status"] == "draft"


def test_get_campaign(client, sample_campaign):
    campaign_id = sample_campaign["id"]
    response = client.get(f"/campaigns/{campaign_id}")
    assert response.status_code == 200
    assert response.json()["id"] == campaign_id


def test_get_campaign_not_found(client):
    response = client.get("/campaigns/nonexistent-id")
    assert response.status_code == 404
    assert "nonexistent-id" in response.json()["detail"]


def test_list_campaigns(client, sample_campaign):
    response = client.get("/campaigns/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert isinstance(data["items"], list)


def test_list_campaigns_filter_by_type(client, sample_campaign):
    response = client.get("/campaigns/?campaign_type=payment_reminder")
    assert response.status_code == 200
    items = response.json()["items"]
    assert all(i["campaign_type"] == "payment_reminder" for i in items)


def test_list_campaigns_filter_by_status(client, sample_campaign):
    response = client.get("/campaigns/?status=draft")
    assert response.status_code == 200
    items = response.json()["items"]
    assert all(i["status"] == "draft" for i in items)


def test_update_campaign(client, sample_campaign):
    campaign_id = sample_campaign["id"]
    response = client.put(f"/campaigns/{campaign_id}", json={
        "name": "Updated Campaign Name",
        "status": "active",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == CAMPAIGN_UPDATED
    assert data["data"]["name"] == "Updated Campaign Name"
    assert data["data"]["status"] == "active"


def test_delete_campaign(client, sample_campaign):
    campaign_id = sample_campaign["id"]
    response = client.delete(f"/campaigns/{campaign_id}")
    assert response.status_code == 200
    assert response.json()["message"] == CAMPAIGN_DELETED

    get_response = client.get(f"/campaigns/{campaign_id}")
    assert get_response.status_code == 404


def test_invalid_campaign_type(client):
    response = client.post("/campaigns/", json={
        "name": "Bad Campaign",
        "campaign_type": "invalid_type",
    })
    assert response.status_code == 422


def test_invalid_max_retries(client):
    response = client.post("/campaigns/", json={
        "name": "Bad Retries",
        "campaign_type": "payment_reminder",
        "max_retries": 99,
    })
    assert response.status_code == 422


def test_campaign_with_prompt_override(client):
    response = client.post("/campaigns/", json={
        "name": "Custom Prompt Campaign",
        "campaign_type": "customer_support",
        "system_prompt_override": "You are a custom support agent.",
    })
    assert response.status_code == 201