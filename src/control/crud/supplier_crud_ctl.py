from domain.model import Supplier

from typing import List, Dict, Union, Optional, Any, Tuple
from data.generic_dao import GenericDAO
from lib.hooks import hooks, HookPoint


class SupplierCrudCTL:
	"""
	Supplier CRUD Controller - Handles CRUD operations for Supplier entities
	Uses GenericDAO for database-agnostic operations
	"""

	dao = GenericDAO()

	@classmethod
	def create(cls, supplier: Union[Supplier, Dict], reify: bool = True) -> Optional[Supplier]:
		"""
		Register a new supplier

		Args:
			supplier: Supplier object or dictionary with supplier data
			reify: If True, return Supplier object; if False, return dictionary

		Returns:
			Created Supplier object or dictionary, None if creation fails
		"""
		supplier = hooks.execute_sync(HookPoint.PRE_CREATE, "Supplier", data=supplier)
		result = cls.dao.insert(entity=Supplier, data=supplier, reify=reify)
		hooks.execute_sync(HookPoint.POST_CREATE, "Supplier", data=result)
		return result


	@classmethod
	def update(cls, supplier_id: str, supplier: Union[Supplier, Dict], reify: bool = True) -> Optional[Supplier]:
		"""
		Update an existing supplier

		Args:
			supplier_id: The supplier ID to update
			supplier: Supplier object or dictionary with updated data
			reify: If True, return Supplier object; if False, return dictionary

		Returns:
			Updated Supplier object or dictionary
		"""
		supplier = hooks.execute_sync(HookPoint.PRE_UPDATE, "Supplier", data=supplier)
		result = cls.dao.update(entity=Supplier, id=supplier_id, data=supplier, reify=reify)
		hooks.execute_sync(HookPoint.POST_UPDATE, "Supplier", data=result)
		return result

	@classmethod
	def get_by_id(cls, supplier_id: str, keys: List[str] = "*", expand: Optional[List[str]] = None, reify: bool = True) -> Optional[Supplier]:
		"""
		Retrieve a supplier by its ID

		Args:
			supplier_id: The supplier ID to search for
			keys: List of fields to retrieve (default: all fields)
			expand: List of reference fields to expand/join
			reify: If True, return Supplier object; if False, return dictionary

		Returns:
			Supplier object or dictionary, None if not found
		"""
		result = cls.dao.find_by_id(entity=Supplier, id=supplier_id, keys=keys, expand=expand, reify=reify)
		result = hooks.execute_sync(HookPoint.POST_FETCH, "Supplier", data=result)
		return result

	@classmethod
	def get_list(cls, supplier_ids: List[str], keys: List[str] = "*", expand: List[str]=None, reify: bool = True) -> List[Union[Supplier, Dict]]:
		"""
		Retrieve multiple suppliers by their IDs

		Args:
			supplier_ids: List of supplier IDs to retrieve
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Supplier objects; if False, return dictionaries

		Returns:
			Generator yielding Supplier objects or dictionaries
		"""
		return cls.dao.find_list(entity=Supplier, ids=supplier_ids, keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[Supplier, Dict]]:
		"""
		Retrieve suppliers by key-value

		Args:
			key: The field name to search
			value: The value to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Supplier objects; if False, return dictionaries

		Returns:
			Generator yielding Supplier objects or dictionaries
		"""
		return cls.dao.fetch(entity=Supplier, query=[(key, "==", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value_like(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[Supplier, Dict]]:
		"""
		Retrieve suppliers by key-value with LIKE operator

		Args:
			key: The field name to search
			value: The value pattern to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Supplier objects; if False, return dictionaries

		Returns:
			Generator yielding Supplier objects or dictionaries
		"""
		return cls.dao.fetch(entity=Supplier, query=[(key, "like", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def fetch(cls, query: Optional[List[Tuple]]=None, expand: Optional[List[str]]=None, keys: List[str]="*", sort_by: Optional[List[Tuple[str, int]]]=None, reify: bool=True) -> List[Union[Supplier, Dict]]:
		"""
		Fetch suppliers with custom query, expansion, and sorting

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			sort_by: List of tuples for sorting [('field', 1/-1), ...] (1=asc, -1=desc)
			reify: If True, return Supplier objects; if False, return dictionaries

		Returns:
			Generator yielding Supplier objects or dictionaries
		"""
		return cls.dao.fetch(entity=Supplier, query=query, expand=expand, keys=keys, sort_by=sort_by, reify=reify)

	@classmethod
	def delete(cls, supplier_id: str, physical_delete: bool = True) -> bool:
		"""
		Delete a supplier by ID

		Args:
			supplier_id: The supplier ID to delete
			physical_delete: If True, permanently delete; if False, soft delete (mark as inactive)

		Returns:
			True if deletion successful, False otherwise
		"""
		hooks.execute_sync(HookPoint.PRE_DELETE, "Supplier", data=supplier_id)
		result = cls.dao.delete(entity=Supplier, id=supplier_id, physical_delete=physical_delete)
		hooks.execute_sync(HookPoint.POST_DELETE, "Supplier", data=supplier_id)
		return result

	@classmethod
	def delete_list(cls, supplier_ids: List[str], physical_delete: bool = True) -> int:
		"""
		Delete multiple suppliers by their IDs

		Args:
			supplier_ids: List of supplier IDs to delete
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of suppliers deleted
		"""
		return cls.dao.delete_objects_list(
			entity=Supplier,
			ids=supplier_ids,
			physical_deletion=physical_delete
		)

	@classmethod
	def delete_many(cls, query: Optional[List[Tuple]] = None, physical_delete: bool = True) -> int:
		"""
		Delete multiple suppliers matching a query

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of suppliers deleted
		"""
		return cls.dao.delete_many(entity=Supplier, query=query, physical_delete=physical_delete)

	@classmethod
	def delete_all(cls, physical_delete: bool = False) -> int:
		"""
		Delete all suppliers (use with caution!)

		Args:
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of suppliers deleted
		"""
		return cls.dao.delete_all(entity=Supplier, physical_deletion=physical_delete)
