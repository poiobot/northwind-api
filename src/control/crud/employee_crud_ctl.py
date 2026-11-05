from domain.model import Employee

from typing import List, Dict, Union, Optional, Any, Tuple
from data.generic_dao import GenericDAO
from lib.hooks import hooks, HookPoint


class EmployeeCrudCTL:
	"""
	Employee CRUD Controller - Handles CRUD operations for Employee entities
	Uses GenericDAO for database-agnostic operations
	"""

	dao = GenericDAO()

	@classmethod
	def create(cls, employee: Union[Employee, Dict], reify: bool = True) -> Optional[Employee]:
		"""
		Register a new employee

		Args:
			employee: Employee object or dictionary with employee data
			reify: If True, return Employee object; if False, return dictionary

		Returns:
			Created Employee object or dictionary, None if creation fails
		"""
		employee = hooks.execute_sync(HookPoint.PRE_CREATE, "Employee", data=employee)
		result = cls.dao.insert(entity=Employee, data=employee, reify=reify)
		hooks.execute_sync(HookPoint.POST_CREATE, "Employee", data=result)
		return result


	@classmethod
	def update(cls, employee_id: str, employee: Union[Employee, Dict], reify: bool = True) -> Optional[Employee]:
		"""
		Update an existing employee

		Args:
			employee_id: The employee ID to update
			employee: Employee object or dictionary with updated data
			reify: If True, return Employee object; if False, return dictionary

		Returns:
			Updated Employee object or dictionary
		"""
		employee = hooks.execute_sync(HookPoint.PRE_UPDATE, "Employee", data=employee)
		result = cls.dao.update(entity=Employee, id=employee_id, data=employee, reify=reify)
		hooks.execute_sync(HookPoint.POST_UPDATE, "Employee", data=result)
		return result

	@classmethod
	def get_by_id(cls, employee_id: str, keys: List[str] = "*", expand: Optional[List[str]] = None, reify: bool = True) -> Optional[Employee]:
		"""
		Retrieve a employee by its ID

		Args:
			employee_id: The employee ID to search for
			keys: List of fields to retrieve (default: all fields)
			expand: List of reference fields to expand/join
			reify: If True, return Employee object; if False, return dictionary

		Returns:
			Employee object or dictionary, None if not found
		"""
		result = cls.dao.find_by_id(entity=Employee, id=employee_id, keys=keys, expand=expand, reify=reify)
		result = hooks.execute_sync(HookPoint.POST_FETCH, "Employee", data=result)
		return result

	@classmethod
	def get_list(cls, employee_ids: List[str], keys: List[str] = "*", expand: List[str]=None, reify: bool = True) -> List[Union[Employee, Dict]]:
		"""
		Retrieve multiple employees by their IDs

		Args:
			employee_ids: List of employee IDs to retrieve
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Employee objects; if False, return dictionaries

		Returns:
			Generator yielding Employee objects or dictionaries
		"""
		return cls.dao.find_list(entity=Employee, ids=employee_ids, keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[Employee, Dict]]:
		"""
		Retrieve employees by key-value

		Args:
			key: The field name to search
			value: The value to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Employee objects; if False, return dictionaries

		Returns:
			Generator yielding Employee objects or dictionaries
		"""
		return cls.dao.fetch(entity=Employee, query=[(key, "==", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value_like(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[Employee, Dict]]:
		"""
		Retrieve employees by key-value with LIKE operator

		Args:
			key: The field name to search
			value: The value pattern to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Employee objects; if False, return dictionaries

		Returns:
			Generator yielding Employee objects or dictionaries
		"""
		return cls.dao.fetch(entity=Employee, query=[(key, "like", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def fetch(cls, query: Optional[List[Tuple]]=None, expand: Optional[List[str]]=None, keys: List[str]="*", sort_by: Optional[List[Tuple[str, int]]]=None, reify: bool=True) -> List[Union[Employee, Dict]]:
		"""
		Fetch employees with custom query, expansion, and sorting

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			sort_by: List of tuples for sorting [('field', 1/-1), ...] (1=asc, -1=desc)
			reify: If True, return Employee objects; if False, return dictionaries

		Returns:
			Generator yielding Employee objects or dictionaries
		"""
		return cls.dao.fetch(entity=Employee, query=query, expand=expand, keys=keys, sort_by=sort_by, reify=reify)

	@classmethod
	def delete(cls, employee_id: str, physical_delete: bool = True) -> bool:
		"""
		Delete a employee by ID

		Args:
			employee_id: The employee ID to delete
			physical_delete: If True, permanently delete; if False, soft delete (mark as inactive)

		Returns:
			True if deletion successful, False otherwise
		"""
		hooks.execute_sync(HookPoint.PRE_DELETE, "Employee", data=employee_id)
		result = cls.dao.delete(entity=Employee, id=employee_id, physical_delete=physical_delete)
		hooks.execute_sync(HookPoint.POST_DELETE, "Employee", data=employee_id)
		return result

	@classmethod
	def delete_list(cls, employee_ids: List[str], physical_delete: bool = True) -> int:
		"""
		Delete multiple employees by their IDs

		Args:
			employee_ids: List of employee IDs to delete
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of employees deleted
		"""
		return cls.dao.delete_objects_list(
			entity=Employee,
			ids=employee_ids,
			physical_deletion=physical_delete
		)

	@classmethod
	def delete_many(cls, query: Optional[List[Tuple]] = None, physical_delete: bool = True) -> int:
		"""
		Delete multiple employees matching a query

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of employees deleted
		"""
		return cls.dao.delete_many(entity=Employee, query=query, physical_delete=physical_delete)

	@classmethod
	def delete_all(cls, physical_delete: bool = False) -> int:
		"""
		Delete all employees (use with caution!)

		Args:
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of employees deleted
		"""
		return cls.dao.delete_all(entity=Employee, physical_deletion=physical_delete)
