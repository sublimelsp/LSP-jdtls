package example;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class CalculatorTest {
    private final Calculator calculator = new Calculator();

    @Test
    void addPasses() {
        assertEquals(3, calculator.add(1, 2));
    }

    @Test
    void addFails() {
        assertEquals(4, calculator.add(1, 2), "deliberate failure");
    }

    @ParameterizedTest
    @CsvSource({"1, 1, 2", "2, 3, 5", "-1, 1, 0"})
    void addParameterized(int a, int b, int expected) {
        assertEquals(expected, calculator.add(a, b));
    }

    @Nested
    @DisplayName("divide")
    class Divide {
        @Test
        void dividesEvenly() {
            assertEquals(2, calculator.divide(4, 2));
        }

        @Test
        void divideByZeroThrows() {
            assertThrows(ArithmeticException.class, () -> calculator.divide(1, 0));
        }
    }
}
