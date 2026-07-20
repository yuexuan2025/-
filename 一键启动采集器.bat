@echo off
setlocal
cd /d "%~dp0"

title DLOU 官网采集器 by yuexuan
cls
echo.
echo  ============================================================
echo   大连海洋大学官网公开信息采集器  -  by yuexuan
echo  ============================================================
echo.
echo   本工具仅采集学校官网的公开信息，不登录、不绕认证。
echo   采集过程中请勿关闭本窗口。
echo.

where py >nul 2>nul
if not errorlevel 1 (
    set "PY=py -3"
    goto run
)
where python >nul 2>nul
if not errorlevel 1 (
    set "PY=python"
    goto run
)
echo  [错误] 没有找到 Python。
echo.
echo   请先安装 Python 3.10 或更高版本：
echo     1. 到 python.org 下载安装包
echo     2. 安装时务必勾选 “Add python.exe to PATH”
echo     3. 安装完成后重新双击本文件
echo.
pause
exit /b 1

:run
echo   正在启动采集（默认每栏 3 页、最多 50 篇，4 线程并发）...
echo.
%PY% -m dlou_crawler --pages 3 --max-articles 50

echo.
echo  ============================================================
if errorlevel 1 (
    echo  [提示] 采集中断（可能部分页面需登录或暂时无法访问）。
    echo         已成功采集的内容仍保存在 output 文件夹中。
) else (
    echo  [完成] 采集顺利完成。
)
echo  ============================================================
echo.

if exist "output" (
    echo   正在打开结果文件夹 output ...
    explorer "%~dp0output"
) else (
    echo   未生成结果文件，请查看上方提示。
)
echo.
echo   按任意键关闭本窗口。
pause >nul
endlocal
