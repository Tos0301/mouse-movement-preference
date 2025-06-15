from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import csv, os
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import base64
import json

app = Flask(__name__)
app.secret_key = 'secret_key'

scopes = ['https://www.googleapis.com/auth/spreadsheets']
service_account_path = 'encoded.txt'  # base64でエンコードされたサービスアカウントキー
spreadsheet_id = '1VMtBdoe1gy_yzarBGbvxI7x4uWnUAropa2wkU_lS4YM'

with open(service_account_path, 'r') as f:
    encoded = f.read()
decoded_json = base64.b64decode(encoded).decode('utf-8')
service_info = json.loads(decoded_json)

credentials = Credentials.from_service_account_info(service_info, scopes=scopes)
gc = gspread.authorize(credentials)
worksheet = gc.open_by_key(spreadsheet_id).sheet1

def log_action(action, page="", total_price=0, hotels=None, quantities=None, subtotals=None, room_type=None, breakfast_options=None):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    participant_id = session.get("participant_id", "")
    hotels = hotels or []
    quantities = quantities or []
    subtotals = subtotals or []
    room_type = room_type or []
    breakfast_options = breakfast_options or []
    
    worksheet.append_row([
        now, participant_id, action, total_price,
        ",".join(hotels),
        ",".join(map(str, quantities)),
        ",".join(map(str, subtotals)),
        ",".join(room_type),
        ",".join(breakfast_options),
        page
    ])

def load_products():
    df = pd.read_csv("data/products.csv", dtype=str).fillna("")  # 欠損を空文字で埋める
    products = df.to_dict(orient="records")
    
    for product in products:
        product['room_type'] = product['room_type'].split('|') if product['room_type'] else []
        product['breakfast_options'] = product['breakfast_options'].split('|') if product['breakfast_options'] else []

        if product.get('breakfast_prices'):
            product[ 'breakfast_prices']=list(map(int, product["breakfast_prices"].split('|')))
        else:
            product['breakfast_prices'] = []
    
    return products


def load_specs():
    specs = {}
    with open("data/specs.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # IDをゼロ埋めして確実に一致させる
            product_id = row["id"].strip().zfill(3)
            specs[product_id] = row["specs"]
    return specs

@app.route('/reset_session')
def reset_session():
    session.clear()
    return "セッションを初期化しました"


@app.route('/')
def input_id():
    return render_template('input_id.html')

@app.route('/set_id', methods=['POST'])
def set_participant_id():
    prefix = request.form.get("prefix", "").upper()
    birthdate = request.form.get("birthdate", "")
    suffix = request.form.get("suffix", "")
    
    if not (prefix and birthdate and suffix):
        return redirect(url_for("input_id"))

    participant_id = f"{prefix}{birthdate}{suffix}"
    session["participant_id"] = participant_id

    # 任意：ログを記録
    log_action("ID入力", page="ID")  # log_action関数があれば

    return redirect(url_for("confirm_id"))

@app.route('/confirm_id', methods=['GET', 'POST'])
def confirm_id():
    participant_id = session.get("participant_id", "")
    if not participant_id:
        return redirect(url_for("input_id"))
    return render_template("confirm_id.html", participant_id=participant_id)

@app.route('/index', methods=['GET', 'POST'])
def index():
    products = load_products()
    cart = session.get("cart", [])
    cart_count = sum(item['quantity'] for item in cart if isinstance(item, dict) and 'quantity' in item)

    if request.method == 'POST':
        log_action("商品一覧表示", page="一覧")
    return render_template('index.html', products=products, cart_count=cart_count)

@app.route('/product/<product_id>', methods=['GET', 'POST'])
def product_detail(product_id):
    products = load_products()
    product = next((p for p in products if p["id"] == product_id), None)
    specs_data = load_specs()
    cart = session.get("cart", [])
    cart_count = sum(item['quantity'] for item in cart if isinstance(item, dict) and 'quantity' in item)

    base_prefix = "noimage"
    image_list = []

    if product and product.get("image"):
        base_prefix = product["image"].rsplit(".", 1)[0]  # 例: towel_b
        room_type = product.get("room_type", [])
        default_room_type = room_type[0] if room_type else ""
        breakfast_options = product.get("breakfast_options", [])
        breakfast_prices = product.get("breakfast_prices", [])
        breakfast_combined = list(zip(breakfast_options, breakfast_prices))

        # 1枚目：カラーバリエーション画像（towel_b_sand-beige_1.jpg）
        first_image = f"{base_prefix}_{default_room_type}_1.jpg"
        image_folder = os.path.join("static", "images")
        if os.path.exists(os.path.join(image_folder, first_image)):
            image_list.append(first_image)

        # 2枚目以降：共通画像（towel_b_2.jpg, towel_b_3.jpg, ...）
        for i in range(2, 6):  # 2〜5枚目まで
            filename = f"{base_prefix}_{i}.jpg"
            if os.path.exists(os.path.join(image_folder, filename)):
                image_list.append(filename)

    if request.method == 'POST':
        log_action(f"商品詳細表示: {product_id}", page="詳細")

    return render_template(
        'product.html',
        product=product,
        cart_count=cart_count,
        specs=specs_data.get(product_id, "(商品説明がありません)"),
        image_list=image_list,
        base_prefix=base_prefix  # JSに渡す
        breakfast_combined=breakfast_combined 
    )




@app.route('/go_product', methods=['POST'])
def go_product():
    product_id = request.form.get("product_id")
    return redirect(url_for('product_detail', product_id=product_id))

@app.route('/go_cart', methods=['POST'])
def go_cart():
    log_action("カートを見る", page="詳細")
    return redirect(url_for('cart'))


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product_id = request.form["product_id"]
    quantity = int(request.form["quantity"])

    products = load_products()
    product = next((p for p in products if p["id"] == product_id), None)

    cart = session.get("cart", [])

    # 新しく追加するアイテム
    new_item = {
        "product_id": product_id,
        "quantity": quantity,
        "room_type": request.form.get("room_type", ""),
        "breakfast_options": request.form.get("breakfast_options", "")
    }

    # 同じ商品・色・サイズの組み合わせがあれば統合
    found = False
    for item in cart:
        if isinstance(item, dict) and \
            item.get("product_id") == new_item["product_id"] and \
            item.get("room_type") == new_item["room_type"] and \
            item.get("breakfast_options") == new_item["breakfast_options"]:
            item["quantity"] += quantity
            found = True
            break


    if not found:
        cart.append(new_item)

    session["cart"] = [item for item in cart if isinstance(item, dict) and 'product_id' in item]



    if product:
        name = product["name"]
        price = int(product["price"])
        subtotal = price * quantity

        log_action("カートに追加", total_price=subtotal,
                   hotels=[name], quantities=[quantity], subtotals=[subtotal], page="詳細")
    else:
        log_action("カートに追加", page="詳細")

    # ✅ 非同期(fetch)リクエストの場合はJSONで返す
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        cart_count = sum(item['quantity'] for item in cart if isinstance(item, dict) and 'quantity' in item)
        return jsonify({"cart_count": cart_count})

    # ✅ 通常遷移のときはリダイレクト（使っていないなら return "", 204 のままでもOK）
    return "", 204



@app.route('/cart', methods=['GET', 'POST'])
def cart():
    products = load_products()
    cart = session.get("cart", [])
    cart_items = []
    total = 0

    for item in cart:
        if not isinstance(item, dict):
            continue

        product = next((p for p in products if p["id"] == item["product_id"]), None)
        if product:
            subtotal = int(product["price"]) * item["quantity"]
            total += subtotal

            # ✅ color に基づく画像ファイル名を構築
            room_type = item.get("room_type", "").strip().lower()
            image_base = product["image"].rsplit(".", 1)[0]  # "mag_c" を取得
            
            if room_type:
                filename = f"{image_base}_{room_type}_1.jpg"
            else:
                filename = f"{image_base}_1.jpg"
            image_path = f"images/{image_base}_{room_type}_1.jpg"

            cart_items.append({
                "product": product,
                "quantity": item["quantity"],
                "subtotal": subtotal,
                "room_type": room_type,
                "breakfast_options": item.get("breakfast_options", ""),
                "image_path": image_path  # ✅ ここが cart.html で参照される
            })

    
    cart_count = sum(item['quantity'] for item in cart if isinstance(item, dict) and 'quantity' in item)
    
    if request.method == 'POST':
        log_action("カート表示", page="カート", total_price=total,
                   hotels=[item["product"]["name"] for item in cart_items],
                   quantities=[item["quantity"] for item in cart_items],
                   subtotals=[item["subtotal"] for item in cart_items])
    
    return render_template(
        'cart.html', 
        cart_items=cart_items, 
        total=total, 
        cart_count=cart_count,
    )

@app.route('/back_to_index', methods=['POST'])
def back_to_index():
    log_action("商品一覧に戻る", page="カート")
    return redirect(url_for('index'))


@app.route('/update_cart', methods=['POST'])
def update_cart():
    product_id = request.form.get("product_id")
    room_type = request.form.get("room_type", "")
    breakfast_options = request.form.get("breakfast_options", "")
    try:
        quantity = int(request.form.get("quantity", 1))
    except (ValueError, TypeError):
        quantity = 1  # 万が一無効な値が来たら1に戻す

    cart = session.get("cart", [])
    new_cart = []
    for item in cart:
        
        if not isinstance(item, dict):
            continue  # 不正なデータはスキップ

        if item["product_id"] == product_id and item["room_type"] == room_type and item["breakfast_options"] == breakfast_options:
            if quantity > 0:
                item["quantity"] = quantity
                new_cart.append(item)

        else:
            new_cart.append(item)  # 存在しない場合でもエラーにしない

    session["cart"] = new_cart
    log_action(f"数量更新: {product_id} → {quantity}", page="カート")
    return redirect(url_for("cart"))

@app.route('/cart_count', methods=['GET'])
def cart_count():
    cart = session.get("cart", [])
    count = sum(item['quantity'] for item in cart if isinstance(item, dict) and 'quantity' in item)
    return jsonify({'count': count})




@app.route('/go_confirm', methods=['POST'])
def go_confirm():
    log_action("確認画面へ進む", page="カート")
    return redirect(url_for('confirm'))

#@app.route('/back_to_index', methods=['POST'])
#def go_index():
    #return redirect(url_for('index'))

@app.route('/back_to_cart', methods=['POST'])
def back_to_cart():
    log_action("カートに戻る", page="確認")
    return redirect(url_for('cart'))

@app.route('/confirm', methods=['GET'])
def confirm():
    cart = session.get("cart", [])
    products = load_products()

    cart_items = []
    total = 0
    cart_count = 0

    for item in cart:
        if not isinstance(item, dict):
            continue  # 不正なデータはスキップ

        product_id = item['product_id']
        quantity = item['quantity']
        product = next((p for p in products if p["id"] == product_id), None)

        if product:
            subtotal = int(product["price"]) * quantity
            cart_items.append({
                "product": product,
                "quantity": quantity,
                "subtotal": subtotal,
                "room_type": item.get("room_type", ""),
                "breakfast_options": item.get("breakfast_options", "")
            })
            total += subtotal
            cart_count += quantity

    log_action("購入確認画面表示", page="確認")
    return render_template("confirm.html", cart_items=cart_items, cart_count=cart_count, total=total)


@app.route('/complete', methods=['POST'])
def complete():
    
    cart = session.get("cart", [])
    products = load_products()

    product_names = []
    quantities = []
    subtotals = []

    total_price = 0

    for item in cart:
        if not isinstance(item, dict):
            continue  # 不正なデータはスキップ
        
        product_id = item['product_id']
        quantity = item['quantity']
        product = next((p for p in products if p["id"] == product_id), None)

        if product:
            name = product["name"]
            price = int(product["price"])
            subtotal = price * quantity

            product_names.append(name)
            quantities.append(quantity)
            subtotals.append(subtotal)
            total_price += subtotal

    room_type = [item.get("room_type", "") for item in cart]
    breakfast_options = [item.get("breakfast_options", "") for item in cart]

    log_action("購入確定", total_price=total_price,
            hotels=product_names,
            quantities=quantities,
            subtotals=subtotals,
            room_type=room_type,
            breakfast_options=breakfast_options,
            page="確認")


    session["cart"] = []  # ✅ カートを空にするのはログ記録のあと

    return redirect(url_for("thanks"))



@app.route('/thanks', methods=['GET', 'POST'])
def thanks():
    log_action("購入完了", page="完了")
    return render_template('thanks.html', cart_count=0)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
