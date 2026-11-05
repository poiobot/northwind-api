from domain.common.profile import Profile
from domain.common.user import User
from domain.common.media import Media
from domain.category import Category
from domain.customer import Customer
from domain.employee import Employee
from domain.employee_territory import EmployeeTerritory
from domain.order import Order
from domain.order_detail import OrderDetail
from domain.product import Product
from domain.region import Region
from domain.shipper import Shipper
from domain.supplier import Supplier

# Rebuild models after all are imported
Profile.model_rebuild()
User.model_rebuild()
Media.model_rebuild()
Category.model_rebuild()
Customer.model_rebuild()
Employee.model_rebuild()
EmployeeTerritory.model_rebuild()
Order.model_rebuild()
OrderDetail.model_rebuild()
Product.model_rebuild()
Region.model_rebuild()
Shipper.model_rebuild()
Supplier.model_rebuild()


__all__ = ["Profile", "User", "Media", "Category", "Customer", "Employee", "EmployeeTerritory", "Order", "OrderDetail", "Product", "Region", "Shipper", "Supplier"]
