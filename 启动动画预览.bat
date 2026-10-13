@echo off
setlocal
pushd "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is required. Install Node.js LTS and run again.
  pause
  exit /b 1
)
if not exist "node_modules\three\build\three.module.js" (
  call npm install
  if errorlevel 1 (
    pause
    exit /b 1
  )
)
start "" "http://127.0.0.1:8765"
node fbx_preview_server.cjs
popd
pause
