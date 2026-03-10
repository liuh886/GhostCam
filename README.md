# GhostCam

GhostCam is a headless virtual camera service that reads a physical camera, applies AI segmentation, composites a new background, and publishes the result to a virtual camera such as UnityCapture.

## Features

- Headless pipeline with no GUI requirement
- Background modes: `image`, `color`, `blur`
- Windows-friendly PM2 startup
- PowerShell helper script for start/stop/setup
- Edge darkening to reduce bright halo around hair and shoulders

## Important Limitation

On Windows with the current `pyvirtualcam` + `unitycapture` backend, GhostCam cannot reliably detect whether another app is actively consuming the virtual camera stream. That means the service may keep the physical camera open while it is running. If you want to fully restore the default camera, stop GhostCam first.

## Windows Setup

Install the UnityCapture driver if you have not already:

1. Open [`drivers/UnityCapture/Install/Install.bat`](/D:/Documents/GitHub/GhostCam/drivers/UnityCapture/Install/Install.bat) as Administrator.
2. Confirm that a virtual camera such as `Unity Video Capture` appears in meeting apps.

## Installation

### pipx

```powershell
pipx install .
```

Update an existing install:

```powershell
pipx install --force .
```

### Manual venv

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
```

## Start Methods

### 1. Direct CLI

Recommended when you want to test parameters quickly.

```powershell
ghostcam --input "video=Integrated Camera" --width 1280 --height 720 --fps 30 --background-mode image --background-image tests\test_background.webp
```

### 2. PM2 Service

The default PM2 config is in [ecosystem.config.js](/D:/Documents/GitHub/GhostCam/ecosystem.config.js). It currently starts GhostCam with:

- `--background-mode color`
- `--background-color #ECE8E0`
- `--blur-strength 21`

Start:

```powershell
pm2 start ecosystem.config.js
```

View logs:

```powershell
pm2 logs ghostcam
```

Stop:

```powershell
pm2 stop ghostcam
pm2 delete ghostcam
```

### 3. Windows Helper Script

Use [GhostCam.ps1](/D:/Documents/GitHub/GhostCam/GhostCam.ps1) for local control:

```powershell
powershell -ExecutionPolicy Bypass -File .\GhostCam.ps1 start
```

Stop GhostCam and restore the default camera path:

```powershell
powershell -ExecutionPolicy Bypass -File .\GhostCam.ps1 stop
```

Setup the local venv:

```powershell
powershell -ExecutionPolicy Bypass -File .\GhostCam.ps1 setup
```

## Parameters

### Core

- `--input`: physical camera name/path. Windows example: `video=Integrated Camera`
- `--width`: output width
- `--height`: output height
- `--fps`: output frame rate

### Background

- `--background-mode`: one of `image`, `color`, `blur`
- `--background-image`: path to the replacement image
- `--background-color`: solid background color in hex, for example `#222222`
- `--blur-strength`: odd blur kernel size; higher means stronger blur

Examples:

```powershell
ghostcam --input "video=Integrated Camera" --background-mode image --background-image tests\test_background.webp
```

```powershell
ghostcam --input "video=Integrated Camera" --background-mode color --background-color "#111111"
```

```powershell
ghostcam --input "video=Integrated Camera" --background-mode blur --blur-strength 31
```

## Restore Default Camera

If `Integrated Camera` does not come back normally, stop GhostCam first:

```powershell
powershell -ExecutionPolicy Bypass -File .\GhostCam.ps1 stop
```

That stop flow will:

- stop and delete the PM2 `ghostcam` process when present
- kill any leftover `ghostcam.exe`
- kill leftover Python processes started by GhostCam
- restart common Windows camera host processes so other apps can reacquire the camera

## Default Assets

- Optional background image asset: [test_background.webp](/D:/Documents/GitHub/GhostCam/tests/test_background.webp)
- Default PM2 solid background color: `#ECE8E0`

## License

MIT
