from services.database.dao_interface import IDatabaseService, DAOInterface
from services.database.impl.mongo_dao import MongoDAO
from services.database.impl.sqlalchemy_dao import SqlAlchemyDAO


class DatabaseConnectionManager(IDatabaseService):

    def connect(self, dbtype: str, dbname: str, **credentials) -> DAOInterface:
        match dbtype.lower():
            case 'mongo' | 'mongodb':
                return MongoDAO(dbname=dbname, credentials=credentials)
            case 'sqlite' | 'sqlite3':
                return SqlAlchemyDAO(dbname=dbname, dbtype=dbtype, **credentials)
            # case 'oracle':
            #     return OracleDAO(...)


if __name__ == "__main__":

    # from domain.customer import Customer

    dao = DatabaseConnectionManager().connect(dbtype="sqlite", dbname="../../../database/sqlite/northwind.db")
    # dao = DatabaseConnectionManager().connect(dbtype="mongodb", dbname="northwind")

    print(dao.describe())
    customers = dao.fetch(table="Customers")
    print(*customers)

