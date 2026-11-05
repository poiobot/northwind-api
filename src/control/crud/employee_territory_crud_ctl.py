from domain.model import EmployeeTerritory

from typing import List, Dict, Union, Optional, Any, Tuple
from data.generic_dao import GenericDAO
from lib.hooks import hooks, HookPoint


class EmployeeTerritoryCrudCTL:
	"""
	EmployeeTerritory CRUD Controller - Handles CRUD operations for EmployeeTerritory entities
	Uses GenericDAO for database-agnostic operations
	"""

	dao = GenericDAO()

	@classmethod
	def create(cls, employee_territory: Union[EmployeeTerritory, Dict], reify: bool = True) -> Optional[EmployeeTerritory]:
		"""
		Register a new employee_territory

		Args:
			employee_territory: EmployeeTerritory object or dictionary with employee_territory data
			reify: If True, return EmployeeTerritory object; if False, return dictionary

		Returns:
			Created EmployeeTerritory object or dictionary, None if creation fails
		"""
		employee_territory = hooks.execute_sync(HookPoint.PRE_CREATE, "EmployeeTerritory", data=employee_territory)
		result = cls.dao.insert(entity=EmployeeTerritory, data=employee_territory, reify=reify)
		hooks.execute_sync(HookPoint.POST_CREATE, "EmployeeTerritory", data=result)
		return result


	@classmethod
	def update(cls, employee_territory_id: str, employee_territory: Union[EmployeeTerritory, Dict], reify: bool = True) -> Optional[EmployeeTerritory]:
		"""
		Update an existing employee_territory

		Args:
			employee_territory_id: The employee_territory ID to update
			employee_territory: EmployeeTerritory object or dictionary with updated data
			reify: If True, return EmployeeTerritory object; if False, return dictionary

		Returns:
			Updated EmployeeTerritory object or dictionary
		"""
		employee_territory = hooks.execute_sync(HookPoint.PRE_UPDATE, "EmployeeTerritory", data=employee_territory)
		result = cls.dao.update(entity=EmployeeTerritory, id=employee_territory_id, data=employee_territory, reify=reify)
		hooks.execute_sync(HookPoint.POST_UPDATE, "EmployeeTerritory", data=result)
		return result

	@classmethod
	def get_by_id(cls, employee_territory_id: str, keys: List[str] = "*", expand: Optional[List[str]] = None, reify: bool = True) -> Optional[EmployeeTerritory]:
		"""
		Retrieve a employee_territory by its ID

		Args:
			employee_territory_id: The employee_territory ID to search for
			keys: List of fields to retrieve (default: all fields)
			expand: List of reference fields to expand/join
			reify: If True, return EmployeeTerritory object; if False, return dictionary

		Returns:
			EmployeeTerritory object or dictionary, None if not found
		"""
		result = cls.dao.find_by_id(entity=EmployeeTerritory, id=employee_territory_id, keys=keys, expand=expand, reify=reify)
		result = hooks.execute_sync(HookPoint.POST_FETCH, "EmployeeTerritory", data=result)
		return result

	@classmethod
	def get_list(cls, employee_territory_ids: List[str], keys: List[str] = "*", expand: List[str]=None, reify: bool = True) -> List[Union[EmployeeTerritory, Dict]]:
		"""
		Retrieve multiple employee_territories by their IDs

		Args:
			employee_territory_ids: List of employee_territory IDs to retrieve
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return EmployeeTerritory objects; if False, return dictionaries

		Returns:
			Generator yielding EmployeeTerritory objects or dictionaries
		"""
		return cls.dao.find_list(entity=EmployeeTerritory, ids=employee_territory_ids, keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[EmployeeTerritory, Dict]]:
		"""
		Retrieve employee_territories by key-value

		Args:
			key: The field name to search
			value: The value to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return EmployeeTerritory objects; if False, return dictionaries

		Returns:
			Generator yielding EmployeeTerritory objects or dictionaries
		"""
		return cls.dao.fetch(entity=EmployeeTerritory, query=[(key, "==", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value_like(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[EmployeeTerritory, Dict]]:
		"""
		Retrieve employee_territories by key-value with LIKE operator

		Args:
			key: The field name to search
			value: The value pattern to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return EmployeeTerritory objects; if False, return dictionaries

		Returns:
			Generator yielding EmployeeTerritory objects or dictionaries
		"""
		return cls.dao.fetch(entity=EmployeeTerritory, query=[(key, "like", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def fetch(cls, query: Optional[List[Tuple]]=None, expand: Optional[List[str]]=None, keys: List[str]="*", sort_by: Optional[List[Tuple[str, int]]]=None, reify: bool=True) -> List[Union[EmployeeTerritory, Dict]]:
		"""
		Fetch employee_territories with custom query, expansion, and sorting

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			sort_by: List of tuples for sorting [('field', 1/-1), ...] (1=asc, -1=desc)
			reify: If True, return EmployeeTerritory objects; if False, return dictionaries

		Returns:
			Generator yielding EmployeeTerritory objects or dictionaries
		"""
		return cls.dao.fetch(entity=EmployeeTerritory, query=query, expand=expand, keys=keys, sort_by=sort_by, reify=reify)

	@classmethod
	def delete(cls, employee_territory_id: str, physical_delete: bool = True) -> bool:
		"""
		Delete a employee_territory by ID

		Args:
			employee_territory_id: The employee_territory ID to delete
			physical_delete: If True, permanently delete; if False, soft delete (mark as inactive)

		Returns:
			True if deletion successful, False otherwise
		"""
		hooks.execute_sync(HookPoint.PRE_DELETE, "EmployeeTerritory", data=employee_territory_id)
		result = cls.dao.delete(entity=EmployeeTerritory, id=employee_territory_id, physical_delete=physical_delete)
		hooks.execute_sync(HookPoint.POST_DELETE, "EmployeeTerritory", data=employee_territory_id)
		return result

	@classmethod
	def delete_list(cls, employee_territory_ids: List[str], physical_delete: bool = True) -> int:
		"""
		Delete multiple employee_territories by their IDs

		Args:
			employee_territory_ids: List of employee_territory IDs to delete
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of employee_territorys deleted
		"""
		return cls.dao.delete_objects_list(
			entity=EmployeeTerritory,
			ids=employee_territory_ids,
			physical_deletion=physical_delete
		)

	@classmethod
	def delete_many(cls, query: Optional[List[Tuple]] = None, physical_delete: bool = True) -> int:
		"""
		Delete multiple employee_territories matching a query

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of employee_territorys deleted
		"""
		return cls.dao.delete_many(entity=EmployeeTerritory, query=query, physical_delete=physical_delete)

	@classmethod
	def delete_all(cls, physical_delete: bool = False) -> int:
		"""
		Delete all employee_territories (use with caution!)

		Args:
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of employee_territorys deleted
		"""
		return cls.dao.delete_all(entity=EmployeeTerritory, physical_deletion=physical_delete)
