from django.db import models


class Requisition(models.Model):
    """Requisition Model - CSE staff requests for items"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('issued', 'Issued'),
    )
    
    req_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='requisitions', db_column='user_id')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    purpose = models.TextField(help_text='Why CSE staff requested item')

    def __str__(self):
        return f"Requisition #{self.req_id} - {self.user.name} - {self.status}"

    class Meta:
        db_table = 'requisitions'
        ordering = ['-created_at']


class RequisitionItem(models.Model):
    """Requisition Items - items requested in a requisition"""
    req_item_id = models.AutoField(primary_key=True)
    requisition = models.ForeignKey(Requisition, on_delete=models.CASCADE, related_name='items', db_column='req_id')
    item = models.ForeignKey('products.Item', on_delete=models.CASCADE, related_name='requisition_items', db_column='item_id')
    quantity = models.IntegerField()

    def __str__(self):
        return f"{self.requisition.req_id} - {self.item.item_name} x {self.quantity}"

    class Meta:
        db_table = 'requisition_items'
