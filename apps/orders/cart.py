from decimal import Decimal


class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get('cart')
        if cart is None:
            cart = {}
            self.session['cart'] = cart
        self.cart = cart

    def add(self, product, quantity=1):
        product_id = str(product.id)
        if product_id in self.cart:
            new_item = dict(self.cart[product_id])
            new_item['quantity'] = self.cart[product_id]['quantity'] + quantity
            new_cart = dict(self.cart)
            new_cart[product_id] = new_item
            self.session['cart'] = new_cart
            self.cart = new_cart
        else:
            new_cart = dict(self.cart)
            new_cart[product_id] = {'quantity': quantity, 'price': str(product.price)}
            self.session['cart'] = new_cart
            self.cart = new_cart
        self.save()

    def remove(self, product_id):
        product_id = str(product_id)
        if product_id in self.cart:
            new_cart = {k: v for k, v in self.cart.items() if k != product_id}
            self.session['cart'] = new_cart
            self.cart = new_cart
            self.save()

    def update_quantity(self, product_id, quantity):
        product_id = str(product_id)
        if product_id in self.cart and quantity > 0:
            new_item = dict(self.cart[product_id])
            new_item['quantity'] = quantity
            new_cart = dict(self.cart)
            new_cart[product_id] = new_item
            self.session['cart'] = new_cart
            self.cart = new_cart
            self.save()
        elif quantity <= 0:
            self.remove(product_id)

    def save(self):
        self.session.modified = True

    def clear(self):
        self.session['cart'] = {}
        self.cart = {}
        self.session.modified = True

    def get_items(self):
        from apps.catalog.models import Product

        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)
        items = []
        for product in products:
            pid = str(product.id)
            if pid in self.cart:
                cart_item = self.cart[pid]
                items.append({
                    'product': product,
                    'quantity': cart_item['quantity'],
                    'price': product.price,
                    'subtotal': product.price * cart_item['quantity'],
                })
        return items

    def get_total(self):
        return sum(
            Decimal(item['price']) * item['quantity']
            for item in self.cart.values()
        )

    def get_count(self):
        return sum(item['quantity'] for item in self.cart.values())

    def __len__(self):
        return self.get_count()
