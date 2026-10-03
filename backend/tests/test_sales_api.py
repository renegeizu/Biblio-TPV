"""Checkout and return business rule integration tests."""

from fastapi.testclient import TestClient
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from app.config import get_settings
from app.main import app


def create_book(client: TestClient, stock: int = 3) -> str:
    response = client.post("/api/v1/books", json={
        "isbn": "978-0-306-40615-7",
        "title": "El nombre del viento",
        "authors": "Patrick Rothfuss",
        "price": "12.50",
        "tax_rate": "0",
        "stock": stock,
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def sale_payload(book_id: str, quantity: int = 1) -> dict[str, object]:
    return {
        "items": [{"book_id": book_id, "quantity": quantity}],
        "payments": [{"method": "cash", "amount": f"{quantity * 12.5:.2f}", "cash_received": f"{quantity * 20:.2f}"}],
    }


def test_sale_is_atomic_idempotent_and_audited(admin: TestClient) -> None:
    book_id = create_book(admin)
    payload = sale_payload(book_id, 2)
    first = admin.post("/api/v1/sales", json=payload, headers={"Idempotency-Key": "checkout-001"})
    replay = admin.post("/api/v1/sales", json=payload, headers={"Idempotency-Key": "checkout-001"})

    assert first.status_code == 201, first.text
    assert replay.status_code == 201, replay.text
    assert first.json()["id"] == replay.json()["id"]
    assert first.json()["total"] == "25.00"
    assert admin.get("/api/v1/books/" + book_id).json()["stock"] == 1


def test_insufficient_stock_does_not_create_a_sale(admin: TestClient) -> None:
    book_id = create_book(admin, stock=1)
    response = admin.post("/api/v1/sales", json=sale_payload(book_id, 2), headers={"Idempotency-Key": "checkout-stock"})

    assert response.status_code == 409
    assert admin.get("/api/v1/books/" + book_id).json()["stock"] == 1
    assert admin.get("/api/v1/sales").json()["items"] == []


def test_payment_total_mismatch_does_not_decrement_stock(admin: TestClient) -> None:
    book_id = create_book(admin, stock=2)
    response = admin.post("/api/v1/sales", json={
        "items": [{"book_id": book_id, "quantity": 1}],
        "payments": [{"method": "card", "amount": "10.00"}],
    }, headers={"Idempotency-Key": "payment-mismatch"})

    assert response.status_code == 422
    assert admin.get("/api/v1/books/" + book_id).json()["stock"] == 2
    assert admin.get("/api/v1/sales").json()["items"] == []


def test_idempotency_key_cannot_be_reused_for_a_different_sale(admin: TestClient) -> None:
    book_id = create_book(admin, stock=3)
    admin.post("/api/v1/sales", json=sale_payload(book_id), headers={"Idempotency-Key": "checkout-reuse"})
    changed_request = admin.post("/api/v1/sales", json=sale_payload(book_id, 2), headers={"Idempotency-Key": "checkout-reuse"})

    assert changed_request.status_code == 409
    assert admin.get("/api/v1/books/" + book_id).json()["stock"] == 2


def test_concurrent_checkouts_cannot_sell_the_last_copy(admin: TestClient) -> None:
    book_id = create_book(admin, stock=1)
    barrier = Barrier(2)

    def checkout(key: str) -> int:
        with TestClient(app) as client:
            client.post("/api/v1/auth/login", json={"username": "admin", "password": "test-admin-password"})
            barrier.wait(timeout=5)
            response = client.post("/api/v1/sales", json=sale_payload(book_id), headers={"Idempotency-Key": key})
            return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(checkout, ["concurrent-1", "concurrent-2"]))

    assert sorted(results) == [201, 409]
    assert admin.get("/api/v1/books/" + book_id).json()["stock"] == 0
    assert admin.get("/api/v1/sales").json()["total"] == 1


def test_tax_inclusive_catalog_price_is_split_into_base_and_tax(admin: TestClient) -> None:
    book_id = admin.post("/api/v1/books", json={
        "title": "Precio con IVA",
        "price": "12.10",
        "tax_rate": "21.00",
        "stock": 1,
    }).json()["id"]
    response = admin.post("/api/v1/sales", json={
        "items": [{"book_id": book_id, "quantity": 1}],
        "payments": [{"method": "card", "amount": "12.10"}],
    }, headers={"Idempotency-Key": "tax-inclusive"})

    assert response.status_code == 201, response.text
    assert response.json()["subtotal"] == "10.00"
    assert response.json()["tax_total"] == "2.10"
    assert response.json()["total"] == "12.10"


def test_partial_return_rounding_preserves_the_original_line_total(admin: TestClient) -> None:
    settings = get_settings()
    previous_tax_mode = settings.prices_include_tax
    settings.prices_include_tax = False
    try:
        book_id = admin.post("/api/v1/books", json={"title": "Importe residual", "price": "0.01", "tax_rate": "21", "stock": 3}).json()["id"]
        sale = admin.post("/api/v1/sales", json={
            "items": [{"book_id": book_id, "quantity": 3}],
            "payments": [{"method": "card", "amount": "0.04"}],
        }, headers={"Idempotency-Key": "return-rounding"}).json()
        admin.post("/api/v1/auth/logout")
        admin.post("/api/v1/auth/login", json={"username": "supervisor", "password": "test-supervisor-password"})
        refunds = []

        for index in range(3):
            response = admin.post(f"/api/v1/sales/{sale['id']}/returns", json={
                "reason": f"Devolución parcial {index + 1}",
                "items": [{"sale_item_id": sale["items"][0]["id"], "quantity": 1, "restock": True}],
            })
            assert response.status_code == 201, response.text
            refunds.append(response.json()["refund_total"])

        assert refunds == ["0.01", "0.02", "0.01"]
    finally:
        settings.prices_include_tax = previous_tax_mode


def test_return_restocks_once_and_cannot_exceed_sold_quantity(admin: TestClient) -> None:
    book_id = create_book(admin, stock=2)
    sale = admin.post("/api/v1/sales", json=sale_payload(book_id), headers={"Idempotency-Key": "checkout-return"}).json()
    line_id = sale["items"][0]["id"]
    admin.post("/api/v1/auth/logout")
    admin.post("/api/v1/auth/login", json={"username": "supervisor", "password": "test-supervisor-password"})

    returned = admin.post(f"/api/v1/sales/{sale['id']}/returns", json={
        "reason": "Pedido por el cliente",
        "items": [{"sale_item_id": line_id, "quantity": 1, "restock": True}],
    })
    duplicate = admin.post(f"/api/v1/sales/{sale['id']}/returns", json={
        "reason": "Segundo intento",
        "items": [{"sale_item_id": line_id, "quantity": 1, "restock": True}],
    })

    assert returned.status_code == 201, returned.text
    assert returned.json()["refund_total"] == "12.50"
    assert duplicate.status_code == 409
    assert admin.get("/api/v1/books/" + book_id).json()["stock"] == 2


def test_cashier_cannot_create_books(client: TestClient) -> None:
    client.post("/api/v1/auth/login", json={"username": "cashier", "password": "test-cashier-password"})
    response = client.post("/api/v1/books", json={"title": "No autorizado", "price": "1.00", "stock": 1})
    assert response.status_code == 403


def test_book_update_rejects_null_for_required_fields(admin: TestClient) -> None:
    book_id = create_book(admin)
    response = admin.patch(f"/api/v1/books/{book_id}", json={"title": None})

    assert response.status_code == 422
    assert admin.get(f"/api/v1/books/{book_id}").json()["title"] == "El nombre del viento"


def test_admin_can_create_staff_but_cannot_remove_last_admin(admin: TestClient) -> None:
    created = admin.post("/api/v1/users", json={"username": "New.Cashier", "password": "a-long-initial-password", "role": "cashier"})
    assert created.status_code == 201, created.text
    assert created.json()["username"] == "new.cashier"
    assert "password_hash" not in created.json()

    last_admin = admin.get("/api/v1/users").json()[0]
    response = admin.patch(f"/api/v1/users/{last_admin['id']}", json={"is_active": False})
    assert response.status_code == 409


def test_mutations_reject_untrusted_origin(admin: TestClient) -> None:
    response = admin.post("/api/v1/books", headers={"Origin": "https://attacker.example"}, json={
        "title": "Petición externa", "price": "1.00", "stock": 1,
    })
    assert response.status_code == 403


def test_daily_report_subtracts_refunds_posted_that_day(admin: TestClient) -> None:
    book_id = create_book(admin, stock=3)
    sale = admin.post("/api/v1/sales", json=sale_payload(book_id, 2), headers={"Idempotency-Key": "daily-net"}).json()
    admin.post("/api/v1/auth/logout")
    admin.post("/api/v1/auth/login", json={"username": "supervisor", "password": "test-supervisor-password"})
    returned = admin.post(f"/api/v1/sales/{sale['id']}/returns", json={
        "reason": "Reembolso del día",
        "items": [{"sale_item_id": sale["items"][0]["id"], "quantity": 1, "restock": True}],
    })
    assert returned.status_code == 201
    detail = admin.get(f"/api/v1/sales/{sale['id']}").json()
    assert detail["status"] == "partially_returned"
    assert detail["items"][0]["returned_quantity"] == 1

    report = admin.get("/api/v1/reports/daily-sales")
    assert report.status_code == 200
    assert float(report.json()["sold_total"]) == 25.0
    assert float(report.json()["refunded_total"]) == 12.5
    assert float(report.json()["total"]) == 12.5


def test_public_config_does_not_require_a_session(client: TestClient) -> None:
    response = client.get("/api/v1/config/public")
    assert response.status_code == 200
    assert response.json()["currency"] == "EUR"
    assert response.json()["prices_include_tax"] is True