# LSP-jdtls

This is a helper package that manages and downloads the [Eclipse JDT language server](https://projects.eclipse.org/projects/eclipse.jdt.ls) for you.

To use this package, you must have:

- The [LSP](https://packagecontrol.io/packages/LSP) package.
- A Java SDK (>= 17).
- It's recommended to have `JAVA_HOME` defined in your environment variables. Otherwise, specify `java.home` in the plugin settings.


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

## Commands

| Sublime Command               | Description                                           | Command Palette                                       | Note       |
|-------------------------------|-------------------------------------------------------|-------------------------------------------------------|------------|
| lsp_jdtls_build_workspace     | Builds the project                                    | LSP-jdtls: Build Workspace                            | |
| lsp_jdtls_refresh_workspace   | Refreshes all files                                   | LSP-jdtls: Refresh Workspace                          | |
| lsp_jdtls_generate_tests      | Generate a test method in the associated test class   | LSP-jdtls: Generate tests...                          | |
| lsp_jdtls_goto_test           | Jump to test and implementation                       | LSP-jdtls: Goto Test / LSP-jdtls: Goto Implementation | |
| lsp_jdtls_run_test_class      | Runs the test class in the active view                | LSP-jdtls: Run Test Class                             | _(experimental)_ Requires [Debugger](https://github.com/daveleroy/sublime_debugger)|
| lsp_jdtls_run_test_at_cursor  | Runs the test at the first cursor                     | LSP-jdtls: Run Test At Cursor                         | _(experimental)_ Requires [Debugger](https://github.com/daveleroy/sublime_debugger)|
| lsp_jdtls_run_test            | Opens a panel to run a test in the active view        | LSP-jdtls: Run Test...                                | _(experimental)_ Requires [Debugger](https://github.com/daveleroy/sublime_debugger)|
| jdtls_clear_data              | Clears the server data directory                      | LSP-jdtls: Clear jdtls_clear_data                     | |

## Troubleshoot

### Server exits with code `13`
The server caches workspace specific information. When this data is corrupted the server crashes with exit code `13` and the server is disabled for the current project.

Run the command `LSP-jdtls: Clear data` from the command palette and re-enable the server using the command `LSP: Enable Language Server in Project`.

## Licenses

- The [Java Debug Plugin](https://github.com/microsoft/java-debug) is licensed under [Eclipse Public License 1.0](https://github.com/Microsoft/java-debug/blob/master/LICENSE.txt).
- The [Test Runner for Java](https://github.com/microsoft/vscode-java-test) is licensed under [MIT License](https://github.com/microsoft/vscode-java-test/blob/main/LICENSE.txt)
