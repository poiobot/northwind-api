from domain.model import Product

from typing import List, Dict, Union, Optional, Any, Tuple
from data.generic_dao import GenericDAO
from lib.hooks import hooks, HookPoint


class ProductCrudCTL:
	"""
	Product CRUD Controller - Handles CRUD operations for Product entities
	Uses GenericDAO for database-agnostic operations
	"""

	dao = GenericDAO()

	@classmethod
	def create(cls, product: Union[Product, Dict], reify: bool = True) -> Optional[Product]:
		"""
		Register a new product

		Args:
			product: Product object or dictionary with product data
			reify: If True, return Product object; if False, return dictionary

		Returns:
			Created Product object or dictionary, None if creation fails
		"""
		product = hooks.execute_sync(HookPoint.PRE_CREATE, "Product", data=product)
		result = cls.dao.insert(entity=Product, data=product, reify=reify)
		hooks.execute_sync(HookPoint.POST_CREATE, "Product", data=result)
		return result


	@classmethod
	def update(cls, product_id: str, product: Union[Product, Dict], reify: bool = True) -> Optional[Product]:
		"""
		Update an existing product

		Args:
			product_id: The product ID to update
			product: Product object or dictionary with updated data
			reify: If True, return Product object; if False, return dictionary

		Returns:
			Updated Product object or dictionary
		"""
		product = hooks.execute_sync(HookPoint.PRE_UPDATE, "Product", data=product)
		result = cls.dao.update(entity=Product, id=product_id, data=product, reify=reify)
		hooks.execute_sync(HookPoint.POST_UPDATE, "Product", data=result)
		return result

	@classmethod
	def get_by_id(cls, product_id: str, keys: List[str] = "*", expand: Optional[List[str]] = None, reify: bool = True) -> Optional[Product]:
		"""
		Retrieve a product by its ID

		Args:
			product_id: The product ID to search for
			keys: List of fields to retrieve (default: all fields)
			expand: List of reference fields to expand/join
			reify: If True, return Product object; if False, return dictionary

		Returns:
			Product object or dictionary, None if not found
		"""
		result = cls.dao.find_by_id(entity=Product, id=product_id, keys=keys, expand=expand, reify=reify)
		result = hooks.execute_sync(HookPoint.POST_FETCH, "Product", data=result)
		return result

	@classmethod
	def get_list(cls, product_ids: List[str], keys: List[str] = "*", expand: List[str]=None, reify: bool = True) -> List[Union[Product, Dict]]:
		"""
		Retrieve multiple products by their IDs

		Args:
			product_ids: List of product IDs to retrieve
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Product objects; if False, return dictionaries

		Returns:
			Generator yielding Product objects or dictionaries
		"""
		return cls.dao.find_list(entity=Product, ids=product_ids, keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[Product, Dict]]:
		"""
		Retrieve products by key-value

		Args:
			key: The field name to search
			value: The value to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Product objects; if False, return dictionaries

		Returns:
			Generator yielding Product objects or dictionaries
		"""
		return cls.dao.fetch(entity=Product, query=[(key, "==", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def get_by_key_value_like(cls, key: str, value: Any, keys: List[str]="*", expand: List[str] = None, reify: bool=True) -> List[Union[Product, Dict]]:
		"""
		Retrieve products by key-value with LIKE operator

		Args:
			key: The field name to search
			value: The value pattern to match
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			reify: If True, return Product objects; if False, return dictionaries

		Returns:
			Generator yielding Product objects or dictionaries
		"""
		return cls.dao.fetch(entity=Product, query=[(key, "like", value)], keys=keys, expand=expand, reify=reify)

	@classmethod
	def fetch(cls, query: Optional[List[Tuple]]=None, expand: Optional[List[str]]=None, keys: List[str]="*", sort_by: Optional[List[Tuple[str, int]]]=None, reify: bool=True) -> List[Union[Product, Dict]]:
		"""
		Fetch products with custom query, expansion, and sorting

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			expand: List of reference fields to expand/join
			keys: List of fields to retrieve (default: all fields)
			sort_by: List of tuples for sorting [('field', 1/-1), ...] (1=asc, -1=desc)
			reify: If True, return Product objects; if False, return dictionaries

		Returns:
			Generator yielding Product objects or dictionaries
		"""
		return cls.dao.fetch(entity=Product, query=query, expand=expand, keys=keys, sort_by=sort_by, reify=reify)

	@classmethod
	def delete(cls, product_id: str, physical_delete: bool = True) -> bool:
		"""
		Delete a product by ID

		Args:
			product_id: The product ID to delete
			physical_delete: If True, permanently delete; if False, soft delete (mark as inactive)

		Returns:
			True if deletion successful, False otherwise
		"""
		hooks.execute_sync(HookPoint.PRE_DELETE, "Product", data=product_id)
		result = cls.dao.delete(entity=Product, id=product_id, physical_delete=physical_delete)
		hooks.execute_sync(HookPoint.POST_DELETE, "Product", data=product_id)
		return result

	@classmethod
	def delete_list(cls, product_ids: List[str], physical_delete: bool = True) -> int:
		"""
		Delete multiple products by their IDs

		Args:
			product_ids: List of product IDs to delete
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of products deleted
		"""
		return cls.dao.delete_objects_list(
			entity=Product,
			ids=product_ids,
			physical_deletion=physical_delete
		)

	@classmethod
	def delete_many(cls, query: Optional[List[Tuple]] = None, physical_delete: bool = True) -> int:
		"""
		Delete multiple products matching a query

		Args:
			query: List of tuples with query conditions [('key', 'operator', 'value'), ...]
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of products deleted
		"""
		return cls.dao.delete_many(entity=Product, query=query, physical_delete=physical_delete)

	@classmethod
	def delete_all(cls, physical_delete: bool = False) -> int:
		"""
		Delete all products (use with caution!)

		Args:
			physical_delete: If True, permanently delete; if False, soft delete

		Returns:
			Number of products deleted
		"""
		return cls.dao.delete_all(entity=Product, physical_deletion=physical_delete)
