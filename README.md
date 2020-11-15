# LSP-jdtls

This is a helper package that bundles the [Eclipse JDT language server](https://projects.eclipse.org/projects/eclipse.jdt.ls) for you. Zip artifacts can be found on the Releases page.

To use this package, you must have:
- The [LSP](https://packagecontrol.io/packages/LSP) package.
- A Java SDK.
- It's recommended to have `JAVA_HOME` defined in your environment variables. Otherwise, specify `java.home` in the plugin settings.

## Applicable Selectors

This language server operates on views with the `source.java` base scope.

## Configuration

Configure jdtls by running `Preferences: LSP-jdtls Settings` from the command palette.

## Quirks

- The language server expects the client (this package) to handle workspace edits. See [this issue](https://github.com/eclipse/eclipse.jdt.ls/issues/376) and [this comment](https://github.com/eclipse/eclipse.jdt.ls/pull/1278#issuecomment-559452278) for more information. TODO: Handle `java.apply.workspaceEdit`.
- The language server currently throws an error for various calls to textDocument/codeAction in the case that we ask for "diagnostic-less" code actions under the caret, but it doesn't seem harmful.

This package

## Capabilities

jdtls can do a lot of cool things, like

- code completion
- signature help
- hover info
- code actions
- formatting
- find references
- goto def
