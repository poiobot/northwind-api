from domain.model import Order

from typing import List, Dict, Union, Optional, Any, Tuple
from data.generic_dao import GenericDAO
from lib.hooks import hooks, HookPoint


class OrderCrudCTL:
	"""
	Order CRUD Controller - Handles CRUD operations for Order entities
	Uses GenericDAO for database-agnostic operations
	"""

	dao = GenericDAO()

	@classmethod
	def create(cls, order: Union[Order, Dict], reify: bool = True) -> Optional[Order]:
		"""
		Register a new order

		Args:
			order: Order object or dictionary with order data
			reify: If True, return Order object; if False, return dictionary

		Returns:
			Created Order object or dictionary, None if creation fails
		"""
		order = hooks.execute_sync(HookPoint.PRE_CREATE, "Order", data=order)
		result = cls.dao.insert(entity=Order, data=order, reify=reify)
		hooks.execute_sync(HookPoint.POST_CREATE, "Order", data=result)
		return result


	@classmethod
	def update(cls, order_id: str, order: Union[Order, Dict], reify: bool = True) -> Optional[Order]:
		"""
		Update an existing order

		Args:
			order_id: The order ID to update
			order: Order object or dictionary with updated data
			reify: If True, return Order object; if False, return dictionary

		Returns:
			Updated Order object or dictionary
		"""
		order = hooks.execute_sync(HookPoint.PRE_UPDATE, "Order", data=order)
		result = cls.dao.update(entity=Order, id=order_id, data=order, reify=reify)
		hooks.execute_sync(HookPoint.POST_UPDATE, "Order", data=result)
		return result

	@classmethod
	def get_by_id(cls, order_id: str, keys: List[str] = "*", expand: Optional[List[str]] = None, reify: bool = True) -> Optional[Order]:
		"""
		Retrieve a order by its ID

		Args:
			order_id: The order ID to search for
			keys: List of fields to retrieve (default: all fields)
			expand: List of reference fields to expand/join
			reify: If True, return Order object; if False, return dictionary

		Returns:
			Order object or dictionary, None if not found
		"""
		result = cls.dao.find_by_id(entity=Order, id=order_id, keys=keys, expand=expand, reify=reify)
		result = hooks.execute_sync(HookPoint.POST_FETCH, "Order", data=result)
		return result

	@classmethod
	def get_list(cls, order_ids: List[str], keys: List[str] = "*", expand: List[str]=None, reify: bool = True) -> List[Union[Order, Dict]]:
		"""
		Retrieve multiple orders by their IDs

		Args:
			order_ids: List of order IDs to retrieve
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Order objects; if False, return dictionaries

		Returns:
			Generator yielding Order objects or dictionaries
		"""
		return cls.dao.find_list(entity=Order, ids=order_ids, keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[Order, Dict]]:
		"""
		Retrieve orders by key-value

		Args:
			key: The field name to search
			value: The value to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Order objects; if False, return dictionaries

		Returns:
			Generator yielding Order objects or dictionaries
		"""
		return cls.dao.fetch(entity=Order, query=[(key, "==", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value_like(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[Order, Dict]]:
		"""
		Retrieve orders by key-value with LIKE operator

		Args:
			key: The field name to search
			value: The value pattern to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Order objects; if False, return dictionaries

		Returns:
			Generator yielding Order objects or dictionaries
		"""
		return cls.dao.fetch(entity=Order, query=[(key, "like", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def fetch(cls, query: Optional[List[Tuple]]=None, expand: Optional[List[str]]=None, keys: List[str]="*", sort_by: Optional[List[Tuple[str, int]]]=None, reify: bool=True) -> List[Union[Order, Dict]]:
		"""
		Fetch orders with custom query, expansion, and sorting

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			sort_by: List of tuples for sorting [('field', 1/-1), ...] (1=asc, -1=desc)
			reify: If True, return Order objects; if False, return dictionaries

		Returns:
			Generator yielding Order objects or dictionaries
		"""
		return cls.dao.fetch(entity=Order, query=query, expand=expand, keys=keys, sort_by=sort_by, reify=reify)

	@classmethod
	def delete(cls, order_id: str, physical_delete: bool = True) -> bool:
		"""
		Delete a order by ID

		Args:
			order_id: The order ID to delete
			physical_delete: If True, permanently delete; if False, soft delete (mark as inactive)

		Returns:
			True if deletion successful, False otherwise
		"""
		hooks.execute_sync(HookPoint.PRE_DELETE, "Order", data=order_id)
		result = cls.dao.delete(entity=Order, id=order_id, physical_delete=physical_delete)
		hooks.execute_sync(HookPoint.POST_DELETE, "Order", data=order_id)
		return result

	@classmethod
	def delete_list(cls, order_ids: List[str], physical_delete: bool = True) -> int:
		"""
		Delete multiple orders by their IDs

		Args:
			order_ids: List of order IDs to delete
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of orders deleted
		"""
		return cls.dao.delete_objects_list(
			entity=Order,
			ids=order_ids,
			physical_deletion=physical_delete
		)

	@classmethod
	def delete_many(cls, query: Optional[List[Tuple]] = None, physical_delete: bool = True) -> int:
		"""
		Delete multiple orders matching a query

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of orders deleted
		"""
		return cls.dao.delete_many(entity=Order, query=query, physical_delete=physical_delete)

	@classmethod
	def delete_all(cls, physical_delete: bool = False) -> int:
		"""
		Delete all orders (use with caution!)

		Args:
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of orders deleted
		"""
		return cls.dao.delete_all(entity=Order, physical_deletion=physical_delete)
