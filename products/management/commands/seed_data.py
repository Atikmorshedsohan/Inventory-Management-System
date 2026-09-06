from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from products.models import Category, Item
from suppliers.models import Supplier
from datetime import date

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed database with sample data for CSE Inventory'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding database...')

        # Create sample users
        if not User.objects.filter(email='admin@cse.edu').exists():
            User.objects.create_superuser(
                email='admin@cse.edu',
                name='Admin User',
                password='admin123',
                role='admin'
            )
            self.stdout.write(self.style.SUCCESS('✓ Admin user created'))

        if not User.objects.filter(email='staff@cse.edu').exists():
            User.objects.create_user(
                email='staff@cse.edu',
                name='Staff User',
                password='staff123',
                role='staff'
            )
            self.stdout.write(self.style.SUCCESS('✓ Staff user created'))

        # Create categories
        categories_data = [
            {'category_name': 'Electronics', 'description': 'Electronic devices and components'},
            {'category_name': 'Furniture', 'description': 'Office and lab furniture'},
            {'category_name': 'Stationery', 'description': 'Papers, pens, and office supplies'},
            {'category_name': 'Computers', 'description': 'Computers and computer accessories'},
            {'category_name': 'Lab Equipment', 'description': 'Laboratory equipment and tools'},
        ]

        for cat_data in categories_data:
            category, created = Category.objects.get_or_create(
                category_name=cat_data['category_name'],
                defaults={'description': cat_data['description']}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✓ Category: {category.category_name}'))

        # Create suppliers
        suppliers_data = [
            {
                'supplier_name': 'Tech Solutions Ltd',
                'contact_person': 'John Smith',
                'phone': '123-456-7890',
                'email': 'sales@techsolutions.com',
                'address': '123 Tech Street, Silicon Valley'
            },
            {
                'supplier_name': 'Office Supplies Co',
                'contact_person': 'Jane Doe',
                'phone': '098-765-4321',
                'email': 'contact@officesupplies.com',
                'address': '456 Supply Avenue, Business District'
            },
            {
                'supplier_name': 'Computer World',
                'contact_person': 'Bob Johnson',
                'phone': '555-123-4567',
                'email': 'info@computerworld.com',
                'address': '789 Hardware Lane, Tech Park'
            },
        ]

        for sup_data in suppliers_data:
            supplier, created = Supplier.objects.get_or_create(
                supplier_name=sup_data['supplier_name'],
                defaults=sup_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✓ Supplier: {supplier.supplier_name}'))

        # Create items
        electronics = Category.objects.get(category_name='Electronics')
        computers = Category.objects.get(category_name='Computers')
        stationery = Category.objects.get(category_name='Stationery')
        furniture = Category.objects.get(category_name='Furniture')
        lab_equipment = Category.objects.get(category_name='Lab Equipment')

        items_data = [
            {
                'item_name': 'Dell Laptop i5',
                'category': computers,
                'unit': 'pcs',
                'quantity': 0,
                'min_quantity': 5,
                'description': 'Dell Inspiron laptops with i5 processor'
            },
            {
                'item_name': 'HP Desktop PC',
                'category': computers,
                'unit': 'pcs',
                'quantity': 0,
                'min_quantity': 10,
                'description': 'HP desktop computers for lab'
            },
            {
                'item_name': 'LED Monitor 24"',
                'category': electronics,
                'unit': 'pcs',
                'quantity': 0,
                'min_quantity': 15,
                'description': '24 inch LED monitors'
            },
            {
                'item_name': 'Wireless Mouse',
                'category': electronics,
                'unit': 'pcs',
                'quantity': 0,
                'min_quantity': 20,
                'description': 'Logitech wireless mouse'
            },
            {
                'item_name': 'Keyboard',
                'category': electronics,
                'unit': 'pcs',
                'quantity': 0,
                'min_quantity': 20,
                'description': 'Standard USB keyboards'
            },
            {
                'item_name': 'A4 Paper',
                'category': stationery,
                'unit': 'reams',
                'quantity': 0,
                'min_quantity': 50,
                'description': 'A4 size copy paper'
            },
            {
                'item_name': 'Whiteboard Markers',
                'category': stationery,
                'unit': 'boxes',
                'quantity': 0,
                'min_quantity': 10,
                'description': 'Whiteboard markers - assorted colors'
            },
            {
                'item_name': 'Office Chair',
                'category': furniture,
                'unit': 'pcs',
                'quantity': 0,
                'min_quantity': 8,
                'description': 'Ergonomic office chairs'
            },
            {
                'item_name': 'Lab Table',
                'category': furniture,
                'unit': 'pcs',
                'quantity': 0,
                'min_quantity': 5,
                'description': 'Computer lab tables'
            },
            {
                'item_name': 'Multimeter',
                'category': lab_equipment,
                'unit': 'pcs',
                'quantity': 0,
                'min_quantity': 10,
                'description': 'Digital multimeters for electronics lab'
            },
            {
                'item_name': 'Oscilloscope',
                'category': lab_equipment,
                'unit': 'pcs',
                'quantity': 0,
                'min_quantity': 3,
                'description': 'Digital oscilloscopes'
            },
            {
                'item_name': 'Arduino Uno',
                'category': lab_equipment,
                'unit': 'pcs',
                'quantity': 0,
                'min_quantity': 15,
                'description': 'Arduino Uno development boards'
            },
        ]

        for item_data in items_data:
            item, created = Item.objects.get_or_create(
                item_name=item_data['item_name'],
                defaults=item_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✓ Item: {item.item_name}'))

        self.stdout.write(self.style.SUCCESS('\n✅ Database seeding completed!'))
        self.stdout.write('\nCreated:')
        self.stdout.write(f'  - {User.objects.count()} users')
        self.stdout.write(f'  - {Category.objects.count()} categories')
        self.stdout.write(f'  - {Supplier.objects.count()} suppliers')
        self.stdout.write(f'  - {Item.objects.count()} items')
        self.stdout.write('\nLogin credentials:')
        self.stdout.write('  Admin: admin@cse.edu / admin123')
        self.stdout.write('  Staff: staff@cse.edu / staff123')
