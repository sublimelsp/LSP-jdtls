# fmt: off
LOMBOK_VERSION = "1.18.38"
LOMBOK_URL = "https://repo1.maven.org/maven2/org/projectlombok/lombok/{version}/lombok-{version}.jar"
JDTLS_VERSION = "1.47.0"
JDTLS_TAR_URL_FILE = "https://download.eclipse.org/jdtls/milestones/{version}/latest.txt"
JDTLS_URL = "https://download.eclipse.org/jdtls/milestones/{version}/{tar}"
VSCODE_PLUGINS = {
    "vscode-java-debug": {
        "url": "https://open-vsx.org/api/vscjava/vscode-java-debug/{version}/file/vscjava.vscode-java-debug-{version}.vsix",
        "version": "0.58.2",
        "extension_path": "extension"
    },
    "vscode-java-test": {
        "url": "https://open-vsx.org/api/vscjava/vscode-java-test/{version}/file/vscjava.vscode-java-test-{version}.vsix",
        "version": "0.43.1",
        "extension_path": "extension"
    },
    "vscode-java-decompiler": {  # https://github.com/dgileadi/vscode-java-decompiler/issues/17
        "url": "https://github.com/dgileadi/vscode-java-decompiler/archive/{version}.zip",
        "version": "57691a5fdacbc67a8b606e34fb636fa89687430b",  # 0.0.4
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
