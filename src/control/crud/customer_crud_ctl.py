from domain.model import Customer

from typing import List, Dict, Union, Optional, Any, Tuple
from data.generic_dao import GenericDAO
from lib.hooks import hooks, HookPoint


class CustomerCrudCTL:
	"""
	Customer CRUD Controller - Handles CRUD operations for Customer entities
	Uses GenericDAO for database-agnostic operations
	"""

	dao = GenericDAO()

	@classmethod
	def create(cls, customer: Union[Customer, Dict], reify: bool = True) -> Optional[Customer]:
		"""
		Register a new customer

		Args:
			customer: Customer object or dictionary with customer data
			reify: If True, return Customer object; if False, return dictionary

		Returns:
			Created Customer object or dictionary, None if creation fails
		"""
		customer = hooks.execute_sync(HookPoint.PRE_CREATE, "Customer", data=customer)
		result = cls.dao.insert(entity=Customer, data=customer, reify=reify)
		hooks.execute_sync(HookPoint.POST_CREATE, "Customer", data=result)
		return result


	@classmethod
	def update(cls, customer_id: str, customer: Union[Customer, Dict], reify: bool = True) -> Optional[Customer]:
		"""
		Update an existing customer

		Args:
			customer_id: The customer ID to update
			customer: Customer object or dictionary with updated data
			reify: If True, return Customer object; if False, return dictionary

		Returns:
			Updated Customer object or dictionary
		"""
		customer = hooks.execute_sync(HookPoint.PRE_UPDATE, "Customer", data=customer)
		result = cls.dao.update(entity=Customer, id=customer_id, data=customer, reify=reify)
		hooks.execute_sync(HookPoint.POST_UPDATE, "Customer", data=result)
		return result

	@classmethod
	def get_by_id(cls, customer_id: str, keys: List[str] = "*", expand: Optional[List[str]] = None, reify: bool = True) -> Optional[Customer]:
		"""
		Retrieve a customer by its ID

		Args:
			customer_id: The customer ID to search for
			keys: List of fields to retrieve (default: all fields)
			expand: List of reference fields to expand/join
			reify: If True, return Customer object; if False, return dictionary

		Returns:
			Customer object or dictionary, None if not found
		"""
		result = cls.dao.find_by_id(entity=Customer, id=customer_id, keys=keys, expand=expand, reify=reify)
		result = hooks.execute_sync(HookPoint.POST_FETCH, "Customer", data=result)
		return result

	@classmethod
	def get_list(cls, customer_ids: List[str], keys: List[str] = "*", expand: List[str]=None, reify: bool = True) -> List[Union[Customer, Dict]]:
		"""
		Retrieve multiple customers by their IDs

		Args:
			customer_ids: List of customer IDs to retrieve
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Customer objects; if False, return dictionaries

		Returns:
			Generator yielding Customer objects or dictionaries
		"""
		return cls.dao.find_list(entity=Customer, ids=customer_ids, keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[Customer, Dict]]:
		"""
		Retrieve customers by key-value

		Args:
			key: The field name to search
			value: The value to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Customer objects; if False, return dictionaries

		Returns:
			Generator yielding Customer objects or dictionaries
		"""
		return cls.dao.fetch(entity=Customer, query=[(key, "==", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value_like(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[Customer, Dict]]:
		"""
		Retrieve customers by key-value with LIKE operator

		Args:
			key: The field name to search
			value: The value pattern to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Customer objects; if False, return dictionaries

		Returns:
			Generator yielding Customer objects or dictionaries
		"""
		return cls.dao.fetch(entity=Customer, query=[(key, "like", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def fetch(cls, query: Optional[List[Tuple]]=None, expand: Optional[List[str]]=None, keys: List[str]="*", sort_by: Optional[List[Tuple[str, int]]]=None, reify: bool=True) -> List[Union[Customer, Dict]]:
		"""
		Fetch customers with custom query, expansion, and sorting

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			sort_by: List of tuples for sorting [('field', 1/-1), ...] (1=asc, -1=desc)
			reify: If True, return Customer objects; if False, return dictionaries

		Returns:
			Generator yielding Customer objects or dictionaries
		"""
		return cls.dao.fetch(entity=Customer, query=query, expand=expand, keys=keys, sort_by=sort_by, reify=reify)

	@classmethod
	def delete(cls, customer_id: str, physical_delete: bool = True) -> bool:
		"""
		Delete a customer by ID

		Args:
			customer_id: The customer ID to delete
			physical_delete: If True, permanently delete; if False, soft delete (mark as inactive)

		Returns:
			True if deletion successful, False otherwise
		"""
		hooks.execute_sync(HookPoint.PRE_DELETE, "Customer", data=customer_id)
		result = cls.dao.delete(entity=Customer, id=customer_id, physical_delete=physical_delete)
		hooks.execute_sync(HookPoint.POST_DELETE, "Customer", data=customer_id)
		return result

	@classmethod
	def delete_list(cls, customer_ids: List[str], physical_delete: bool = True) -> int:
		"""
		Delete multiple customers by their IDs

		Args:
			customer_ids: List of customer IDs to delete
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of customers deleted
		"""
		return cls.dao.delete_objects_list(
			entity=Customer,
			ids=customer_ids,
			physical_deletion=physical_delete
		)

	@classmethod
	def delete_many(cls, query: Optional[List[Tuple]] = None, physical_delete: bool = True) -> int:
		"""
		Delete multiple customers matching a query

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of customers deleted
		"""
		return cls.dao.delete_many(entity=Customer, query=query, physical_delete=physical_delete)

	@classmethod
	def delete_all(cls, physical_delete: bool = False) -> int:
		"""
		Delete all customers (use with caution!)

		Args:
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of customers deleted
		"""
		return cls.dao.delete_all(entity=Customer, physical_deletion=physical_delete)
