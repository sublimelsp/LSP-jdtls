package example;

import static org.testng.Assert.assertEquals;

import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

public class CalculatorTest {
    private final Calculator calculator = new Calculator();

    @Test
    public void addPasses() {
        assertEquals(calculator.add(1, 2), 3);
    }

    @Test
    public void addFails() {
        assertEquals(calculator.add(1, 2), 4, "deliberate failure");
    }

    @DataProvider
    public Object[][] sums() {
        return new Object[][] {{1, 1, 2}, {2, 3, 5}, {-1, 1, 0}};
    }

    @Test(dataProvider = "sums")
    public void addParameterized(int a, int b, int expected) {
        assertEquals(calculator.add(a, b), expected);
    }

    @Test(expectedExceptions = ArithmeticException.class)
    public void divideByZeroThrows() {
        calculator.divide(1, 0);
    }
}
