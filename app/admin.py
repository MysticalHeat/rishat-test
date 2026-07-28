from django.contrib import admin

from app.models import Item, Order, Price

admin.site.register(Item)
admin.site.register(Order)
admin.site.register(Price)
