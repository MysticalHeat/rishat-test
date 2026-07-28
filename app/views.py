import json

import stripe
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from app.models import Currency, Item, Order, Price

stripe.api_key = settings.STRIPE_SECRET_KEY


RESOURCE_TYPE_FORBIDDEN = "Оплата возможна только для item и order"
CURRENCY_REQUIRED = "Поле currency обязательно (usd или eur)"
CURRENCY_INVALID = "Недопустимая валюта. Разрешены: usd, eur"
NO_PRICE_FOUND = "Цена в валюте {currency} не найдена"
MULTIPLE_PRICES = "У товара несколько цен в одной валюте"
NO_PRICES_FOR_ORDER = "Ни у одного товара из заказа нет цены в валюте {currency}"
MISSING_PRICE_IN_ORDER = "Не для всех товаров доступна цена в валюте {currency}"
ZERO_AMOUNT = "Сумма заказа должна быть больше нуля"
STRIPE_ERROR = "Не удалось создать платеж"


def index(request):
    orders = Order.objects.all()
    items = Item.objects.all()
    return render(request, "app/index.html", {"orders": orders, "items": items})


def order_card(request, id):
    order = get_object_or_404(Order, id=id)
    return render(
        request,
        "app/payment_card/order_card.html",
        {
            "order": order,
            "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        },
    )


def payment_result(request):
    return render(
        request,
        "app/payment_card/result.html",
        {
            "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        },
    )


def _get_item_prices_in_currency(resource_type, object_id, currency):
    if resource_type == "item":
        item = get_object_or_404(Item, id=object_id)
        prices = Price.objects.filter(item=item, currency=currency)
        item_prices = [(item, prices)]
    else:
        order = get_object_or_404(Order, id=object_id)
        item_prices = []
        for item in order.items.all():
            prices = Price.objects.filter(item=item, currency=currency)
            item_prices.append((item, prices))
    return item_prices


def _validate_and_calculate(item_prices, currency):
    total = 0
    for item, prices in item_prices:
        count = prices.count()
        if count == 0:
            raise ValueError(NO_PRICE_FOUND.format(currency=currency.upper()))
        if count > 1:
            raise ValueError(MULTIPLE_PRICES)
        total += prices.first().price

    if total == 0:
        raise ValueError(ZERO_AMOUNT)

    return total


@require_POST
@csrf_protect
def create_payment_intent(request, resource_type, object_id):
    if resource_type not in ("item", "order"):
        return JsonResponse(
            {"error": RESOURCE_TYPE_FORBIDDEN}, status=400
        )

    try:
        body = json.loads(request.body)
        currency = body.get("currency", "").lower()
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": CURRENCY_REQUIRED}, status=400
        )

    if not currency:
        return JsonResponse(
            {"error": CURRENCY_REQUIRED}, status=400
        )

    if currency not in Currency.values:
        return JsonResponse(
            {"error": CURRENCY_INVALID}, status=400
        )

    try:
        item_prices = _get_item_prices_in_currency(resource_type, object_id, currency)
    except ValueError:
        return JsonResponse(
            {"error": NO_PRICE_FOUND.format(currency=currency.upper())}, status=400
        )

    try:
        amount = _validate_and_calculate(item_prices, currency)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    idempotency_key = (
        f"payment-{resource_type}-{object_id}-{currency}-{amount}"
    )

    try:
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            automatic_payment_methods={"enabled": True},
            metadata={
                "resource_type": resource_type,
                "resource_id": str(object_id),
                "currency": currency,
            },
            idempotency_key=idempotency_key,
        )
    except stripe.StripeError:
        return JsonResponse(
            {"error": STRIPE_ERROR}, status=500
        )

    return JsonResponse({"client_secret": intent.client_secret})
