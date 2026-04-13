from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from .models import Farmer, Customer, Product, Order ,Cart , Category
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail 


def home(request):
    is_farmer = False
    if request.user.is_authenticated:
        try:
            is_farmer = request.user.farmer is not None
        except:
            is_farmer = False

    return render(request, 'home.html', {'is_farmer': is_farmer})



def register(request):
    if request.method == 'POST':
        username = request.POST['username'].strip()
        email = request.POST['email']
        password = request.POST['password']
        phone = request.POST['phone']
        role = request.POST['role']
        extra = request.POST['extra']

        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken. Please choose another.')
            return render(request, 'register.html')

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered. Please use another.')
            return render(request, 'register.html')

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        if role == 'farmer':
            Farmer.objects.create(
                user=user,
                name=user,   # THIS SAVES FARMER NAME
                phone=phone,
                location=extra
            )
        else:
            Customer.objects.create(
                user=user, 
                phone=phone, 
                address=extra
            )


        messages.success(request, 'Registration successful! Please login.')
        return redirect('login')

    return render(request, 'register.html')


def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(username=username, password=password)

        if user:
            login(request, user)

            if hasattr(user, 'farmer'):
                return redirect('farmer_dashboard')
            else:
                return redirect('product_list')

    return render(request, 'login.html')






@login_required
def farmer_dashboard(request):

    # Prevent non-farmers from accessing
    if not hasattr(request.user, 'farmer'):
        return redirect('home')

    farmer = request.user.farmer

    # Get farmer products
    products = Product.objects.filter(farmer=farmer)

    # Total products
    total_products = products.count()

    # Orders for farmer products
    orders = Order.objects.filter(product__in=products)

    # Total orders
    total_orders = orders.count()

    # Total revenue
    total_revenue = sum(order.total_price for order in orders)

    context = {
        'products': products,
        'total_products': total_products,
        'total_orders': total_orders,
        'total_revenue': total_revenue
    }

    return render(request, 'farmer_dashboard.html', context)


@login_required
def add_product(request):
    if not hasattr(request.user, 'farmer'):
        return redirect('home')

    categories = Category.objects.all()  # Fetch categories for the dropdown

    if request.method == 'POST':
        farmer = request.user.farmer
        name = request.POST['name']
        price = request.POST['price']
        quantity = int(request.POST['quantity'])   # number only
        unit = request.POST['unit']
        image = request.FILES.get('image')
        category_id = request.POST['category']    # get selected category
        category = Category.objects.get(id=category_id)


        if not image:
            return render(request, 'add_product.html', {
                'categories': categories,
                'error': 'Please upload an image!'
            })
            

        Product.objects.create(
    
            farmer=farmer,
            name=name,
            price=price,
            quantity=quantity,
            unit=unit,
            image=image,
            category=category,   # save the category
        )

        return redirect('farmer_dashboard')

    return render(request, 'add_product.html', {'categories': categories})



def product_list(request):

    query = request.GET.get('q')

    if query:
        products = Product.objects.filter(name__icontains=query)
    else:
        products = Product.objects.all()

    return render(request, 'product_list.html', {'products': products})

@login_required
def delete_product(request, id):
    # Ensure only the owner farmer can delete their product
    product = get_object_or_404(Product, id=id)
    if product.farmer != request.user.farmer:
        return redirect('farmer_dashboard')  # prevent unauthorized deletion

    product.delete()
    return redirect('farmer_dashboard')







@login_required
def add_to_cart(request, id):
    product = get_object_or_404(Product, id=id)

    # Only customers can add to cart
    if not hasattr(request.user, 'customer'):
        return redirect('home')

    customer = request.user.customer

    # Check if this product is already in the cart
    existing_cart_item = Cart.objects.filter(customer=customer, product=product).first()
    if existing_cart_item:
        existing_cart_item.quantity += 1
        existing_cart_item.total_price = existing_cart_item.quantity * product.price
        existing_cart_item.save()
    else:
        Cart.objects.create(
            customer=customer,
            product=product,
            quantity=1,
            total_price=product.price
        )

    return redirect('cart')  # redirect to cart page




@login_required
def place_order(request, id):

    product = get_object_or_404(Product, id=id)
    customer = request.user.customer
    customer_email = customer.user.email

    if request.method == "POST":

        quantity = int(request.POST.get("quantity"))
        unit = request.POST.get("unit")

        product_quantity = product.quantity

        if quantity > product_quantity:
            return render(request, "place_order.html", {
                "product": product,
                "error": "Not enough quantity available"
            })

        total_price = quantity * product.price

        # Get farmer details
        farmer_email = product.farmer.user.email
        farmer_name = product.farmer.user.username

        # Save Order
        Order.objects.create(
            customer=customer,
            product=product,
            quantity=quantity,
            unit=unit,
            total_price=total_price,
            status='pending'
        )

        # Send email to farmer
        send_mail(
            subject='New Order Received',
            message=f'Hi {farmer_name},\n\nYou received a new order for {product.name}.\nQuantity: {quantity} {unit}\nTotal Price: ₹{total_price}',
            from_email='snehaangadi690@gmail.com',
            recipient_list=[farmer_email],
        )


        # Reduce product quantity
        product.quantity = product_quantity - quantity
        product.save()

        return redirect("orders")

    return render(request, "place_order.html", {"product": product})


@login_required
def update_order_status(request, id):

    order = get_object_or_404(Order, id=id)

    if request.method == "POST":
        status = request.POST.get("status")
        order.status = status
        order.save()

        customer_email = order.customer.user.email

        send_mail(
            subject="Order Status Updated",
            message=f"Your order for {order.product.name} is now: {status}",
            from_email="snehaangadi690@gmail.com",
            recipient_list=[customer_email],
        )

    return redirect("orders")



@login_required
def orders(request):

    # If logged user is a customer
    if hasattr(request.user, 'customer'):
        customer = request.user.customer
        orders = Order.objects.filter(customer=customer).order_by('-created_at')

    # If logged user is a farmer
    elif hasattr(request.user, 'farmer'):
        farmer = request.user.farmer
        products = Product.objects.filter(farmer=farmer)
        orders = Order.objects.filter(product__in=products).order_by('-created_at')


    return render(request, 'orders.html', {'orders': orders})





@login_required
def user_logout(request):
    logout(request)
    return redirect('home')


@login_required
def cart(request):

    # get logged customer
    customer = request.user.customer

    # get cart items of this customer
    cart_items = Cart.objects.filter(customer=customer).exclude(product__isnull=True)

    # calculate total cart price
    cart_total = sum(item.total_price for item in cart_items)

    # send data to template
    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'cart_total': cart_total
    })


@login_required
def remove_from_cart(request, id):
    cart_item = get_object_or_404(Cart, id=id)

    # Only allow the owner to remove
    if cart_item.customer.user == request.user:
        cart_item.delete()

    return redirect('cart')  # redirect to cart page