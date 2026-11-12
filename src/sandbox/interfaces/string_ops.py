from demo_interface import IDemo

class StringImpl(IDemo):

    def calculate(self, a: Any, b: Any, op: str) -> Any:
        """
        Makes a calculation between two numbers
        :param a: first value
        :param b: second value
        :param op: name of operation to apply
        :return: Result value
        """
        # Verify the types of the parameters
        match op:
            case "concat":
                return a + b
            case "concat-upcase":
                return (a + b).upper()
        return None


if __name__ == "__main__":

    print(StringImpl().calculate("Hello","World", "concat-upcase"))