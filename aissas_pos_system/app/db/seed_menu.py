def seed_menu(db):
    # Clear old data
    db.execute("DELETE FROM products;")
    db.execute("DELETE FROM categories;")

    categories = [
        "Hot Coffee",
        "Iced Coffee",
        "Beef",
        "Chicken Pastil",
        "Chicken Poppers Silog",
        "Special Sisig",
        "Pasta",
        "Premium Pasta",
        "Premium Silog",
        "Coolers",
        "Milktea",
        "Hot Tea",
        "Others",
        "Quesadilla/Sandwich",
        "Pizza/Burrito/Pica",
    ]

    cat_ids = {}
    for c in categories:
        cat_id = db.execute_id("INSERT INTO categories (name) VALUES (?)", (c,))
        cat_ids[c] = cat_id

    def add(cat, name, price, stock=50, active=1, low_stock=5):
        db.execute(
            "INSERT INTO products (category_id, name, price, stock, active, low_stock) VALUES (?, ?, ?, ?, ?, ?)",
            (cat_ids[cat], name, price, stock, active, low_stock),
        )

    # --- MAIN MENU (single price items) ---
    menu = [
        # HOT COFFEE
        ("Hot Coffee","Cafe Latte",60),
        ("Hot Coffee","Hot Choco",65),
        ("Hot Coffee","Spanish Latte",70),
        ("Hot Coffee","Mochaccino",70),
        ("Hot Coffee","Salted Caramel",75),
        ("Hot Coffee","Matcha Latte",75),

        # ICED COFFEE
        ("Iced Coffee","Cafe Latte",65),
        ("Iced Coffee","Iced Choco",80),
        ("Iced Coffee","Mochaccino",80),
        ("Iced Coffee","Salted Caramel",80),
        ("Iced Coffee","Matcha Latte",85),
        ("Iced Coffee","Coffee Matcha",90),

        # BEEF
        ("Beef","Beef Silog",95),
        ("Beef","Beef Garlic Mushroom",95),
        ("Beef","Beef Tapa Teriyaki",95),
        ("Beef","Beef Hickory Stir Fry",95),
        ("Beef","Beef Shawarma",95),
        ("Beef","Beef Stir Fry",95),
        ("Beef","Cheesy Beef Caldereta",95),

        # CHICKEN PASTIL
        ("Chicken Pastil","Original Pastil",75),
        ("Chicken Pastil","Chili Garlic",85),
        ("Chicken Pastil","Sweet and Chili Garlic",85),
        ("Chicken Pastil","Biryani",85),

        # CHICKEN POPPERS SILOG
        ("Chicken Poppers Silog","Cheesy Teriyaki Poppers",95),
        ("Chicken Poppers Silog","Korean Gochujang Poppers",95),
        ("Chicken Poppers Silog","House Gravy Poppers",95),

        # SPECIAL SISIG
        ("Special Sisig","Chicken Sisig",90),
        ("Special Sisig","Pork Sisig",90),
        ("Special Sisig","Bangus Sisig",95),
        ("Special Sisig","Fish Fillet Sisig",95),
        ("Special Sisig","Pork Stir Fry Hickory",95),
        ("Special Sisig","Pork Tapa Teriyaki",95),
        ("Special Sisig","Pork Garlic Mushroom",95),

        # PASTA
        ("Pasta","Chicken Pesto",95),
        ("Pasta","Cheesy Carbonara",90),
        ("Pasta","Beef Bolognese",95),
        ("Pasta","Mac & Cheese",95),

        # PREMIUM PASTA
        ("Premium Pasta","Spaghetti Bolognese with Bechamel Sauce",105),

        # PREMIUM SILOG
        ("Premium Silog","Porkchop Silog",110),
        ("Premium Silog","Liempo Silog",120),
        ("Premium Silog","Chicken Steak Silog",110),
        ("Premium Silog","Beef Burger Steak",115),

        # QUESADILLA / SANDWICH
        ("Quesadilla/Sandwich","Chicken Sisig Quesadilla",80),
        ("Quesadilla/Sandwich","Beef Quesadilla",80),
        ("Quesadilla/Sandwich","Mexican Chicken Quesadilla",85),
        ("Quesadilla/Sandwich","Ham and Egg Club",75),
        ("Quesadilla/Sandwich","Chicken and Egg Club",85),
        ("Quesadilla/Sandwich","Beef Steak Hickory Sandwich",95),
        ("Quesadilla/Sandwich","Korean Spam Club Sandwich",95),

        # PIZZA / BURRITO / PICA (fries)
        ("Pizza/Burrito/Pica","Regular Fries",50),
        ("Pizza/Burrito/Pica","Big Fries",70),
        ("Pizza/Burrito/Pica","Cheesy Beef Fries",90),
        ("Pizza/Burrito/Pica","Cheesy Beef Hickory BBQ Fries",100),
        ("Pizza/Burrito/Pica","Cheesy Chicken BBQ Poppers and Fries",120),

        # HOT TEA
        ("Hot Tea","Jasmine Tea",30),
        ("Hot Tea","Green Tea",30),
        ("Hot Tea","Oolong Tea",30),
        ("Hot Tea","Hibiscus Tea",30),
    ]

    for cat, name, price in menu:
        add(cat, name, price)

    # --- MILKTEA (S/M/L) ---
    milktea_sizes = {"S": 45, "M": 55, "L": 65}
    milktea_flavors = [
        "Dark Choco",
        "Matcha",
        "Okinawa",
        "Wintermelon",
        "Cookies and Cream",
        "Taro",
    ]
    for flavor in milktea_flavors:
        for size, price in milktea_sizes.items():
            add("Milktea", f"{flavor} ({size})", price)

    # --- OTHERS (S/M/L) ---
    others_sizes = {"S": 35, "M": 45, "L": 55}
    others_flavors = [
        "Pink Lychee",
        "Red Strawberry",
        "Blue Lemonade",
        "Green Cucumber",
    ]
    for flavor in others_flavors:
        for size, price in others_sizes.items():
            add("Others", f"{flavor} ({size})", price)

    print("[OK] MENU SEEDED SUCCESSFULLY")
