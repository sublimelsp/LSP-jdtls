# LSP-jdtls

This is a helper package that bundles the [Eclipse JDT language server](https://projects.eclipse.org/projects/eclipse.jdt.ls) for you. Zip artifacts can be found on the Releases page.

To use this package, you must have:
- The [LSP](https://packagecontrol.io/packages/LSP) package.
- A Java SDK.
- It's recommended to have `JAVA_HOME` defined in your environment variables. Otherwise, specify `java.home` in the plugin settings.

## Manual Installation

This package is not on packagecontrol.io because it only works on ST4.
To install this package, **download a zip** [release](https://github.com/sublimelsp/LSP-jdtls/releases).
Unzip the release, and put the files in $DATA/Packages/LSP-jdtls.

If you want to make changes to this repository, clone this repo with git,
and run

```bash
bash make.sh
```

to generate an `out/` directory. Symlink this `out/`
directory to $DATA/Packages/LSP-jdtls. e.g.,

```bash
ln -s $(pwd -P)/out $packages/LSP-jdtls
```

Any time you make changes to one of the files, you must re-run `bash make.sh`.

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
