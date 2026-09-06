from django.db import models


class Category(models.Model):
    """Product Category Model"""
    category_id = models.AutoField(primary_key=True)
    category_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.category_name

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'
        ordering = ['category_name']


class Item(models.Model):
    """Item Model - All items belong to CSE department by default"""
    item_id = models.AutoField(primary_key=True)
    item_name = models.CharField(max_length=150)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='items', db_column='category_id')
    unit = models.CharField(max_length=50)  # e.g., pcs, kg, liters, etc.
    quantity = models.IntegerField(default=0)
    min_quantity = models.IntegerField(default=10)  # Minimum stock level
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.item_name} ({self.unit})"

    @property
    def is_low_stock(self):
        return self.quantity <= self.min_quantity

    class Meta:
        db_table = 'items'
        ordering = ['item_name']


class StockTransaction(models.Model):
    """Stock Transaction Model"""
    TRANSACTION_TYPES = (
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
        ('ADJUST', 'Adjustment'),
    )
    
    transaction_id = models.AutoField(primary_key=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='transactions', db_column='item_id')
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    quantity = models.IntegerField()
    user = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, db_column='user_id')
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.item.item_name} - {self.type} - {self.quantity}"

    class Meta:
        db_table = 'stock_transactions'
        ordering = ['-timestamp']
