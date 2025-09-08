import os
import sqlite3
import filetype
from io import BytesIO
from flask import (
    Flask, request, render_template, redirect, url_for,
    session, send_file, abort, flash, jsonify
)
import stripe
from decimal import Decimal
from datetime import datetime, timezone

app = Flask(__name__)
app.secret_key = 'your_secret_key'
PASSWORD = '2437792837'

# Stripe config
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")  # set in your env
DOMAIN = os.environ.get("APP_DOMAIN", "http://127.0.0.1:5000")  # change for prod

# DB config
DB_NAME = 'BTS.db'
TABLE_NAME = 'Expenses'

# ---------- Helpers ----------
def guess_mime_from_bytes(data: bytes) -> str:
    kind = filetype.guess(data)
    return kind.mime if kind else "application/octet-stream"

def price_text_to_cents(price_text: str) -> int:
    clean = (price_text or "").replace("$", "").strip()
    return int(Decimal(clean) * 100)

def get_cart():
    # structure: {"<itemid>_<size>": {"qty": int, "size": "Small|Medium|Large"}}
    return session.setdefault("cart", {})

def get_db():
    return sqlite3.connect(DB_NAME)

def initialize_bts_expenses():
    conn = get_db()
    curs = conn.cursor()
    curs.execute(f'''
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            cost REAL NOT NULL,
            store_name TEXT NOT NULL,
            item_description TEXT,
            purchased_by TEXT
        )
    ''')
    # Add purchased_by column if missing (safe to try each start)
    try:
        curs.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN purchased_by TEXT")
    except sqlite3.OperationalError:
        pass

    curs.execute('''
        CREATE TABLE IF NOT EXISTS Contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            message TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    return "Expenses & Contacts tables ensured."

def initialize_shop_items():
    conn = get_db()
    curs = conn.cursor()
    curs.execute('''
        CREATE TABLE IF NOT EXISTS shop_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            item_pictures BLOB,
            item_price TEXT NOT NULL,
            item_description TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    return "Shop table ensured."

def initialize_gross_income():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS gross_income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            source TEXT NOT NULL,
            amount REAL NOT NULL,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()
    return "Gross income table ensured."

def initialize_shop_item_images():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS shop_item_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            img BLOB NOT NULL,
            position INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(item_id) REFERENCES shop_items(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()
    return "Shop item images table ensured."

def initialize_orders():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            stripe_session_id TEXT UNIQUE NOT NULL,
            customer_email TEXT,
            total_cents INTEGER NOT NULL,
            status TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            item_id INTEGER,
            item_name TEXT NOT NULL,
            unit_amount_cents INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            size TEXT,  -- store size
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
        )
    """)
    # Try to add size column if table already existed
    try:
        c.execute("ALTER TABLE order_items ADD COLUMN size TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()
    return "Orders tables ensured."

# ---------- Public ----------
@app.route('/')
def Office_Hours():
    return render_template('Office_Hours.html')

@app.route('/Opening_Soon')
def Opening_Soon():
    return render_template('Opening_Soon.html')

@app.route('/Cherry_Bud_Shop')
def Cherry_Bud_Shop():
    return render_template('Shop.html')

# ---------- Expenses ----------
@app.route('/submit', methods=['POST'])
def submit():
    if not session.get('authenticated'):
        return redirect(url_for("login"))

    date = request.form['date']
    cost = request.form['cost']
    store = request.form['store_name']
    description = request.form['item_description']
    purchased_by = request.form['purchased_by']

    conn = get_db()
    curs = conn.cursor()
    curs.execute(f'''
        INSERT INTO {TABLE_NAME} (date, cost, store_name, item_description, purchased_by)
        VALUES (?, ?, ?, ?, ?)
    ''', (date, cost, store, description, purchased_by))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/delete/<int:expense_id>', methods=['POST'])
def delete_expense(expense_id):
    if not session.get('authenticated'):
        return redirect(url_for("login"))

    conn = get_db()
    curs = conn.cursor()
    curs.execute(f"DELETE FROM {TABLE_NAME} WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

# ---------- Contacts ----------
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')

        conn = get_db()
        curs = conn.cursor()
        curs.execute('''
            INSERT INTO Contacts (name, email, message)
            VALUES (?, ?, ?)
        ''', (name, email, message))
        conn.commit()
        conn.close()

        return render_template('contact.html', success=True)

    return render_template('contact.html', success=False)

@app.route("/delete_contact/<int:contact_id>", methods=["POST"])
def delete_contact(contact_id):
    if not session.get('authenticated'):
        return redirect(url_for("login"))

    conn = get_db()
    curs = conn.cursor()
    curs.execute("DELETE FROM Contacts WHERE id = ?", (contact_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

# ---------- Auth ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == PASSWORD:
            session["authenticated"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            return render_template("login.html", error="Incorrect password")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("authenticated", None)
    return redirect(url_for("login"))

# ---------- Shop (public) ----------
@app.route("/shop")
def shop():
    conn = get_db()
    conn.row_factory = sqlite3.Row
    curs = conn.cursor()
    curs.execute("""SELECT id, item_name, item_pictures, item_price, item_description
                    FROM shop_items ORDER BY id DESC""")
    rows = curs.fetchall()
    conn.close()

    shop_items = [{
        "id": r["id"],
        "item_name": r["item_name"],
        "has_image": r["item_pictures"] is not None,
        "item_price": r["item_price"],
        "item_description": r["item_description"],
    } for r in rows]

    return render_template("shop.html", shop_items=shop_items)

# ---------- Shop Admin ----------
@app.route("/add_item", methods=["GET", "POST"])
def add_item():
    if not session.get('authenticated'):
        return redirect(url_for("login"))

    if request.method == "POST":
        item_name = request.form["item_name"]
        item_price = request.form["item_price"]
        item_description = request.form["item_description"]
        files = request.files.getlist("item_pictures")  # multiple files

        conn = get_db()
        c = conn.cursor()

        # store a lightweight first image (optional): keep old column for backward compat
        first_img = files[0].read() if files and files[0].filename else None

        c.execute("""
            INSERT INTO shop_items (item_name, item_pictures, item_price, item_description)
            VALUES (?, ?, ?, ?)
        """, (item_name, first_img, item_price, item_description))
        item_id = c.lastrowid

        # insert all images (include the first one too so gallery is complete)
        for idx, f in enumerate(files):
            if not f or not f.filename:
                continue
            data = f.read() if idx != 0 else (first_img or f.read())
            c.execute("""
                INSERT INTO shop_item_images (item_id, img, position)
                VALUES (?, ?, ?)
            """, (item_id, data, idx))

        conn.commit()
        conn.close()

        return redirect(url_for("admin_dashboard"))

    return render_template("add_item.html")

@app.route("/item_image/<int:item_id>")
def item_image(item_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT item_pictures FROM shop_items WHERE id = ?", (item_id,))
    row = c.fetchone()
    conn.close()

    if not row or row[0] is None:
        abort(404)

    data = row[0]
    mime = guess_mime_from_bytes(data)
    return send_file(BytesIO(data), mimetype=mime)

@app.route("/delete_item/<int:item_id>", methods=["POST"])
def delete_item(item_id):
    if not session.get('authenticated'):
        return redirect(url_for("login"))

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM shop_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for("admin_dashboard"))

@app.route("/item/<int:item_id>")
def view_item(item_id):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, item_name, item_pictures, item_price, item_description FROM shop_items WHERE id = ?", (item_id,))
    item_row = c.fetchone()
    if not item_row:
        conn.close()
        abort(404)

    # how many images?
    c.execute("SELECT COUNT(*) FROM shop_item_images WHERE item_id = ?", (item_id,))
    image_count = c.fetchone()[0] or 0
    conn.close()

    item = {
        "id": item_row["id"],
        "item_name": item_row["item_name"],
        "has_image": (image_count > 0) or (item_row["item_pictures"] is not None),
        "item_price": item_row["item_price"],
        "item_description": item_row["item_description"],
    }
    return render_template("view_item.html", item=item, image_count=image_count)

@app.route("/item_image/<int:item_id>/<int:idx>")
def item_image_idx(item_id, idx):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT img FROM shop_item_images
        WHERE item_id = ?
        ORDER BY position ASC, id ASC
        LIMIT 1 OFFSET ?
    """, (item_id, idx))
    row = c.fetchone()
    conn.close()

    if not row:
        abort(404)
    data = row[0]
    mime = guess_mime_from_bytes(data)
    return send_file(BytesIO(data), mimetype=mime)

# ---------- Admin (single definition) ----------
@app.route('/Office_Hours')
def admin_dashboard():
    if not session.get('authenticated'):
        return redirect(url_for("login"))

    conn = get_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Expenses
    c.execute(f"""
        SELECT id, date, cost, store_name, item_description, purchased_by
        FROM {TABLE_NAME}
    """)
    expenses = c.fetchall()

    # Totals
    c.execute(f"SELECT COALESCE(SUM(cost), 0) FROM {TABLE_NAME}")
    total_expenses = c.fetchone()[0] or 0.0

    # Contacts
    c.execute("SELECT id, name, email, message FROM Contacts")
    contacts = c.fetchall()

    # Shop items
    c.execute("""SELECT id, item_name, item_pictures, item_price, item_description
                 FROM shop_items ORDER BY id DESC""")
    si_rows = c.fetchall()
    shop_items = [{
        "id": r["id"],
        "item_name": r["item_name"],
        "has_image": r["item_pictures"] is not None,
        "item_price": r["item_price"],
        "item_description": r["item_description"],
    } for r in si_rows]

    # Gross income
    c.execute("""SELECT id, date, source, amount, notes
                 FROM gross_income ORDER BY date DESC, id DESC""")
    incomes = c.fetchall()

    c.execute("SELECT COALESCE(SUM(amount), 0) FROM gross_income")
    total_income = c.fetchone()[0] or 0.0

    # Expense breakdown by person
    c.execute(f"SELECT purchased_by, SUM(cost) FROM {TABLE_NAME} GROUP BY purchased_by")
    expense_breakdown = {row[0]: row[1] for row in c.fetchall() if row[0]}

    # Orders & Order Items (now include size)
    c.execute("""
        SELECT id, created_at, customer_email, total_cents, status, stripe_session_id
        FROM orders
        ORDER BY id DESC
    """)
    orders = c.fetchall()

    c.execute("""
        SELECT order_id, item_name, unit_amount_cents, quantity, size
        FROM order_items
        ORDER BY order_id DESC, id ASC
    """)
    oi_rows = c.fetchall()
    order_items = {}
    for r in oi_rows:
        order_items.setdefault(r["order_id"], []).append({
            "item_name": r["item_name"],
            "unit_amount_cents": r["unit_amount_cents"],
            "quantity": r["quantity"],
            "size": r["size"],
        })

    conn.close()

    net = (total_income or 0.0) - (total_expenses or 0.0)

    return render_template(
        'BTSOH.html',
        expenses=expenses,
        contacts=contacts,
        shop_items=shop_items,
        incomes=incomes,
        total_income=total_income,
        total_expenses=total_expenses,
        net=net,
        expense_breakdown=expense_breakdown,
        orders=orders,
        order_items=order_items
    )

@app.route("/add_income", methods=["POST"])
def add_income():
    if not session.get('authenticated'):
        return redirect(url_for("login"))

    date = request.form.get("income_date")
    source = request.form.get("income_source")
    amount = request.form.get("income_amount")
    notes = request.form.get("income_notes")

    if not date or not source or not amount:
        return redirect(url_for("admin_dashboard"))

    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO gross_income (date, source, amount, notes)
                 VALUES (?, ?, ?, ?)""", (date, source, float(amount), notes))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))

@app.route("/delete_income/<int:income_id>", methods=["POST"])
def delete_income(income_id):
    if not session.get('authenticated'):
        return redirect(url_for("login"))

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM gross_income WHERE id = ?", (income_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))

# ---------- Cart / Checkout (with sizes) ----------
@app.route("/add_to_cart/<int:item_id>", methods=["POST"])
def add_to_cart(item_id):
    qty = max(1, int(request.form.get("qty", 1)))
    size = (request.form.get("size") or "").strip()
    if size not in ("Small", "Medium", "Large"):
        flash("Please select a size (Small, Medium, or Large).")
        return redirect(url_for("view_item", item_id=item_id))

    cart = get_cart()
    key = f"{item_id}_{size}"  # unique key per item-size combo
    if key in cart:
        cart[key]["qty"] += qty
    else:
        cart[key] = {"qty": qty, "size": size}
    session.modified = True
    return redirect(url_for("cart_view"))

@app.route("/cart", methods=["GET"])
def cart_view():
    cart = get_cart()
    if not cart:
        return render_template("cart.html", items=[], subtotal=0)

    # Gather unique item IDs to fetch
    unique_ids = sorted(set(int(k.split("_", 1)[0]) for k in cart.keys()))
    conn = get_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    q = ",".join(["?"] * len(unique_ids))
    c.execute(f"SELECT id, item_name, item_price FROM shop_items WHERE id IN ({q})", unique_ids)
    rows = c.fetchall()
    conn.close()

    # Map rows by id for quick lookup
    by_id = {r["id"]: r for r in rows}

    items = []
    subtotal_cents = 0
    for key, data in cart.items():
        item_id_str, size = key.split("_", 1)
        item_id = int(item_id_str)
        row = by_id.get(item_id)
        if not row:
            continue

        qty = data["qty"]
        unit_cents = price_text_to_cents(row["item_price"])
        line_total = unit_cents * qty
        subtotal_cents += line_total

        items.append({
            "id": item_id,
            "name": row["item_name"],
            "size": size,
            "price_text": row["item_price"],
            "unit_cents": unit_cents,
            "qty": qty,
            "line_total_cents": line_total,
        })

    return render_template("cart.html", items=items, subtotal=subtotal_cents)

@app.route("/update_cart", methods=["POST"])
def update_cart():
    cart = get_cart()
    # qty inputs now keyed by itemid_size: e.g., qty_12_Small
    for key, val in request.form.items():
        if key.startswith("qty_"):
            k = key[4:]  # everything after "qty_"
            qty = max(0, int(val or 0))
            if qty == 0:
                cart.pop(k, None)
            else:
                # keep size stored
                old = cart.get(k, {})
                size = old.get("size")
                if not size and "_" in k:
                    size = k.split("_", 1)[1]
                cart[k] = {"qty": qty, "size": size or "Medium"}
    session.modified = True
    return redirect(url_for("cart_view"))

@app.route("/clear_cart", methods=["POST"])
def clear_cart():
    session["cart"] = {}
    return redirect(url_for("cart_view"))

@app.route("/create_checkout_session", methods=["POST"])
def create_checkout_session():
    cart = session.get("cart", {})
    if not cart:
        return redirect(url_for("cart_view"))

    # Pull live prices by item_id
    unique_ids = sorted(set(int(k.split("_", 1)[0]) for k in cart.keys()))
    conn = get_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    q = ",".join(["?"] * len(unique_ids))
    c.execute(f"SELECT id, item_name, item_price FROM shop_items WHERE id IN ({q})", unique_ids)
    rows = c.fetchall()
    conn.close()
    by_id = {r["id"]: r for r in rows}

    line_items = []
    for key, data in cart.items():
        item_id = int(key.split("_", 1)[0])
        size = key.split("_", 1)[1]
        row = by_id.get(item_id)
        if not row:
            continue
        qty = data["qty"]
        amount_cents = price_text_to_cents(row["item_price"])
        if amount_cents <= 0 or qty <= 0:
            continue

        line_items.append({
            "quantity": qty,
            "price_data": {
                "currency": "usd",
                "unit_amount": amount_cents,
                "product_data": {
                    "name": f"{row['item_name']} ({size})",
                    "metadata": {"item_id": str(item_id), "size": size}
                },
            },
        })

    if not line_items:
        return redirect(url_for("cart_view"))

    session_stripe = stripe.checkout.Session.create(
        mode="payment",
        line_items=line_items,
        success_url=f"{DOMAIN}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{DOMAIN}/cart",
        automatic_tax={"enabled": False},
        shipping_address_collection={"allowed_countries": ["US", "CA"]},
        client_reference_id=session.get("_id")
    )

    return redirect(session_stripe.url, code=303)

@app.route("/checkout/success")
def checkout_success():
    session.pop("cart", None)
    return render_template("success.html")

# ---------- Stripe Webhook (idempotent, with size) ----------
@app.route("/stripe_webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")  # set this in your env

    # Verify signature
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception as e:
        return str(e), 400

    if event["type"] == "checkout.session.completed":
        session_obj = event["data"]["object"]
        session_id = session_obj["id"]

        # Retrieve full session with line items & product metadata
        checkout = stripe.checkout.Session.retrieve(
            session_id,
            expand=["line_items.data.price.product", "customer_details"]
        )

        customer_email = (checkout.customer_details or {}).get("email")
        total_amount_cents = int(checkout.amount_total or 0)

        conn = get_db()
        c = conn.cursor()

        # Idempotent order insert
        c.execute("""
            INSERT OR IGNORE INTO orders
                (created_at, stripe_session_id, customer_email, total_cents, status)
            VALUES (?, ?, ?, ?, ?)
        """, (datetime.now(timezone.utc).isoformat(timespec="seconds"),
              session_id, customer_email, total_amount_cents, "paid"))

        # Get order id (existing or newly inserted)
        c.execute("SELECT id FROM orders WHERE stripe_session_id = ?", (session_id,))
        row = c.fetchone()
        order_id = row[0]

        # Only insert line items once
        c.execute("SELECT COUNT(1) FROM order_items WHERE order_id = ?", (order_id,))
        already_has_items = (c.fetchone()[0] or 0) > 0

        if not already_has_items:
            for li in checkout.line_items.data:
                qty = int(li.quantity or 0)
                unit_cents = int((li.price.unit_amount or 0))

                # Pull our metadata (item_id + size)
                item_id = None
                size = None
                try:
                    size = li.price.product.metadata.get("size")
                except Exception:
                    size = None
                try:
                    item_id = int(li.price.product.metadata.get("item_id"))
                except Exception:
                    item_id = None

                item_name = li.description or (
                    getattr(li.price, "product", None).name
                    if getattr(li.price, "product", None) else "Item"
                )

                c.execute("""
                    INSERT INTO order_items (order_id, item_id, item_name, unit_amount_cents, quantity, size)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (order_id, item_id, item_name, unit_cents, qty, size))

        conn.commit()
        conn.close()

    return "", 200

# ---------- Entrypoint ----------
if __name__ == "__main__":
    print(initialize_shop_item_images())
    print(initialize_bts_expenses())
    print(initialize_shop_items())
    print(initialize_gross_income())
    print(initialize_orders())
    print("Static folder:", os.path.abspath(app.static_folder))
    app.run(debug=True)
