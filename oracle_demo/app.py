from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import csv, os

app = Flask(__name__)
app.secret_key = "change_this_to_a_random_secret_for_prod"

# Load users (username/password)
#USERS_CSV = r"C:\Users\Harshita Paliwal\Documents\oracle_demo\users1.csv"
USERS_CSV = os.getenv("USERS_CSV", "./users1.csv")
#PROFILES_CSV = os.getenv("PROFILES_CSV", "./profiles1.csv")
users = {}
if os.path.exists(USERS_CSV):
    with open(USERS_CSV, newline='') as f:
        r = csv.DictReader(f)
        for row in r:
            users[row['username']] = row['password']

# NEW: user profiles (shipping/contact), stored separately to avoid changing your users1.csv
PROFILES_CSV = r"C:\Users\Harshita Paliwal\Documents\oracle_demo\profiles1.csv"
profiles = {}  # username -> {username, full_name, address1, address2, city, state, postal, phone}

def _ensure_csv_with_header(path, fieldnames):
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()

# Load profiles
if os.path.exists(PROFILES_CSV):
    with open(PROFILES_CSV, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            profiles[row["username"]] = row

# Products
PRODUCTS = [
    {"id": 1, "name": "Siebel Upgrade", "image": "https://www.siebelhub.com/main/wp-content/uploads/2019/02/update-1672350_960_720.png", "price": 199},
    {"id": 2, "name": "OCI Migration", "image": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTi-Tl0uf8P5TjLdBCfpgAdqtqt_sRLDm6GcA&s", "price": 499},
    {"id": 3, "name": "Implementing AI", "image": "data:image/jpeg;base64,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", "price": 599},
    {"id": 4, "name": "Siebel Test Automation", "image": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTK_Nn-cT2GcCbFWq_pTdMsBzj7QAUEsReJkA&s", "price": 199},
    {"id": 5, "name": "Siebel Code Review", "image": "data:image/jpeg;base64,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", "price": 999},
    {"id": 6, "name": "24*7 Support", "image": "data:image/png;base64,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", "price": 1299},
]

def get_product(pid):
    return next((p for p in PRODUCTS if p["id"] == pid), None)

# --------- Existing routes ---------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","").strip()
        if username in users and users[username] == password:
            session['username'] = username
            session['cart'] = []
            flash(f"Welcome, {username}!", "success")
            return redirect(url_for('products'))
        else:
            flash("Invalid username or password", "danger")
    return render_template("login.html")

@app.route("/products")
def products():
    if 'username' not in session:
        return redirect(url_for('login'))
    q = request.args.get("q","").strip().lower()
    filtered = [p for p in PRODUCTS if q in p['name'].lower()] if q else PRODUCTS
    return render_template("products.html", products=filtered, query=q)

@app.route("/add-to-cart/<int:pid>", methods=["POST"])
def add_to_cart(pid):
    if 'username' not in session:
        return jsonify({"ok": False, "error": "not logged in"}), 401
    p = get_product(pid)
    if not p:
        flash("Product not found", "danger")
        return redirect(request.referrer or url_for('products'))
    cart = session.get('cart', [])
    cart.append(pid)
    session['cart'] = cart
    flash(f"Product added: {p['name']}", "success")
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"ok": True, "msg": f"Product added: {p['name']}"})
    return redirect(request.referrer or url_for('products'))

@app.route("/cart")
def cart():
    if 'username' not in session:
        return redirect(url_for('login'))
    cart_ids = session.get('cart', [])
    items = [get_product(pid) for pid in cart_ids if get_product(pid)]
    total = sum(p['price'] for p in items)
    return render_template("cart.html", items=items, total=total)

@app.route("/checkout", methods=["POST"])
def checkout():
    if 'username' not in session:
        return redirect(url_for('login'))
    session['cart'] = []
    flash("Payment done. Order confirmed! (simulated)", "success")
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"ok": True, "msg": "Payment done"})
    return redirect(url_for('products'))

@app.route("/logout")
def logout():
    session.clear()
    flash("You are logged out.", "info")
    return redirect(url_for('login'))

@app.route("/_health")
def health():
    return jsonify({"ok": True, "user_count": len(users), "product_count": len(PRODUCTS)})

# --------- Order flow (added earlier) ---------

@app.route('/summary', methods=['GET'])
def summary():
    if 'username' not in session:
        return redirect(url_for('login'))
    cart_ids = session.get('cart', [])
    items = [get_product(pid) for pid in cart_ids if get_product(pid)]
    total = sum(p['price'] for p in items)
    return render_template('summary.html', items=items, total=total)

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if 'username' not in session:
        return redirect(url_for('login'))
    # NEW: require profile before payment
    uname = session['username']
    if uname not in profiles:
        flash("Please complete your account details before payment.", "info")
        next_url = url_for('payment')
        return redirect(url_for('account', next=next_url))

    cart_ids = session.get('cart', [])
    items = [get_product(pid) for pid in cart_ids if get_product(pid)]
    total = sum(p['price'] for p in items)
    return render_template('payment.html', total=total)

@app.route('/pay-now', methods=['POST'])
def pay_now():
    if 'username' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('order_confirmation'))

@app.route('/order-confirmation', methods=['GET'])
def order_confirmation():
    if 'username' not in session:
        return redirect(url_for('login'))
    session['cart'] = []
    return render_template('confirmation.html')

# --------- NEW: Registration & Account Details ---------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","").strip()
        confirm  = request.form.get("confirm","").strip()

        if not username or not password:
            flash("Username and password are required.", "danger")
            return render_template("register.html")

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("register.html", username=username)

        if username in users:
            flash("Username already exists. Please choose another.", "warning")
            return render_template("register.html", username=username)

        # append to CSV (create header if needed)
        _ensure_csv_with_header(USERS_CSV, ["username", "password"])
        with open(USERS_CSV, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["username", "password"])
            w.writerow({"username": username, "password": password})
        users[username] = password

        session["username"] = username
        session.setdefault("cart", [])
        flash("Account created and logged in!", "success")
        return redirect(url_for("products"))
    return render_template("register.html")

@app.route("/account", methods=["GET", "POST"])
def account():
    if "username" not in session:
        return redirect(url_for("login"))
    uname = session["username"]

    if request.method == "POST":
        data = {
            "username": uname,
            "full_name": request.form.get("full_name","").strip(),
            "address1": request.form.get("address1","").strip(),
            "address2": request.form.get("address2","").strip(),
            "city":     request.form.get("city","").strip(),
            "state":    request.form.get("state","").strip(),
            "postal":   request.form.get("postal","").strip(),
            "phone":    request.form.get("phone","").strip(),
        }
        # persist to CSV (upsert)
        _ensure_csv_with_header(PROFILES_CSV, ["username","full_name","address1","address2","city","state","postal","phone"])

        # Load all, replace or append, then write back
        all_rows = []
        if os.path.exists(PROFILES_CSV):
            with open(PROFILES_CSV, newline="") as f:
                r = csv.DictReader(f)
                for row in r:
                    if row["username"] != uname:
                        all_rows.append(row)
        all_rows.append(data)
        with open(PROFILES_CSV, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["username","full_name","address1","address2","city","state","postal","phone"])
            w.writeheader()
            w.writerows(all_rows)

        profiles[uname] = data
        flash("Account details saved.", "success")

        next_url = request.args.get("next") or url_for("summary")
        return redirect(next_url)

    # GET
    existing = profiles.get(uname, {"full_name":"","address1":"","address2":"","city":"","state":"","postal":"","phone":""})
    next_url = request.args.get("next","")
    return render_template("account.html", profile=existing, next_url=next_url)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
