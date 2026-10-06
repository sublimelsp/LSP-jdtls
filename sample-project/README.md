# jdtls-test-sample

Sample Maven project for manually testing LSP-jdtls test commands
(`LSP-jdtls: Run Test Class`, `Run Test at Cursor`, `Run Test`, `Goto Test`, `Generate Tests`).

Each module uses a different framework so every `TestKind` code path is covered:

| Module   | Framework      | TestKind |
|----------|----------------|----------|
| `junit4` | JUnit 4.13.2   | JUnit    |
| `junit5` | JUnit 5.14.4   | JUnit5   |
| `junit6` | JUnit 6.1.3    | JUnit6   |
| `testng` | TestNG 7.12.0  | TestNG   |

Every test class has one passing test, one deliberately failing test (`addFails`),
and an expected-exception test; JUnit 5/6 and TestNG also have parameterized tests,
and JUnit 5/6 have a `@Nested` class.

Running tests requires the Sublime Debugger package.

Sanity check from the command line (expect 4 failures, one `addFails` per module):

```
mvn test -fae
```
