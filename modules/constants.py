# fmt: off
LOMBOK_VERSION = "1.18.24"
LOMBOK_URL = "https://repo1.maven.org/maven2/org/projectlombok/lombok/{version}/lombok-{version}.jar"
JDTLS_VERSION = "1.18.0-202212011747"
JDTLS_URL = "http://download.eclipse.org/jdtls/snapshots/jdt-language-server-{version}.tar.gz"
VSCODE_PLUGINS = [
    {
        "name": "vscode-java-debug",
        "url": "https://github.com/microsoft/vscode-java-debug/releases/download/{version}/vscjava.vscode-java-debug-{version}.vsix",
        "version": "0.47.0"
    },
    {
        "name": "vscode-java-test",
        "url": "https://github.com/microsoft/vscode-java-test/releases/download/{version}/vscjava.vscode-java-test-{version}.vsix",
        "version": "0.37.1"
    }
]
SETTINGS_FILENAME = "LSP-jdtls.sublime-settings"
STORAGE_DIR = "LSP-jdtls"
SESSION_NAME = "jdtls"
INSTALL_DIR = "server"
DATA_DIR = "data"

SETTING_LOMBOK_ENABLED = "java.jdt.ls.lombokSupport.enabled"
SETTING_JAVA_HOME = "java.jdt.ls.java.home"
SETTING_JAVA_HOME_DEPRECATED = "java.home"
SETTING_ENABLE_NULL_ANALYSIS = "java.compile.nullAnalysis.mode"
SETTING_PROGRESS_REPORT_ENABLED = "java.progressReports.enabled"
# fmt: on
