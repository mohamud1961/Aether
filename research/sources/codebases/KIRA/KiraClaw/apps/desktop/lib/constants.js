const os = require("os");
const path = require("path");
const { app } = require("electron");

const DESKTOP_ROOT = path.resolve(__dirname, "..");
const IS_PACKAGED = app.isPackaged;
const USER_DATA_DIR = app.getPath("userData");
const APP_ROOT = IS_PACKAGED
  ? path.join(process.resourcesPath, "kiraclaw")
  : path.resolve(DESKTOP_ROOT, "..", "..");
const CONFIG_DIR = path.join(os.homedir(), ".kira");
const CONFIG_FILE = path.join(CONFIG_DIR, "config.env");
const RUNTIME_ENV_DIR = path.join(USER_DATA_DIR, "runtime-env");
const RUNTIME_STATE_FILE = path.join(USER_DATA_DIR, "runtime-state.json");
const VENV_BIN_DIR = process.platform === "win32" ? "Scripts" : "bin";
const DAEMON_BIN_NAME = process.platform === "win32" ? "kiraclaw-agentd.exe" : "kiraclaw-agentd";
const DAEMON_BIN = path.join(APP_ROOT, ".venv", VENV_BIN_DIR, DAEMON_BIN_NAME);
const DAEMON_PORT = 8787;
const DAEMON_URL = `http://127.0.0.1:${DAEMON_PORT}`;

module.exports = {
  APP_ROOT,
  CONFIG_DIR,
  CONFIG_FILE,
  DAEMON_BIN,
  DAEMON_URL,
  DESKTOP_ROOT,
  IS_PACKAGED,
  RUNTIME_ENV_DIR,
  RUNTIME_STATE_FILE,
  USER_DATA_DIR,
};
