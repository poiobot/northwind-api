from domain.model import Shipper

from typing import List, Dict, Union, Optional, Any, Tuple
from data.generic_dao import GenericDAO
from lib.hooks import hooks, HookPoint


class ShipperCrudCTL:
	"""
	Shipper CRUD Controller - Handles CRUD operations for Shipper entities
	Uses GenericDAO for database-agnostic operations
	"""

	dao = GenericDAO()

	@classmethod
	def create(cls, shipper: Union[Shipper, Dict], reify: bool = True) -> Optional[Shipper]:
		"""
		Register a new shipper

		Args:
			shipper: Shipper object or dictionary with shipper data
			reify: If True, return Shipper object; if False, return dictionary

		Returns:
			Created Shipper object or dictionary, None if creation fails
		"""
		shipper = hooks.execute_sync(HookPoint.PRE_CREATE, "Shipper", data=shipper)
		result = cls.dao.insert(entity=Shipper, data=shipper, reify=reify)
		hooks.execute_sync(HookPoint.POST_CREATE, "Shipper", data=result)
		return result


	@classmethod
	def update(cls, shipper_id: str, shipper: Union[Shipper, Dict], reify: bool = True) -> Optional[Shipper]:
		"""
		Update an existing shipper

		Args:
			shipper_id: The shipper ID to update
			shipper: Shipper object or dictionary with updated data
			reify: If True, return Shipper object; if False, return dictionary

		Returns:
			Updated Shipper object or dictionary
		"""
		shipper = hooks.execute_sync(HookPoint.PRE_UPDATE, "Shipper", data=shipper)
		result = cls.dao.update(entity=Shipper, id=shipper_id, data=shipper, reify=reify)
		hooks.execute_sync(HookPoint.POST_UPDATE, "Shipper", data=result)
		return result

	@classmethod
	def get_by_id(cls, shipper_id: str, keys: List[str] = "*", expand: Optional[List[str]] = None, reify: bool = True) -> Optional[Shipper]:
		"""
		Retrieve a shipper by its ID

		Args:
			shipper_id: The shipper ID to search for
			keys: List of fields to retrieve (default: all fields)
			expand: List of reference fields to expand/join
			reify: If True, return Shipper object; if False, return dictionary

		Returns:
			Shipper object or dictionary, None if not found
		"""
		result = cls.dao.find_by_id(entity=Shipper, id=shipper_id, keys=keys, expand=expand, reify=reify)
		result = hooks.execute_sync(HookPoint.POST_FETCH, "Shipper", data=result)
		return result

	@classmethod
	def get_list(cls, shipper_ids: List[str], keys: List[str] = "*", expand: List[str]=None, reify: bool = True) -> List[Union[Shipper, Dict]]:
		"""
		Retrieve multiple shippers by their IDs

		Args:
			shipper_ids: List of shipper IDs to retrieve
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Shipper objects; if False, return dictionaries

		Returns:
			Generator yielding Shipper objects or dictionaries
		"""
		return cls.dao.find_list(entity=Shipper, ids=shipper_ids, keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[Shipper, Dict]]:
		"""
		Retrieve shippers by key-value

		Args:
			key: The field name to search
			value: The value to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Shipper objects; if False, return dictionaries

		Returns:
			Generator yielding Shipper objects or dictionaries
		"""
		return cls.dao.fetch(entity=Shipper, query=[(key, "==", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value_like(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[Shipper, Dict]]:
		"""
		Retrieve shippers by key-value with LIKE operator

		Args:
			key: The field name to search
			value: The value pattern to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Shipper objects; if False, return dictionaries

		Returns:
			Generator yielding Shipper objects or dictionaries
		"""
		return cls.dao.fetch(entity=Shipper, query=[(key, "like", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def fetch(cls, query: Optional[List[Tuple]]=None, expand: Optional[List[str]]=None, keys: List[str]="*", sort_by: Optional[List[Tuple[str, int]]]=None, reify: bool=True) -> List[Union[Shipper, Dict]]:
		"""
		Fetch shippers with custom query, expansion, and sorting

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			sort_by: List of tuples for sorting [('field', 1/-1), ...] (1=asc, -1=desc)
			reify: If True, return Shipper objects; if False, return dictionaries

		Returns:
			Generator yielding Shipper objects or dictionaries
		"""
		return cls.dao.fetch(entity=Shipper, query=query, expand=expand, keys=keys, sort_by=sort_by, reify=reify)

	@classmethod
	def delete(cls, shipper_id: str, physical_delete: bool = True) -> bool:
		"""
		Delete a shipper by ID

		Args:
			shipper_id: The shipper ID to delete
			physical_delete: If True, permanently delete; if False, soft delete (mark as inactive)

		Returns:
			True if deletion successful, False otherwise
		"""
		hooks.execute_sync(HookPoint.PRE_DELETE, "Shipper", data=shipper_id)
		result = cls.dao.delete(entity=Shipper, id=shipper_id, physical_delete=physical_delete)
		hooks.execute_sync(HookPoint.POST_DELETE, "Shipper", data=shipper_id)
		return result

	@classmethod
	def delete_list(cls, shipper_ids: List[str], physical_delete: bool = True) -> int:
		"""
		Delete multiple shippers by their IDs

		Args:
			shipper_ids: List of shipper IDs to delete
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of shippers deleted
		"""
		return cls.dao.delete_objects_list(
			entity=Shipper,
			ids=shipper_ids,
			physical_deletion=physical_delete
		)

	@classmethod
	def delete_many(cls, query: Optional[List[Tuple]] = None, physical_delete: bool = True) -> int:
		"""
		Delete multiple shippers matching a query

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of shippers deleted
		"""
		return cls.dao.delete_many(entity=Shipper, query=query, physical_delete=physical_delete)

	@classmethod
	def delete_all(cls, physical_delete: bool = False) -> int:
		"""
		Delete all shippers (use with caution!)

		Args:
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of shippers deleted
		"""
		return cls.dao.delete_all(entity=Shipper, physical_deletion=physical_delete)
