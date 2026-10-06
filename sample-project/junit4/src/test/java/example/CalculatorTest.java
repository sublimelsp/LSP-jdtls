package example;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class CalculatorTest {
    private final Calculator calculator = new Calculator();

    @Test
    public void addPasses() {
        assertEquals(3, calculator.add(1, 2));
    }

    @Test
    public void addFails() {
        assertEquals("deliberate failure", 4, calculator.add(1, 2));
    }

    @Test(expected = ArithmeticException.class)
    public void divideByZeroThrows() {
        calculator.divide(1, 0);
    }
}
