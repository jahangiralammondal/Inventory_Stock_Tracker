import csv
import io
import os
import re
import secrets
import uuid
from decimal import Decimal
from pathlib import Path

import click
from dotenv import load_dotenv
from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   Response, session, url_for)
from mysql.connector import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash
from db import database
from inventory import Warehouse, bill, closing_quantity, integer, money, status

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
app = Flask(__name__)
if os.environ.get("SESSION_SECRET"):
    app.secret_key = os.environ["SESSION_SECRET"]
else:
    instance = Path(app.instance_path)
    instance.mkdir(exist_ok=True)
    key = instance / "session.key"
    if not key.exists():
        try:
            with key.open("xb") as f:
                f.write(secrets.token_bytes(32))
        except FileExistsError:
            pass
    app.secret_key = key.read_bytes()
if os.environ.get("RAILWAY_ENVIRONMENT_ID"):
    if not os.environ.get("SESSION_SECRET"):
        raise RuntimeError("Set SESSION_SECRET before starting the Railway service.")
    app.config["SESSION_COOKIE_SECURE"] = True
app.config.update(SESSION_COOKIE_SAMESITE="Lax", MAX_CONTENT_LENGTH=65536)
app.jinja_env.globals.update(status=status, bill=bill)
INTERNAL = ("Admin", "Staff")


def field(name, limit):
    value = request.form.get(name, "").strip()
    if not value or len(value) > limit:
        raise ValueError(f"Enter a valid {name} (up to {limit} characters).")
    return value


def require(*roles):
    if not g.user or g.user["role"] not in roles:
        abort(403)


def warehouse(cur):
    cur.execute("SELECT * FROM products ORDER BY aisle, bin_no, sku")
    return Warehouse(cur.fetchall())


@app.before_request
def identity():
    if request.endpoint == "static":
        return
    session.setdefault("csrf", secrets.token_hex(24))
    if request.method == "POST" and request.form.get("csrf") != session["csrf"]:
        abort(400)
    g.user = None
    if session.get("uid"):
        with database() as cur:
            cur.execute("SELECT id,name,role,username FROM users WHERE id=%s", (session["uid"],))
            g.user = cur.fetchone()
    if not g.user and request.endpoint != "login":
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        with database() as cur:
            cur.execute("SELECT * FROM users WHERE username=%s", (request.form.get("username", "").strip(),))
            user = cur.fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["uid"] = user["id"]
            return redirect(url_for("home"))
        flash("Username or password is incorrect.", "error")
    return render_template("login.html", title="Sign in")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
def home():
    if g.user["role"] not in INTERNAL:
        return redirect(url_for("history"))
    with database() as cur:
        stock = warehouse(cur)
    rows = list(stock.by_code.values())
    low = [p for p in rows if p["qty"] <= p["minimum"]]
    return render_template("home.html", title="Stock overview", rows=rows, low=low,
                           units=sum(p["qty"] for p in rows),
                           value=sum(p["qty"] * p["cost"] for p in rows))


@app.get("/inventory")
def inventory():
    require(*INTERNAL)
    with database() as cur:
        stock = warehouse(cur)
    q = request.args.get("q", "").strip()
    exact = stock.lookup(q)
    rows = [exact] if exact else [p for p in stock.by_code.values() if q.casefold() in
        " ".join((p["sku"], p["name"], p["category"])).casefold()]
    if request.args.get("low"):
        rows = [p for p in rows if p["qty"] <= p["minimum"]]
    return render_template("inventory.html", title="Inventory", rows=rows, q=q)


@app.get("/warehouse")
def locations():
    require(*INTERNAL)
    with database() as cur:
        stock = warehouse(cur)
    return render_template("warehouse.html", title="Warehouse map", aisles=stock.aisles)


@app.route("/product", defaults={"sku": None}, methods=["GET", "POST"])
@app.route("/product/<sku>", methods=["GET", "POST"])
def product(sku):
    require(*INTERNAL)
    with database() as cur:
        item = warehouse(cur).lookup(sku) if sku else None
        if sku and not item:
            abort(404)
        if request.method == "POST":
            try:
                code = sku or field("sku", 40).upper()
                if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,39}", code):
                    raise ValueError("Use letters, digits, underscores or hyphens for the SKU.")
                data = (field("name",100), field("category",80), integer(field("aisle",3),"Aisle",1,100),
                        integer(field("bin_no",3),"Bin",1,100), integer(field("minimum",7),"Threshold"),
                        money(field("cost",12)), money(field("price",12)), code)
                if sku:
                    cur.execute("UPDATE products SET name=%s,category=%s,aisle=%s,bin_no=%s,minimum=%s,cost=%s,price=%s WHERE sku=%s", data)
                else:
                    cur.execute("INSERT INTO products(name,category,aisle,bin_no,minimum,cost,price,sku) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", data)
                flash("Product saved.")
                return redirect(url_for("inventory",q=code))
            except (ValueError, IntegrityError) as exc:
                flash(str(exc) if isinstance(exc, ValueError) else "This SKU already exists.", "error")
    return render_template("product.html", title="Edit product" if sku else "Add product", item=request.form or item or {})


@app.route("/accounts", methods=["GET", "POST"])
def accounts():
    require(*INTERNAL)
    roles = ["Buyer","Supplier"] + (["Staff","Admin"] if g.user["role"] == "Admin" else [])
    with database() as cur:
        if request.method == "POST":
            try:
                role = field("role",10)
                if role not in roles:
                    abort(403)
                password = request.form.get("password","")
                if not 8 <= len(password) <= 128:
                    raise ValueError("Use a password of 8–128 characters.")
                cur.execute("INSERT INTO users(name,username,role,password_hash) VALUES(%s,%s,%s,%s)",
                    (field("name",100),field("username",80),role,generate_password_hash(password)))
                flash("Account created.")
                return redirect(url_for("accounts"))
            except (ValueError, IntegrityError) as exc:
                flash(str(exc) if isinstance(exc,ValueError) else "Username already exists.", "error")
        cur.execute("SELECT name,username,role FROM users ORDER BY name")
        users = cur.fetchall()
    return render_template("accounts.html", title="Accounts", roles=roles, users=users)


def record(cur):
    form = request.form
    ticket = uuid.UUID(form.get("ticket","")).hex
    sku = field("sku",40).upper()
    cur.execute("SELECT * FROM products WHERE sku=%s FOR UPDATE",(sku,))
    p = cur.fetchone()
    if not p:
        raise ValueError("Choose an existing product.")
    cur.execute("SELECT id,actor FROM movements WHERE ticket=%s FOR UPDATE",(ticket,))
    existing = cur.fetchone()
    if existing:
        if existing["actor"] != g.user["id"]:
            abort(403)
        return existing["id"]
    kind = field("kind",30)
    units = integer(form.get("units"),"Units")
    balance = closing_quantity(p["qty"],kind,units)
    note = form.get("note","").strip()
    if len(note) > 240:
        raise ValueError("Notes must be at most 240 characters.")
    partner = original = None
    discount = tax = price = Decimal("0")
    if kind == "Count":
        require("Admin")
        if not note:
            raise ValueError("Enter a reason for the count correction.")
    elif kind in ("Sale","Purchase"):
        partner = integer(form.get("partner"),"Account",1)
        role = "Buyer" if kind == "Sale" else "Supplier"
        cur.execute("SELECT id FROM users WHERE id=%s AND role=%s",(partner,role))
        if not cur.fetchone():
            raise ValueError(f"Select a {role.lower()} account.")
        price = money(form.get("price") or p["price" if kind=="Sale" else "cost"])
        discount = money(form.get("discount") or 0,100)
        tax = money(form.get("tax") or 0,100)
    else:
        original = integer(form.get("original"),"Original receipt",1,2**63-1)
        expected = "Sale" if kind=="Customer return" else "Purchase"
        cur.execute("SELECT * FROM movements WHERE id=%s AND kind=%s AND sku=%s FOR UPDATE",
                    (original,expected,sku))
        source = cur.fetchone()
        if not source:
            raise ValueError("The original receipt must match the product and transaction type.")
        cur.execute("SELECT COALESCE(SUM(units),0) AS used FROM movements WHERE original_id=%s",(original,))
        if cur.fetchone()["used"] + units > source["units"]:
            raise ValueError("Return quantity exceeds the remaining units on that receipt.")
        partner,price,discount,tax = (source[k] for k in ("partner","price","discount","tax"))
    delta = balance - p["qty"]
    cur.execute("UPDATE products SET qty=%s WHERE sku=%s",(balance,sku))
    cur.execute("""INSERT INTO movements(ticket,sku,kind,units,balance,delta,actor,partner,original_id,note,price,discount,tax)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (ticket,sku,kind,units,balance,delta,g.user["id"],partner,original,note,price,discount,tax))
    flash(f"{sku} · {balance} units remaining. {status(balance,p['minimum'])}.")
    return cur.lastrowid


@app.route("/movement", methods=["GET","POST"])
def movement():
    require(*INTERNAL)
    if request.method == "POST":
        try:
            with database() as cur:
                number = record(cur)
            return redirect(url_for("receipt",number=number))
        except ValueError as exc:
            flash(str(exc),"error")
    with database() as cur:
        stock = warehouse(cur)
        cur.execute("SELECT id,name,role FROM users WHERE role IN ('Buyer','Supplier') ORDER BY name")
        partners = cur.fetchall()
    return render_template("movement.html",title="Record stock movement",rows=stock.by_code.values(),
                           partners=partners,ticket=uuid.uuid4().hex)


def ledger(cur, number=None):
    sql = """SELECT m.*,p.name, a.name AS operator,b.name AS counterparty FROM movements m
             JOIN products p ON p.sku=m.sku JOIN users a ON a.id=m.actor LEFT JOIN users b ON b.id=m.partner"""
    filters, params = [], []
    if g.user["role"] not in INTERNAL:
        filters.append("m.partner=%s")
        params.append(g.user["id"])
    if number is not None:
        filters.append("m.id=%s")
        params.append(number)
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    cur.execute(sql + " ORDER BY m.id DESC",tuple(params))
    return cur.fetchall()


@app.get("/history")
def history():
    with database() as cur:
        rows = ledger(cur)
    return render_template("history.html",title="Transaction history",rows=rows)


@app.get("/receipt/<int:number>")
def receipt(number):
    with database() as cur:
        rows = ledger(cur,number)
    if not rows:
        abort(404)
    return render_template("receipt.html",title=f"Receipt #{number}",m=rows[0])


@app.get("/export/<kind>")
def export(kind):
    with database() as cur:
        if kind=="inventory":
            require(*INTERNAL)
            rows = warehouse(cur).by_code.values()
            keys = "sku name category aisle bin_no qty minimum cost price".split()
        elif kind=="history":
            rows = ledger(cur)
            keys = "id created sku kind units price discount tax counterparty".split()
        else:
            abort(404)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(keys)
    for row in rows:
        values = [row[k] for k in keys]
        writer.writerow(["'"+v if isinstance(v,str) and v.lstrip().startswith(("=","+","-","@")) else v for v in values])
    return Response("\ufeff"+buf.getvalue(),mimetype="text/csv",headers={
        "Content-Disposition":f'attachment; filename="{kind}.csv"'})


@app.cli.command("setup")
@click.option("--demo",is_flag=True,help="Add electronics products and sample buyer/supplier accounts.")
def setup(demo):
    """Create tables and the first administrator. Safe to run again."""
    with database() as cur:
        for statement in (ROOT/"schema.sql").read_text().split(";"):
            if statement.strip():
                cur.execute(statement)
        cur.execute("SELECT id FROM users WHERE role='Admin' LIMIT 1")
        if not cur.fetchone():
            password = os.environ.get("INITIAL_ADMIN_PASSWORD") or click.prompt("Choose admin password (8–128 characters)",hide_input=True,confirmation_prompt=True)
            if not 8 <= len(password) <= 128:
                raise click.ClickException("Use 8–128 characters.")
            cur.execute("INSERT INTO users(username,name,role,password_hash) VALUES('admin','Shop administrator','Admin',%s)",
                        (generate_password_hash(password),))
        if demo:
            with (ROOT/"demo.csv").open() as f:
                for p in csv.DictReader(f):
                    cur.execute("SELECT sku FROM products WHERE sku=%s",(p["sku"],))
                    if cur.fetchone():
                        continue
                    cur.execute("INSERT INTO products(sku,name,category,aisle,bin_no,qty,minimum,cost,price) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",tuple(p.values()))
                    if int(p["qty"]):
                        cur.execute("""INSERT INTO movements(ticket,sku,kind,units,balance,delta,actor,note,price,discount,tax)
                            SELECT %s,%s,'Count',%s,%s,%s,id,'Opening stock',0,0,0 FROM users WHERE role='Admin' ORDER BY id LIMIT 1""",
                            (uuid.uuid4().hex,p["sku"],p["qty"],p["qty"],p["qty"]))
            for username,name,role in [("demo.buyer","Campus IT Lab","Buyer"),("demo.supplier","Eastern Components","Supplier")]:
                cur.execute("SELECT id FROM users WHERE username=%s",(username,))
                if not cur.fetchone():
                    password = secrets.token_urlsafe(12)
                    cur.execute("INSERT INTO users(username,name,role,password_hash) VALUES(%s,%s,%s,%s)",
                                (username,name,role,generate_password_hash(password)))
                    if not os.environ.get("RAILWAY_ENVIRONMENT_ID"):
                        click.echo(f"Demo login: {username} / {password}")
    click.echo("Setup complete. Sign in with your administrator account.")
