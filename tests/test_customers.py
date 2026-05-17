from app.constants.messages import (
    CUSTOMER_CREATED,
    CUSTOMER_UPDATED,
    CUSTOMER_DELETED,
)


def test_create_customer(client):
    response = client.post("/customers/", json={
        "first_name": "Priya",
        "last_name": "Patel",
        "phone_number": "+919876543211",
        "email": "priya@example.com",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["message"] == CUSTOMER_CREATED
    assert data["data"]["phone_number"] == "+919876543211"
    assert data["data"]["full_name"] == "Priya Patel"


def test_get_customer(client, sample_customer):
    customer_id = sample_customer["id"]
    response = client.get(f"/customers/{customer_id}")
    assert response.status_code == 200
    assert response.json()["id"] == customer_id


def test_get_customer_not_found(client):
    response = client.get("/customers/nonexistent-id")
    assert response.status_code == 404
    assert "nonexistent-id" in response.json()["detail"]


def test_list_customers(client, sample_customer):
    response = client.get("/customers/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert data["page"] == 1
    assert isinstance(data["items"], list)


def test_list_customers_filter_by_status(client, sample_customer):
    response = client.get("/customers/?status=active")
    assert response.status_code == 200
    items = response.json()["items"]
    assert all(i["status"] == "active" for i in items)


def test_update_customer(client, sample_customer):
    customer_id = sample_customer["id"]
    response = client.put(f"/customers/{customer_id}", json={
        "first_name": "Dhara Updated",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == CUSTOMER_UPDATED
    assert data["data"]["first_name"] == "Dhara Updated"


def test_delete_customer(client, sample_customer):
    customer_id = sample_customer["id"]
    response = client.delete(f"/customers/{customer_id}")
    assert response.status_code == 200
    assert response.json()["message"] == CUSTOMER_DELETED

    get_response = client.get(f"/customers/{customer_id}")
    assert get_response.status_code == 404


def test_duplicate_phone_number(client, sample_customer):
    response = client.post("/customers/", json={
        "first_name": "Another",
        "last_name": "Person",
        "phone_number": "+919876543210",
    })
    assert response.status_code == 409


def test_invalid_phone_number(client):
    response = client.post("/customers/", json={
        "first_name": "Test",
        "last_name": "User",
        "phone_number": "not-a-phone",
    })
    assert response.status_code == 422


def test_create_customer_do_not_call_status(client):
    response = client.post("/customers/", json={
        "first_name": "No",
        "last_name": "Call",
        "phone_number": "+919876543299",
        "status": "do_not_call",
    })
    assert response.status_code == 201
    assert response.json()["data"]["status"] == "do_not_call"