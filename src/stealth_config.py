"""
Stealth configuration to bypass LinkedIn bot detection.
Patches browser fingerprints, WebDriver flags, and navigator properties.
"""

STEALTH_JS = """
// ========== Override navigator.webdriver ==========
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// ========== Override navigator.languages ==========
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en', 'es']
});

// ========== Override navigator.plugins ==========
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            {
                0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                description: "Portable Document Format",
                filename: "internal-pdf-viewer",
                length: 1,
                name: "Chrome PDF Plugin"
            },
            {
                0: {type: "application/pdf", suffixes: "pdf", description: ""},
                description: "",
                filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                length: 1,
                name: "Chrome PDF Viewer"
            },
            {
                0: {type: "application/x-nacl", suffixes: "", description: "Native Client Executable"},
                1: {type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable"},
                description: "",
                filename: "internal-nacl-plugin",
                length: 2,
                name: "Native Client"
            }
        ];
        return Object.create(PluginArray.prototype, {
            length: { value: plugins.length },
            item: { value: (index) => plugins[index] || null },
            namedItem: { value: (name) => plugins.find(p => p.name === name) || null },
            refresh: { value: () => {} },
            ...Object.fromEntries(plugins.map((p, i) => [i, {value: p}]))
        });
    }
});

// ========== Override navigator.platform ==========
Object.defineProperty(navigator, 'platform', {
    get: () => 'Win32'
});

// ========== Override navigator.hardwareConcurrency ==========
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8
});

// ========== Override navigator.deviceMemory ==========
Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8
});

// ========== Fix Chrome runtime ==========
window.chrome = {
    runtime: {
        PlatformOs: {MAC: 'mac', WIN: 'win', ANDROID: 'android', CROS: 'cros', LINUX: 'linux', OPENBSD: 'openbsd'},
        PlatformArch: {ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64', MIPS: 'mips', MIPS64: 'mips64'},
        PlatformNaclArch: {ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64', MIPS: 'mips', MIPS64: 'mips64'},
        RequestUpdateCheckStatus: {THROTTLED: 'throttled', NO_UPDATE: 'no_update', UPDATE_AVAILABLE: 'update_available'},
        OnInstalledReason: {INSTALL: 'install', UPDATE: 'update', CHROME_UPDATE: 'chrome_update', SHARED_MODULE_UPDATE: 'shared_module_update'},
        OnRestartRequiredReason: {APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic'},
    },
    loadTimes: function() { return {} },
    csi: function() { return {} },
    app: {
        isInstalled: false,
        InstallState: {INSTALLED: 'installed', NOT_INSTALLED: 'not_installed', DISABLED: 'disabled'},
        RunningState: {RUNNING: 'running', CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run'},
        getDetails: function() { return null },
        getIsInstalled: function() { return false },
    }
};

// ========== Fix permissions query ==========
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// ========== Override WebGL Renderer ==========
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) {
        return 'Intel Inc.';
    }
    if (parameter === 37446) {
        return 'Intel Iris OpenGL Engine';
    }
    return getParameter.apply(this, arguments);
};

// ========== Remove automation indicators ==========
delete window.__playwright;
delete window.__pw_manual;
delete window.__PW_inspect;

// ========== Override toString for modified functions ==========
const nativeToStringFunctionString = Error.toString().replace(/Error/g, "toString");
const oldToString = Function.prototype.toString;
function newToString() {
    if (this === window.navigator.permissions.query) {
        return "function query() { [native code] }";
    }
    return oldToString.call(this);
}
Object.defineProperty(Function.prototype, "toString", {
    value: newToString,
    writable: true,
    configurable: true
});

// ========== Prevent iframe detection ==========
Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
    get: function() {
        return window;
    }
});

// ========== Spoof screen properties ==========
Object.defineProperty(screen, 'width', { get: () => 1920 });
Object.defineProperty(screen, 'height', { get: () => 1080 });
Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
Object.defineProperty(screen, 'availHeight', { get: () => 1040 });
Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
Object.defineProperty(screen, 'pixelDepth', { get: () => 24 });

// ========== Spoof connection info ==========
Object.defineProperty(navigator, 'connection', {
    get: () => ({
        effectiveType: '4g',
        rtt: 50,
        downlink: 10,
        saveData: false
    })
});

console.log('Stealth patches applied successfully.');
"""