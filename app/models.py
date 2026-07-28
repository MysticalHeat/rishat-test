from django.db import models
from django.db.models.aggregates import Sum


class Currency(models.TextChoices):
    USD = "usd", "US Dollar"
    EUR = "eur", "Euro"


class Item(models.Model):
    name = models.CharField()
    description = models.TextField()

    def __str__(self):
        return self.name


class Price(models.Model):
    price = models.PositiveBigIntegerField()
    currency = models.CharField(
        max_length=3, choices=Currency.choices, default=Currency.USD
    )
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="prices")

    @property
    def display_price(self):
        return self.price / 100


class Order(models.Model):
    name = models.CharField()
    description = models.TextField()
    items = models.ManyToManyField(Item, related_name="orders")

    @property
    def total_cost(self):
        totals = (
            Price.objects.filter(item__orders=self)
            .values("currency")
            .annotate(total=Sum("price"))
        )

        return {row["currency"]: row["total"] / 100 for row in totals}

    def __str__(self):
        return self.name
