from demo_interface import IDemo

class NumericImpl(IDemo):

    def calculate(self, a: Any, b: Any, op: str) -> Any:
        """
        Makes a calculation between two numbers
        :param a: first number
        :param b: second number
        :param op: name of operation to apply
        :return: Result value
        """
        # Verify the types of the parameters
        match op:
            case "+":
                return a + b
            case "-":
                return a - b
            case "*":
                return a * b
            case "/":
                return a / b
        return None


if __name__ == "__main__":

    print(NumericImpl().calculate(10,20, "-"))