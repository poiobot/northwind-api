from domain.model import Category

from typing import List, Dict, Union, Optional, Any, Tuple
from data.generic_dao import GenericDAO
from lib.hooks import hooks, HookPoint


class CategoryCrudCTL:
	"""
	Category CRUD Controller - Handles CRUD operations for Category entities
	Uses GenericDAO for database-agnostic operations
	"""

	dao = GenericDAO()

	@classmethod
	def create(cls, category: Union[Category, Dict], reify: bool = True) -> Optional[Category]:
		"""
		Register a new category

		Args:
			category: Category object or dictionary with category data
			reify: If True, return Category object; if False, return dictionary

		Returns:
			Created Category object or dictionary, None if creation fails
		"""
		category = hooks.execute_sync(HookPoint.PRE_CREATE, "Category", data=category)
		result = cls.dao.insert(entity=Category, data=category, reify=reify)
		hooks.execute_sync(HookPoint.POST_CREATE, "Category", data=result)
		return result


	@classmethod
	def update(cls, category_id: str, category: Union[Category, Dict], reify: bool = True) -> Optional[Category]:
		"""
		Update an existing category

		Args:
			category_id: The category ID to update
			category: Category object or dictionary with updated data
			reify: If True, return Category object; if False, return dictionary

		Returns:
			Updated Category object or dictionary
		"""
		category = hooks.execute_sync(HookPoint.PRE_UPDATE, "Category", data=category)
		result = cls.dao.update(entity=Category, id=category_id, data=category, reify=reify)
		hooks.execute_sync(HookPoint.POST_UPDATE, "Category", data=result)
		return result

	@classmethod
	def get_by_id(cls, category_id: str, keys: List[str] = "*", expand: Optional[List[str]] = None, reify: bool = True) -> Optional[Category]:
		"""
		Retrieve a category by its ID

		Args:
			category_id: The category ID to search for
			keys: List of fields to retrieve (default: all fields)
			expand: List of reference fields to expand/join
			reify: If True, return Category object; if False, return dictionary

		Returns:
			Category object or dictionary, None if not found
		"""
		result = cls.dao.find_by_id(entity=Category, id=category_id, keys=keys, expand=expand, reify=reify)
		result = hooks.execute_sync(HookPoint.POST_FETCH, "Category", data=result)
		return result

	@classmethod
	def get_list(cls, category_ids: List[str], keys: List[str] = "*", expand: List[str]=None, reify: bool = True) -> List[Union[Category, Dict]]:
		"""
		Retrieve multiple categories by their IDs

		Args:
			category_ids: List of category IDs to retrieve
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Category objects; if False, return dictionaries

		Returns:
			Generator yielding Category objects or dictionaries
		"""
		return cls.dao.find_list(entity=Category, ids=category_ids, keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[Category, Dict]]:
		"""
		Retrieve categories by key-value

		Args:
			key: The field name to search
			value: The value to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Category objects; if False, return dictionaries

		Returns:
			Generator yielding Category objects or dictionaries
		"""
		return cls.dao.fetch(entity=Category, query=[(key, "==", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value_like(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[Category, Dict]]:
		"""
		Retrieve categories by key-value with LIKE operator

		Args:
			key: The field name to search
			value: The value pattern to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Category objects; if False, return dictionaries

		Returns:
			Generator yielding Category objects or dictionaries
		"""
		return cls.dao.fetch(entity=Category, query=[(key, "like", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def fetch(cls, query: Optional[List[Tuple]]=None, expand: Optional[List[str]]=None, keys: List[str]="*", sort_by: Optional[List[Tuple[str, int]]]=None, reify: bool=True) -> List[Union[Category, Dict]]:
		"""
		Fetch categories with custom query, expansion, and sorting

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			sort_by: List of tuples for sorting [('field', 1/-1), ...] (1=asc, -1=desc)
			reify: If True, return Category objects; if False, return dictionaries

		Returns:
			Generator yielding Category objects or dictionaries
		"""
		return cls.dao.fetch(entity=Category, query=query, expand=expand, keys=keys, sort_by=sort_by, reify=reify)

	@classmethod
	def delete(cls, category_id: str, physical_delete: bool = True) -> bool:
		"""
		Delete a category by ID

		Args:
			category_id: The category ID to delete
			physical_delete: If True, permanently delete; if False, soft delete (mark as inactive)

		Returns:
			True if deletion successful, False otherwise
		"""
		hooks.execute_sync(HookPoint.PRE_DELETE, "Category", data=category_id)
		result = cls.dao.delete(entity=Category, id=category_id, physical_delete=physical_delete)
		hooks.execute_sync(HookPoint.POST_DELETE, "Category", data=category_id)
		return result

	@classmethod
	def delete_list(cls, category_ids: List[str], physical_delete: bool = True) -> int:
		"""
		Delete multiple categories by their IDs

		Args:
			category_ids: List of category IDs to delete
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of categorys deleted
		"""
		return cls.dao.delete_objects_list(
			entity=Category,
			ids=category_ids,
			physical_deletion=physical_delete
		)

	@classmethod
	def delete_many(cls, query: Optional[List[Tuple]] = None, physical_delete: bool = True) -> int:
		"""
		Delete multiple categories matching a query

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of categorys deleted
		"""
		return cls.dao.delete_many(entity=Category, query=query, physical_delete=physical_delete)

	@classmethod
	def delete_all(cls, physical_delete: bool = False) -> int:
		"""
		Delete all categories (use with caution!)

		Args:
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of categorys deleted
		"""
		return cls.dao.delete_all(entity=Category, physical_deletion=physical_delete)
