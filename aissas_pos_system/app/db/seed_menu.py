"""
app/db/seed_menu.py
Official Aissa's Kitchenette menu seeder — hierarchical structure.

Category hierarchy: Main Category → Subcategory → Products

seed_menu_if_empty(db) — seeds only when products table is empty.
seed_menu(db)          — DESTRUCTIVE: clears then reseeds.
"""
from __future__ import annotations

# ── MENU STRUCTURE ────────────────────────────────────────────────────────────
# Format: (main_category, subcategory, product_name, price, image_path)
# image_path is relative to product_images/ folder (or "" if none)

_MENU: list[tuple[str, str, str, int, str]] = [

    # ── RICE MEALS ────────────────────────────────────────────────────────────
    # Silog Meals
    ("Rice Meals", "Silog Meals", "Beefsilog",          95,  "product_images/beefsilog.png"),
    ("Rice Meals", "Silog Meals", "Liempo Silog",        120, "product_images/liemposilog.png"),
    ("Rice Meals", "Silog Meals", "Chicken Steak Silog", 110, "product_images/chickensteaksilog.png"),
    ("Rice Meals", "Silog Meals", "Pork Chop Silog",     110, "product_images/porckchopsilog.png"),

    # Filipino Rice Meals
    ("Rice Meals", "Filipino Rice Meals", "Pastil",              75,  "product_images/pastil.webp"),
    ("Rice Meals", "Filipino Rice Meals", "Sweet n Chili Pastil", 85, "product_images/sweetnchilipastil.png"),
    ("Rice Meals", "Filipino Rice Meals", "Biryani",             85,  "product_images/biryani.png"),
    ("Rice Meals", "Filipino Rice Meals", "Fish Fillet Rice Meal", 95, "product_images/fishfillet.png"),
    ("Rice Meals", "Filipino Rice Meals", "Burger Steak",        115, "product_images/burgersteak.png"),

    # Teriyaki Meals
    ("Rice Meals", "Teriyaki Meals", "Chicken Teriyaki Poppers", 95, "product_images/chickenteriyakipoppers.png"),
    ("Rice Meals", "Teriyaki Meals", "Beeftapa Teriyaki",        95, "product_images/beeftapateriyaki.png"),
    ("Rice Meals", "Teriyaki Meals", "Pork Tapa Teriyaki",       95, "product_images/porktapateriyaki.png"),

    # Stir Fry & Specialty Meals
    ("Rice Meals", "Stir Fry & Specialty Meals", "Beef Stir Fry",             95, "product_images/beefstirfry.png"),
    ("Rice Meals", "Stir Fry & Specialty Meals", "Beef Hickory Stir Fry",     95, "product_images/beefhickorystirfry.png"),
    ("Rice Meals", "Stir Fry & Specialty Meals", "Pork Stir Fry Hickory",     95, "product_images/porkstirfryhickory.png"),
    ("Rice Meals", "Stir Fry & Specialty Meals", "Pork Garlic Mushroom",      95, "product_images/porkgarlicmushroom.png"),
    ("Rice Meals", "Stir Fry & Specialty Meals", "Korean Gojuchang Chicken",  95, "product_images/koreangojuchangchicken.png"),
    ("Rice Meals", "Stir Fry & Specialty Meals", "Cheesy Beef Caldereta",     95, "product_images/cheesybeefcaldereta.png"),

    # ── SISIG SPECIALS ────────────────────────────────────────────────────────
    ("Sisig Specials", "Pork Sisig",    "Classic Pork Sisig",   90, "product_images/porksisig.png"),
    ("Sisig Specials", "Chicken Sisig", "Classic Chicken Sisig", 90, "product_images/chickensisig.png"),
    ("Sisig Specials", "Bangus Sisig",  "Classic Bangus Sisig",  95, "product_images/bangussisig.png"),

    # ── PASTA ────────────────────────────────────────────────────────────────
    ("Pasta", "Cream-Based Pasta", "Cheesy Carbonara", 90, "product_images/cheesecarbonara.png"),
    ("Pasta", "Cream-Based Pasta", "Mac n Cheese",     95, "product_images/macncheese.png"),

    ("Pasta", "Tomato-Based Pasta", "Spaghetti Bolognese",                   95,  "product_images/beefbolognese.webp"),
    ("Pasta", "Tomato-Based Pasta", "Spaghetti Bolognese w/ Bechamel Sauce", 105, "product_images/SpaghettiBolognesewBechamelsauce.png"),

    ("Pasta", "Pesto Pasta", "Chicken Pesto", 95, "product_images/chickenpesto.png"),

    # ── SANDWICHES, WRAPS & QUESADILLAS ──────────────────────────────────────
    ("Sandwiches, Wraps & Quesadillas", "Sandwiches", "Ham and Egg Sandwich",        75, "product_images/hamnegg.png"),
    ("Sandwiches, Wraps & Quesadillas", "Sandwiches", "Korean Spam Sandwich",        95, "product_images/koreanspamsandwich.png"),
    ("Sandwiches, Wraps & Quesadillas", "Sandwiches", "Beef Steak Hickory Sandwich", 95, "product_images/beefsteakhickorysandwich.png"),

    ("Sandwiches, Wraps & Quesadillas", "Quesadillas", "Beef Quesadilla",            80, "product_images/beefquesadilla.png"),
    ("Sandwiches, Wraps & Quesadillas", "Quesadillas", "Chicken Quesadilla",         80, "product_images/chickensisigquesadilla.png"),
    ("Sandwiches, Wraps & Quesadillas", "Quesadillas", "Mexican Chicken Quesadilla", 85, "product_images/mexicanchickenquesadilla.png"),
    ("Sandwiches, Wraps & Quesadillas", "Quesadillas", "Chicken Sisig Quesadilla",   80, "product_images/chickensisigquesadilla.png"),

    ("Sandwiches, Wraps & Quesadillas", "Wraps", "Beef Shawarma", 95, "product_images/beefshawarma.png"),

    # ── FRIES & SNACKS ────────────────────────────────────────────────────────
    ("Fries & Snacks", "Fries", "Regular Fries",    50, "product_images/regularfries.png"),
    ("Fries & Snacks", "Fries", "Big Fries",         70, "product_images/bigfries.png"),
    ("Fries & Snacks", "Fries", "Cheesy Beef Fries", 90, "product_images/cheesybeeffries.png"),

    # ── COFFEE & ESPRESSO ─────────────────────────────────────────────────────
    # Hot Coffee
    ("Coffee & Espresso", "Hot Coffee", "Latte",         60, "product_images/latte.png"),
    ("Coffee & Espresso", "Hot Coffee", "Spanish Latte",  70, "product_images/SpanishLatte.png"),
    ("Coffee & Espresso", "Hot Coffee", "Mochaccino",     70, "product_images/mochaccino.png"),
    ("Coffee & Espresso", "Hot Coffee", "Matcha Latte",   75, "product_images/matchalatte.png"),

    # Iced Coffee
    ("Coffee & Espresso", "Iced Coffee", "Iced Latte",          65, "product_images/icedlatte.webp"),
    ("Coffee & Espresso", "Iced Coffee", "Iced Mochaccino",      80, "product_images/icedmochaccino.png"),
    ("Coffee & Espresso", "Iced Coffee", "Iced Salted Caramel",  80, "product_images/icedsaltedcaramel.png"),
    ("Coffee & Espresso", "Iced Coffee", "Matcha Iced Coffee",   90, "product_images/coffeematchaiced.png"),
    ("Coffee & Espresso", "Iced Coffee", "Matcha Latte Iced",    85, "product_images/matchalatteiced.webp"),

    # Chocolate Drinks
    ("Coffee & Espresso", "Chocolate Drinks", "Hot Choco",  65, "product_images/hotchoco.png"),
    ("Coffee & Espresso", "Chocolate Drinks", "Iced Choco", 80, "product_images/icedchoco.png"),

    # ── MILK TEA ─────────────────────────────────────────────────────────────
    # Classic Milk Tea
    ("Milk Tea", "Classic Milk Tea", "Wintermelon Milk Tea", 55, "product_images/wintermelon.png"),
    ("Milk Tea", "Classic Milk Tea", "Okinawa Milk Tea",     55, "product_images/okinawamtea.png"),
    ("Milk Tea", "Classic Milk Tea", "Taro Milk Tea",        55, "product_images/taromilktea.png"),

    # Flavored Milk Tea
    ("Milk Tea", "Flavored Milk Tea", "Cookies n Cream Milk Tea", 60, "product_images/cookncream.png"),
    ("Milk Tea", "Flavored Milk Tea", "Dark Choco Milk Tea",      60, "product_images/darkchocomtea.png"),
    ("Milk Tea", "Flavored Milk Tea", "Matcha Milk Tea",          60, "product_images/matchamilktea.png"),

    # ── SPECIALTY TEA ─────────────────────────────────────────────────────────
    ("Specialty Tea", "Hot Tea", "Green Tea",    30, "product_images/greentea.png"),
    ("Specialty Tea", "Hot Tea", "Jasmine Tea",  30, "product_images/jasminetea.png"),
    ("Specialty Tea", "Hot Tea", "Oolong Tea",   30, "product_images/oolong.png"),
    ("Specialty Tea", "Hot Tea", "Hibiscus Tea", 30, "product_images/hibiscus.png"),

    # ── REFRESHERS & COLD DRINKS ──────────────────────────────────────────────
    ("Refreshers & Cold Drinks", "Lemonade & Fruit Refreshers", "Blue Lemonade",   45, "product_images/bluelemonade.png"),
    ("Refreshers & Cold Drinks", "Lemonade & Fruit Refreshers", "Pink Lychee",     45, "product_images/pinklychee.png"),
    ("Refreshers & Cold Drinks", "Lemonade & Fruit Refreshers", "Green Cucumber",  45, "product_images/greencucumber.png"),
    ("Refreshers & Cold Drinks", "Lemonade & Fruit Refreshers", "Red Strawberry",  45, "product_images/redstrawberry.png"),
]


def _do_seed(db) -> None:
    """Insert all categories (main + sub) and products."""
    # Step 1 — build main categories and their IDs
    main_ids: dict[str, int] = {}
    for main_name in dict.fromkeys(row[0] for row in _MENU):
        cid = db.execute_id(
            "INSERT INTO categories (name, parent_id) VALUES (?, NULL);",
            (main_name,),
        )
        main_ids[main_name] = cid

    # Step 2 — build subcategories
    sub_ids: dict[tuple[str, str], int] = {}
    seen_subs: set[tuple[str, str]] = set()
    for main_name, sub_name, *_ in _MENU:
        key = (main_name, sub_name)
        if key not in seen_subs:
            seen_subs.add(key)
            cid = db.execute_id(
                "INSERT INTO categories (name, parent_id) VALUES (?, ?);",
                (sub_name, main_ids[main_name]),
            )
            sub_ids[key] = cid

    # Step 3 — insert products under their subcategory
    for main_name, sub_name, prod_name, price, image_path in _MENU:
        cat_id = sub_ids[(main_name, sub_name)]
        db.execute(
            "INSERT INTO products "
            "(category_id, name, price, stock, active, low_stock, image_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?);",
            (cat_id, prod_name, float(price), 50, 1, 5, image_path),
        )

    print("[OK] Menu seeded successfully (hierarchical structure).")


def seed_menu_if_empty(db) -> None:
    """Seed official menu only when the products table is empty."""
    row = db.fetchone("SELECT COUNT(*) AS c FROM products;")
    if row and int(row["c"]) > 0:
        print("[INFO] Products not empty — skipping seed.")
        return
    print("[INFO] Products empty — seeding official menu...")
    _do_seed(db)


def seed_menu(db) -> None:
    """DESTRUCTIVE: clear products + categories then reseed."""
    db.execute("DELETE FROM products;")
    db.execute("DELETE FROM categories;")
    _do_seed(db)
