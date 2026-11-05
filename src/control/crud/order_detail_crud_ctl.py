from domain.model import OrderDetail

from typing import List, Dict, Union, Optional, Any, Tuple
from data.generic_dao import GenericDAO
from lib.hooks import hooks, HookPoint


class OrderDetailCrudCTL:
	"""
	OrderDetail CRUD Controller - Handles CRUD operations for OrderDetail entities
	Uses GenericDAO for database-agnostic operations
	"""

	dao = GenericDAO()

	@classmethod
	def create(cls, order_detail: Union[OrderDetail, Dict], reify: bool = True) -> Optional[OrderDetail]:
		"""
		Register a new order_detail

		Args:
			order_detail: OrderDetail object or dictionary with order_detail data
			reify: If True, return OrderDetail object; if False, return dictionary

		Returns:
			Created OrderDetail object or dictionary, None if creation fails
		"""
		order_detail = hooks.execute_sync(HookPoint.PRE_CREATE, "OrderDetail", data=order_detail)
		result = cls.dao.insert(entity=OrderDetail, data=order_detail, reify=reify)
		hooks.execute_sync(HookPoint.POST_CREATE, "OrderDetail", data=result)
		return result


	@classmethod
	def update(cls, order_detail_id: str, order_detail: Union[OrderDetail, Dict], reify: bool = True) -> Optional[OrderDetail]:
		"""
		Update an existing order_detail

		Args:
			order_detail_id: The order_detail ID to update
			order_detail: OrderDetail object or dictionary with updated data
			reify: If True, return OrderDetail object; if False, return dictionary

		Returns:
			Updated OrderDetail object or dictionary
		"""
		order_detail = hooks.execute_sync(HookPoint.PRE_UPDATE, "OrderDetail", data=order_detail)
		result = cls.dao.update(entity=OrderDetail, id=order_detail_id, data=order_detail, reify=reify)
		hooks.execute_sync(HookPoint.POST_UPDATE, "OrderDetail", data=result)
		return result

	@classmethod
	def get_by_id(cls, order_detail_id: str, keys: List[str] = "*", expand: Optional[List[str]] = None, reify: bool = True) -> Optional[OrderDetail]:
		"""
		Retrieve a order_detail by its ID

		Args:
			order_detail_id: The order_detail ID to search for
			keys: List of fields to retrieve (default: all fields)
			expand: List of reference fields to expand/join
			reify: If True, return OrderDetail object; if False, return dictionary

		Returns:
			OrderDetail object or dictionary, None if not found
		"""
		result = cls.dao.find_by_id(entity=OrderDetail, id=order_detail_id, keys=keys, expand=expand, reify=reify)
		result = hooks.execute_sync(HookPoint.POST_FETCH, "OrderDetail", data=result)
		return result

	@classmethod
	def get_list(cls, order_detail_ids: List[str], keys: List[str] = "*", expand: List[str]=None, reify: bool = True) -> List[Union[OrderDetail, Dict]]:
		"""
		Retrieve multiple order_details by their IDs

		Args:
			order_detail_ids: List of order_detail IDs to retrieve
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return OrderDetail objects; if False, return dictionaries

		Returns:
			Generator yielding OrderDetail objects or dictionaries
		"""
		return cls.dao.find_list(entity=OrderDetail, ids=order_detail_ids, keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[OrderDetail, Dict]]:
		"""
		Retrieve order_details by key-value

		Args:
			key: The field name to search
			value: The value to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return OrderDetail objects; if False, return dictionaries

		Returns:
			Generator yielding OrderDetail objects or dictionaries
		"""
		return cls.dao.fetch(entity=OrderDetail, query=[(key, "==", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value_like(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[OrderDetail, Dict]]:
		"""
		Retrieve order_details by key-value with LIKE operator

		Args:
			key: The field name to search
			value: The value pattern to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return OrderDetail objects; if False, return dictionaries

		Returns:
			Generator yielding OrderDetail objects or dictionaries
		"""
		return cls.dao.fetch(entity=OrderDetail, query=[(key, "like", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def fetch(cls, query: Optional[List[Tuple]]=None, expand: Optional[List[str]]=None, keys: List[str]="*", sort_by: Optional[List[Tuple[str, int]]]=None, reify: bool=True) -> List[Union[OrderDetail, Dict]]:
		"""
		Fetch order_details with custom query, expansion, and sorting

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			sort_by: List of tuples for sorting [('field', 1/-1), ...] (1=asc, -1=desc)
			reify: If True, return OrderDetail objects; if False, return dictionaries

		Returns:
			Generator yielding OrderDetail objects or dictionaries
		"""
		return cls.dao.fetch(entity=OrderDetail, query=query, expand=expand, keys=keys, sort_by=sort_by, reify=reify)

	@classmethod
	def delete(cls, order_detail_id: str, physical_delete: bool = True) -> bool:
		"""
		Delete a order_detail by ID

		Args:
			order_detail_id: The order_detail ID to delete
			physical_delete: If True, permanently delete; if False, soft delete (mark as inactive)

		Returns:
			True if deletion successful, False otherwise
		"""
		hooks.execute_sync(HookPoint.PRE_DELETE, "OrderDetail", data=order_detail_id)
		result = cls.dao.delete(entity=OrderDetail, id=order_detail_id, physical_delete=physical_delete)
		hooks.execute_sync(HookPoint.POST_DELETE, "OrderDetail", data=order_detail_id)
		return result

	@classmethod
	def delete_list(cls, order_detail_ids: List[str], physical_delete: bool = True) -> int:
		"""
		Delete multiple order_details by their IDs

		Args:
			order_detail_ids: List of order_detail IDs to delete
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of order_details deleted
		"""
		return cls.dao.delete_objects_list(
			entity=OrderDetail,
			ids=order_detail_ids,
			physical_deletion=physical_delete
		)

	@classmethod
	def delete_many(cls, query: Optional[List[Tuple]] = None, physical_delete: bool = True) -> int:
		"""
		Delete multiple order_details matching a query

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of order_details deleted
		"""
		return cls.dao.delete_many(entity=OrderDetail, query=query, physical_delete=physical_delete)

	@classmethod
	def delete_all(cls, physical_delete: bool = False) -> int:
		"""
		Delete all order_details (use with caution!)

		Args:
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of order_details deleted
		"""
		return cls.dao.delete_all(entity=OrderDetail, physical_deletion=physical_delete)
