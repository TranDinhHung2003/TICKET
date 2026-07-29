@echo off
setlocal EnableExtensions
cd /d "%~dp0"
REM Double-click file nay de mo shop ban token (khong can go CMD)
if exist "token-shop\start_shop_silent.vbs" (
  wscript "%~dp0token-shop\start_shop_silent.vbs"
) else (
  call "%~dp0token-shop\start_shop.bat"
)
