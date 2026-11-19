from data.generic_dao import GenericDAO
from domain.model import Customer


if __name__ == "__main__":

    from domain.customer import Customer

    dao = GenericDAO()  # DBTYPE and DBNAME come from the project's .env, through api.settings

    print(dao.find_by_id(entity=Customer, id="ALFKI"))
