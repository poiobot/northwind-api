from itertools import chain, starmap

class FlattenDict:

    @staticmethod
    def flatten(dictionary, delimiter: str = '.'):
        """Flatten a nested json file"""

        def unpack(parent_key, parent_value, delimiter: str = '.'):
            """Unpack one level of nesting in json file"""
            # Unpack one level only!!!

            if isinstance(parent_value, dict):
                for key, value in parent_value.items():
                    temp1 = parent_key + delimiter + key
                    yield temp1, value
            # elif isinstance(parent_value, list):
            #     i = 0
            #     for value in parent_value:
            #         temp2 = parent_key + delimiter + str(i)
            #         i += 1
            #         yield temp2, value
            else:
                yield parent_key, parent_value

                # Keep iterating until the termination condition is satisfied

        while True:
            # Keep unpacking the json file until all values are atomic elements (not dictionary or list)
            dictionary = dict(chain.from_iterable(starmap(unpack, dictionary.items())))
            # Terminate condition: not any value in the json file is dictionary or list
            if not any(isinstance(value, dict) for value in dictionary.values()):
            # ) and not any(isinstance(value, list) for value in dictionary.values()):
                break

        return dictionary


if __name__ == '__main__':

    d = {
        '_id': 'CHOPS',
        'companyName': 'Chop-suey Chinese',
        'contactName': 'Yang Wang',
        'contactTitle': 'Owner',
        'address': {
            'street': 'Hauptstr. 29',
            'city': 'Bern',
            'region': 'NULL',
            'postalCode': 3012,
            'country': 'Switzerland',
            'phone': '0452-076545'
        }
    }

    print(FlattenDict.flatten(d))
