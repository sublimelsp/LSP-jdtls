# LSP-jdtls

This is a helper package that manages and downloads the [Eclipse JDT language server](https://projects.eclipse.org/projects/eclipse.jdt.ls) for you.

To use this package, you must have:

- The [LSP](https://packagecontrol.io/packages/LSP) package.
- A Java SDK.
- It's recommended to have `JAVA_HOME` defined in your environment variables. Otherwise, specify `java.home` in the plugin settings.

## Applicable Selectors

This language server operates on views with the `source.java` base scope.

## Configuration

Configure jdtls by running `Preferences: LSP-jdtls Settings` from the command palette.

## Capabilities

jdtls can do a lot of cool things, like

- code completion
- signature help
- hover info
- code actions
- formatting
- find references
- goto def

## Licenses

The [Java Debug Plugin](https://github.com/microsoft/java-debug) is licensed under [Eclipse Public License 1.0](https://github.com/Microsoft/java-debug/blob/master/LICENSE.txt).
The [Test Runner for Java](https://github.com/microsoft/vscode-java-test) is licensed under [MIT License](https://github.com/microsoft/vscode-java-test/blob/main/LICENSE.txt)
