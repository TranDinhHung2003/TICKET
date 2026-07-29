@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title FB Poster Token Shop
echo ============================================
echo  FB Poster - Token Shop (tu dong)
echo  MB Bank STK: 0910108069999
echo ============================================
echo.

set "JAVA_CMD="
where java >nul 2>&1 && set "JAVA_CMD=java"
if not defined JAVA_CMD if exist "%JAVA_HOME%\bin\java.exe" set "JAVA_CMD=%JAVA_HOME%\bin\java.exe"
if not defined JAVA_CMD (
  echo [LOI] Chua cai Java 21+. Cai tu https://adoptium.net roi chay lai.
  pause
  exit /b 1
)

if not defined APP_BASE_URL set "APP_BASE_URL=http://localhost:8080"
if not defined SEPAY_BANK set "SEPAY_BANK=MB"
if not defined SEPAY_ACCOUNT set "SEPAY_ACCOUNT=0910108069999"
if not defined SEPAY_ACCOUNT_NAME set "SEPAY_ACCOUNT_NAME=MB BANK"

echo Dang khoi dong server ban hang tu dong...
echo Mo trinh duyet: %APP_BASE_URL%
echo Dong cua so nay se TAT shop. De chay an ^(khong CMD^): bam start_shop_silent.vbs
echo.

start "" "%APP_BASE_URL%"

if exist "target\token-shop-0.0.1-SNAPSHOT.jar" (
  "%JAVA_CMD%" -jar "target\token-shop-0.0.1-SNAPSHOT.jar"
  goto :eof
)

if exist "mvnw.cmd" (
  call "mvnw.cmd" -DskipTests spring-boot:run
  goto :eof
)

echo [LOI] Khong tim thay JAR hoac mvnw.cmd
pause
exit /b 1
