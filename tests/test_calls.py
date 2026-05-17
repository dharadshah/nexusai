from app.constants.messages import DO_NOT_CALL_RESTRICTED


def test_create_call_record(client, sample_customer, sample_campaign):
    response = client.post("/calls/", json={
        "customer_id": sample_customer["id"],
        "campaign_id": sample_campaign["id"],
        "attempt_number": 1,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["data"]["customer_id"] == sample_customer["id"]
    assert data["data"]["campaign_id"] == sample_campaign["id"]
    assert data["data"]["status"] == "pending"


def test_get_call_record(client, sample_customer, sample_campaign):
    create_response = client.post("/calls/", json={
        "customer_id": sample_customer["id"],
        "campaign_id": sample_campaign["id"],
    })
    call_id = create_response.json()["data"]["id"]

    response = client.get(f"/calls/{call_id}")
    assert response.status_code == 200
    assert response.json()["id"] == call_id
    assert "conversations" in response.json()


def test_get_call_not_found(client):
    response = client.get("/calls/nonexistent-id")
    assert response.status_code == 404


def test_list_call_records(client, sample_customer, sample_campaign):
    client.post("/calls/", json={
        "customer_id": sample_customer["id"],
        "campaign_id": sample_campaign["id"],
    })
    response = client.get("/calls/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert isinstance(data["items"], list)


def test_get_calls_by_customer(client, sample_customer, sample_campaign):
    client.post("/calls/", json={
        "customer_id": sample_customer["id"],
        "campaign_id": sample_campaign["id"],
    })
    response = client.get(f"/calls/customer/{sample_customer['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all(i["customer_id"] == sample_customer["id"] for i in data["items"])


def test_get_calls_by_campaign(client, sample_customer, sample_campaign):
    client.post("/calls/", json={
        "customer_id": sample_customer["id"],
        "campaign_id": sample_campaign["id"],
    })
    response = client.get(f"/calls/campaign/{sample_campaign['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all(i["campaign_id"] == sample_campaign["id"] for i in data["items"])


def test_do_not_call_guard(client, sample_campaign):
    dnc_customer = client.post("/customers/", json={
        "first_name": "Do",
        "last_name": "NotCall",
        "phone_number": "+919999999999",
        "status": "do_not_call",
    }).json()["data"]

    response = client.post("/calls/", json={
        "customer_id": dnc_customer["id"],
        "campaign_id": sample_campaign["id"],
    })
    assert response.status_code == 403
    assert response.json()["detail"] == DO_NOT_CALL_RESTRICTED


def test_update_call_record(client, sample_customer, sample_campaign):
    create_response = client.post("/calls/", json={
        "customer_id": sample_customer["id"],
        "campaign_id": sample_campaign["id"],
    })
    call_id = create_response.json()["data"]["id"]

    response = client.put(f"/calls/{call_id}", json={
        "status": "completed",
        "outcome": "payment_confirmed",
        "duration_seconds": 120,
    })
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["outcome"] == "payment_confirmed"
    assert data["duration_seconds"] == 120


def test_call_record_customer_not_found(client, sample_campaign):
    response = client.post("/calls/", json={
        "customer_id": "nonexistent-customer",
        "campaign_id": sample_campaign["id"],
    })
    assert response.status_code == 404


def test_call_record_campaign_not_found(client, sample_customer):
    response = client.post("/calls/", json={
        "customer_id": sample_customer["id"],
        "campaign_id": "nonexistent-campaign",
    })
    assert response.status_code == 404