"""Run from project root after setup --demo: python -m tests.mysql_smoke."""
import getpass
import uuid
from app import app

client = app.test_client()
client.get("/login")


def post(url, **fields):
    with client.session_transaction() as s:
        token = s["csrf"]
    return client.post(url, data=dict(csrf=token, **fields), follow_redirects=True)


page = post("/login", username="admin", password=getpass.getpass("Admin password: "))
assert b"Stock overview" in page.data, "Admin login failed"
from db import database
with database() as cur:
    cur.execute("SELECT id FROM users WHERE username='demo.buyer'")
    buyer = cur.fetchone()
assert buyer, "Run setup --demo first"
sku = "TEST-" + uuid.uuid4().hex[:8].upper()
page = post("/product",sku=sku,name="Smoke test item",category="Test",aisle=1,bin_no=1,
            minimum=2,cost=50,price=100)
assert b"Product saved" in page.data
def move(kind, units, ticket=None, **extra):
    return post("/movement",kind=kind,sku=sku,units=str(units),
                ticket=ticket or uuid.uuid4().hex,**extra)
assert b"5 units remaining" in move("Count",5,note="Test opening balance").data
ticket = uuid.uuid4().hex
sale = move("Sale",3,ticket,partner=buyer["id"])
assert b"Low stock" in sale.data
number = sale.request.path.rsplit("/",1)[1]
assert move("Sale",3,ticket,partner=buyer["id"]).request.path == sale.request.path
assert b"Only 2 units available" in move("Sale",3,partner=buyer["id"]).data
assert b"4 units remaining" in move("Customer return",2,original=number).data
assert b"exceeds the remaining" in move("Customer return",2,original=number).data
assert sku.encode() in client.get("/export/inventory").data
print("Passed. Test SKU and receipts retained:",sku)
