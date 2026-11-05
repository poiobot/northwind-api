from domain.model import Region

from typing import List, Dict, Union, Optional, Any, Tuple
from data.generic_dao import GenericDAO
from lib.hooks import hooks, HookPoint


class RegionCrudCTL:
	"""
	Region CRUD Controller - Handles CRUD operations for Region entities
	Uses GenericDAO for database-agnostic operations
	"""

	dao = GenericDAO()

	@classmethod
	def create(cls, region: Union[Region, Dict], reify: bool = True) -> Optional[Region]:
		"""
		Register a new region

		Args:
			region: Region object or dictionary with region data
			reify: If True, return Region object; if False, return dictionary

		Returns:
			Created Region object or dictionary, None if creation fails
		"""
		region = hooks.execute_sync(HookPoint.PRE_CREATE, "Region", data=region)
		result = cls.dao.insert(entity=Region, data=region, reify=reify)
		hooks.execute_sync(HookPoint.POST_CREATE, "Region", data=result)
		return result


	@classmethod
	def update(cls, region_id: str, region: Union[Region, Dict], reify: bool = True) -> Optional[Region]:
		"""
		Update an existing region

		Args:
			region_id: The region ID to update
			region: Region object or dictionary with updated data
			reify: If True, return Region object; if False, return dictionary

		Returns:
			Updated Region object or dictionary
		"""
		region = hooks.execute_sync(HookPoint.PRE_UPDATE, "Region", data=region)
		result = cls.dao.update(entity=Region, id=region_id, data=region, reify=reify)
		hooks.execute_sync(HookPoint.POST_UPDATE, "Region", data=result)
		return result

	@classmethod
	def get_by_id(cls, region_id: str, keys: List[str] = "*", expand: Optional[List[str]] = None, reify: bool = True) -> Optional[Region]:
		"""
		Retrieve a region by its ID

		Args:
			region_id: The region ID to search for
			keys: List of fields to retrieve (default: all fields)
			expand: List of reference fields to expand/join
			reify: If True, return Region object; if False, return dictionary

		Returns:
			Region object or dictionary, None if not found
		"""
		result = cls.dao.find_by_id(entity=Region, id=region_id, keys=keys, expand=expand, reify=reify)
		result = hooks.execute_sync(HookPoint.POST_FETCH, "Region", data=result)
		return result

	@classmethod
	def get_list(cls, region_ids: List[str], keys: List[str] = "*", expand: List[str]=None, reify: bool = True) -> List[Union[Region, Dict]]:
		"""
		Retrieve multiple regions by their IDs

		Args:
			region_ids: List of region IDs to retrieve
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Region objects; if False, return dictionaries

		Returns:
			Generator yielding Region objects or dictionaries
		"""
		return cls.dao.find_list(entity=Region, ids=region_ids, keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[Region, Dict]]:
		"""
		Retrieve regions by key-value

		Args:
			key: The field name to search
			value: The value to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Region objects; if False, return dictionaries

		Returns:
			Generator yielding Region objects or dictionaries
		"""
		return cls.dao.fetch(entity=Region, query=[(key, "==", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value_like(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[Region, Dict]]:
		"""
		Retrieve regions by key-value with LIKE operator

		Args:
			key: The field name to search
			value: The value pattern to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Region objects; if False, return dictionaries

		Returns:
			Generator yielding Region objects or dictionaries
		"""
		return cls.dao.fetch(entity=Region, query=[(key, "like", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def fetch(cls, query: Optional[List[Tuple]]=None, expand: Optional[List[str]]=None, keys: List[str]="*", sort_by: Optional[List[Tuple[str, int]]]=None, reify: bool=True) -> List[Union[Region, Dict]]:
		"""
		Fetch regions with custom query, expansion, and sorting

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			sort_by: List of tuples for sorting [('field', 1/-1), ...] (1=asc, -1=desc)
			reify: If True, return Region objects; if False, return dictionaries

		Returns:
			Generator yielding Region objects or dictionaries
		"""
		return cls.dao.fetch(entity=Region, query=query, expand=expand, keys=keys, sort_by=sort_by, reify=reify)

	@classmethod
	def delete(cls, region_id: str, physical_delete: bool = True) -> bool:
		"""
		Delete a region by ID

		Args:
			region_id: The region ID to delete
			physical_delete: If True, permanently delete; if False, soft delete (mark as inactive)

		Returns:
			True if deletion successful, False otherwise
		"""
		hooks.execute_sync(HookPoint.PRE_DELETE, "Region", data=region_id)
		result = cls.dao.delete(entity=Region, id=region_id, physical_delete=physical_delete)
		hooks.execute_sync(HookPoint.POST_DELETE, "Region", data=region_id)
		return result

	@classmethod
	def delete_list(cls, region_ids: List[str], physical_delete: bool = True) -> int:
		"""
		Delete multiple regions by their IDs

		Args:
			region_ids: List of region IDs to delete
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of regions deleted
		"""
		return cls.dao.delete_objects_list(
			entity=Region,
			ids=region_ids,
			physical_deletion=physical_delete
		)

	@classmethod
	def delete_many(cls, query: Optional[List[Tuple]] = None, physical_delete: bool = True) -> int:
		"""
		Delete multiple regions matching a query

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of regions deleted
		"""
		return cls.dao.delete_many(entity=Region, query=query, physical_delete=physical_delete)

	@classmethod
	def delete_all(cls, physical_delete: bool = False) -> int:
		"""
		Delete all regions (use with caution!)

		Args:
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of regions deleted
		"""
		return cls.dao.delete_all(entity=Region, physical_deletion=physical_delete)
