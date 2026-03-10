const path = require("path");

const isWindows = process.platform === "win32";
const homeDir = process.env.USERPROFILE || process.env.HOME || "";
const ghostcamBinary = isWindows
  ? path.join(homeDir, ".local", "bin", "ghostcam.exe")
  : "ghostcam";
const backgroundImage = path.join(
  __dirname,
  "tests",
  "test_background.webp"
);

const args = [
  "--width", "1280",
  "--height", "720",
  "--fps", "30",
  "--background-mode", "color",
  "--background-color", "#ECE8E0",
  "--blur-strength", "21",
];

if (!isWindows) {
  args.unshift("/dev/video0");
  args.unshift("--input");
}

module.exports = {
  apps: [
    {
      name: "ghostcam",
      cwd: __dirname,
      script: ghostcamBinary,
      interpreter: "none",
      args: args.join(" "),
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: "1G",
      env: {
        NODE_ENV: "development",
        PYTHONUNBUFFERED: "1",
      },
      env_production: {
        NODE_ENV: "production",
        PYTHONUNBUFFERED: "1",
      },
    },
  ],
};
