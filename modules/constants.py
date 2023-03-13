# fmt: off
LOMBOK_VERSION = "1.18.26"
LOMBOK_URL = "https://repo1.maven.org/maven2/org/projectlombok/lombok/{version}/lombok-{version}.jar"
JDTLS_VERSION = "1.20.0-202302201605"
JDTLS_URL = "http://download.eclipse.org/jdtls/snapshots/jdt-language-server-{version}.tar.gz"
VSCODE_PLUGINS = {
    "vscode-java-debug": {
        "url": "https://github.com/microsoft/vscode-java-debug/releases/download/{version}/vscjava.vscode-java-debug-{version}.vsix",
        "version": "0.49.0",
        "extension_path": "extension"
    },
    "vscode-java-test": {
        "url": "https://github.com/microsoft/vscode-java-test/releases/download/{version}/vscjava.vscode-java-test-{version}.vsix",
        "version": "0.38.1",
        "extension_path": "extension"
    },
    "vscode-java-decompiler": {
        "url": "https://github.com/dgileadi/vscode-java-decompiler/archive/{version}.zip",
        "version": "5eaf2fcf73ba6763f1eba69047f631fba80f9a50",
        "extension_path": "vscode-java-decompiler-{version}"
    }
}
DATA_DIR = "data"
INSTALL_DIR = "server"
SESSION_NAME = "jdtls"
SETTINGS_FILENAME = "LSP-jdtls.sublime-settings"
STORAGE_DIR = "LSP-jdtls"

SETTING_ENABLE_NULL_ANALYSIS = "java.compile.nullAnalysis.mode"
SETTING_JAVA_HOME = "java.jdt.ls.java.home"
SETTING_JAVA_HOME_DEPRECATED = "java.home"
SETTING_LOMBOK_ENABLED = "java.jdt.ls.lombokSupport.enabled"
SETTING_PROGRESS_REPORT_ENABLED = "java.progressReports.enabled"

JDTLS_CONFIG_TO_SUBLIME_SETTING = {
    "java.format.tabSize": "tab_size",
    "java.format.insertSpaces": "translate_tabs_to_spaces"
}
""" Config dict for workspace/configuration requests. """

# fmt: on
