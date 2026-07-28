import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from app.models import Currency, Item, Order, Price


class CreatePaymentIntentTests(TestCase):
    def setUp(self):
        self.item_usd = Item.objects.create(
            name="Widget", description="A useful widget"
        )
        self.item_eur = Item.objects.create(
            name="Gadget", description="A fancy gadget"
        )
        self.item_both = Item.objects.create(
            name="Dual", description="Has both currencies"
        )
        self.item_multi_usd = Item.objects.create(
            name="BadMulti", description="Two USD prices"
        )
        self.item_no_price = Item.objects.create(
            name="Freebie", description="No price set"
        )

        Price.objects.create(item=self.item_usd, price=1999, currency=Currency.USD)
        Price.objects.create(item=self.item_eur, price=1499, currency=Currency.EUR)
        Price.objects.create(item=self.item_both, price=999, currency=Currency.USD)
        Price.objects.create(item=self.item_both, price=899, currency=Currency.EUR)

        Price.objects.create(item=self.item_multi_usd, price=100, currency=Currency.USD)
        Price.objects.create(item=self.item_multi_usd, price=200, currency=Currency.USD)

        self.order_usd = Order.objects.create(
            name="USD Bundle", description="All items have USD prices"
        )
        self.order_usd.items.add(self.item_usd, self.item_both)

        self.order_eur = Order.objects.create(
            name="EUR Bundle", description="All items have EUR prices"
        )
        self.order_eur.items.add(self.item_eur, self.item_both)

        self.order_mixed = Order.objects.create(
            name="Mixed", description="Mixed currencies"
        )
        self.order_mixed.items.add(self.item_usd, self.item_eur)

        self.empty_order = Order.objects.create(
            name="Empty", description="No items"
        )

    def _post(self, resource_type, object_id, body):
        return self.client.post(
            reverse(
                "create_payment_intent",
                kwargs={
                    "resource_type": resource_type,
                    "object_id": object_id,
                },
            ),
            data=json.dumps(body),
            content_type="application/json",
        )

    def test_get_returns_405(self):
        response = self.client.get(
            reverse(
                "create_payment_intent",
                kwargs={"resource_type": "item", "object_id": self.item_usd.id},
            )
        )
        self.assertEqual(response.status_code, 405)

    def test_invalid_resource_type(self):
        response = self._post("product", 1, {"currency": "usd"})
        self.assertEqual(response.status_code, 400)

    def test_nonexistent_order(self):
        response = self._post("order", 9999, {"currency": "usd"})
        self.assertEqual(response.status_code, 404)

    def test_nonexistent_item(self):
        response = self._post("item", 9999, {"currency": "usd"})
        self.assertEqual(response.status_code, 404)

    def test_missing_currency(self):
        response = self._post("item", self.item_usd.id, {})
        self.assertEqual(response.status_code, 400)
        self.assertIn("currency", response.json()["error"].lower())

    def test_empty_currency(self):
        response = self._post("item", self.item_usd.id, {"currency": ""})
        self.assertEqual(response.status_code, 400)

    def test_invalid_currency(self):
        response = self._post("item", self.item_usd.id, {"currency": "gbp"})
        self.assertEqual(response.status_code, 400)

    def test_missing_json_body(self):
        response = self.client.post(
            reverse(
                "create_payment_intent",
                kwargs={"resource_type": "item", "object_id": self.item_usd.id},
            ),
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("app.views.stripe.PaymentIntent.create")
    def test_item_payment_intent_created(self, mock_create):
        mock_create.return_value.client_secret = "pi_test_secret_123"
        mock_create.return_value.id = "pi_123"

        response = self._post("item", self.item_usd.id, {"currency": "usd"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["client_secret"], "pi_test_secret_123")

        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs["amount"], 1999)
        self.assertEqual(kwargs["currency"], "usd")
        self.assertEqual(kwargs["metadata"]["resource_type"], "item")
        self.assertEqual(kwargs["metadata"]["resource_id"], str(self.item_usd.id))
        self.assertEqual(kwargs["metadata"]["currency"], "usd")
        self.assertIn("idempotency_key", kwargs)

    @patch("app.views.stripe.PaymentIntent.create")
    def test_order_payment_intent_created(self, mock_create):
        mock_create.return_value.client_secret = "pi_test_secret_456"
        mock_create.return_value.id = "pi_456"

        response = self._post("order", self.order_usd.id, {"currency": "usd"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["client_secret"], "pi_test_secret_456")

        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs["amount"], 2998)
        self.assertEqual(kwargs["currency"], "usd")
        self.assertEqual(kwargs["metadata"]["resource_type"], "order")
        self.assertEqual(kwargs["metadata"]["resource_id"], str(self.order_usd.id))

    @patch("app.views.stripe.PaymentIntent.create")
    def test_order_with_eur_currency(self, mock_create):
        mock_create.return_value.client_secret = "pi_eur_secret"
        mock_create.return_value.id = "pi_eur"

        response = self._post("order", self.order_eur.id, {"currency": "eur"})
        self.assertEqual(response.status_code, 200)

        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs["amount"], 2398)
        self.assertEqual(kwargs["currency"], "eur")

    def test_item_without_price_in_currency(self):
        response = self._post("item", self.item_usd.id, {"currency": "eur"})
        self.assertEqual(response.status_code, 400)

    def test_order_missing_price_for_some_items(self):
        response = self._post("order", self.order_mixed.id, {"currency": "usd"})
        self.assertEqual(response.status_code, 400)

    def test_item_with_multiple_prices_same_currency(self):
        response = self._post("item", self.item_multi_usd.id, {"currency": "usd"})
        self.assertEqual(response.status_code, 400)

    def test_empty_order(self):
        response = self._post("order", self.empty_order.id, {"currency": "usd"})
        self.assertEqual(response.status_code, 400)

    @patch("app.views.stripe.PaymentIntent.create")
    def test_idempotency_key_consistent(self, mock_create):
        mock_create.return_value.client_secret = "pi_idem"
        mock_create.return_value.id = "pi_idem"

        self._post("item", self.item_usd.id, {"currency": "usd"})
        self._post("item", self.item_usd.id, {"currency": "usd"})

        first_key = mock_create.call_args_list[0].kwargs["idempotency_key"]
        second_key = mock_create.call_args_list[1].kwargs["idempotency_key"]
        self.assertEqual(first_key, second_key)

    @patch("app.views.stripe.PaymentIntent.create")
    def test_stripe_error_returns_500(self, mock_create):
        import stripe

        mock_create.side_effect = stripe.StripeError("API error")

        response = self._post("item", self.item_usd.id, {"currency": "usd"})
        self.assertEqual(response.status_code, 500)
        self.assertIn("error", response.json())


class OrderCardViewTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            name="Test Bundle", description="A test bundle"
        )

    def test_stripe_key_in_context(self):
        response = self.client.get(
            reverse("order_card", kwargs={"id": self.order.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pk_test_")
        self.assertNotContains(response, "sk_test_")
        self.assertNotContains(response, "sk_live_")

    def test_order_name_in_template(self):
        response = self.client.get(
            reverse("order_card", kwargs={"id": self.order.id})
        )
        self.assertContains(response, "Test Bundle")

    def test_nonexistent_order_returns_404(self):
        response = self.client.get(
            reverse("order_card", kwargs={"id": 9999})
        )
        self.assertEqual(response.status_code, 404)


class PaymentResultViewTests(TestCase):
    def test_result_page_renders(self):
        response = self.client.get(reverse("payment_result"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "stripe")


class ItemCardViewTests(TestCase):
    def setUp(self):
        self.item = Item.objects.create(
            name="Widget", description="A useful widget"
        )
        Price.objects.create(item=self.item, price=1999, currency=Currency.USD)

    def test_stripe_key_in_context(self):
        response = self.client.get(
            reverse("item_card", kwargs={"id": self.item.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pk_test_")
        self.assertNotContains(response, "sk_test_")

    def test_item_name_in_template(self):
        response = self.client.get(
            reverse("item_card", kwargs={"id": self.item.id})
        )
        self.assertContains(response, "Widget")

    def test_price_displayed(self):
        response = self.client.get(
            reverse("item_card", kwargs={"id": self.item.id})
        )
        self.assertContains(response, "19.99")

    def test_nonexistent_item_returns_404(self):
        response = self.client.get(
            reverse("item_card", kwargs={"id": 9999})
        )
        self.assertEqual(response.status_code, 404)
