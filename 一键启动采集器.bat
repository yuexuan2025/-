@echo off
setlocal
cd /d "%~dp0"

cls
echo.
echo  ============================================================
echo   大连海洋大学 公开信息采集器
echo  ============================================================
echo.
echo   本工具只采集学校官网的公开信息，不会登录、不会绕过限制。
echo   采集时会礼貌地控制访问速度，请耐心等待。
echo.
echo  [步骤 1/3] 正在检查运行环境...
echo.

where py >nul 2>nul
if not errorlevel 1 (
    py -3 --version >nul 2>nul
    if not errorlevel 1 (
        set "PY=py -3"
        goto run
    )
)

where python >nul 2>nul
if not errorlevel 1 (
    set "PY=python"
    goto run
)

echo  [错误] 没有找到 Python。
echo.
echo   请先安装 Python 3.10 或更高版本：
echo     1. 打开 python.org 下载安装包
echo     2. 安装时务必勾选 “Add python.exe to PATH”
echo     3. 安装完成后重新双击本文件
echo.
pause
exit /b 1

:run
echo   运行环境正常。
echo.
echo  [步骤 2/3] 开始采集（默认每栏目第 1 页，最多 10 篇）...
echo.

%PY% -m dlou_crawler --pages 1 --max-articles 10

echo.
echo  ============================================================
if errorlevel 1 (
    echo  [提示] 采集已结束，部分内容可能因需登录未能完整采集，
    echo         不影响已成功采集的部分，详情见 output\采集报告.txt。
) else (
    echo   采集顺利完成。
)
echo  ============================================================

if exist "output" (
    echo.
    echo  [步骤 3/3] 查看结果
    echo.
    echo   结果已生成在 output 文件夹：
    echo     - 文章清单.txt  文章目录（标题/栏目/日期/链接）
    echo     - 正文合集.txt  每篇文章的完整正文
    echo     - 采集报告.txt  采集概览与警告（推荐先看这个）
    echo     - articles.json 机器可读的原始数据
    echo.
    echo   正在为你打开 output 文件夹...
    start "" "%cd%\output"
) else (
    echo.
    echo   没有生成结果文件夹，请查看上面的提示。
)

echo.
echo   按任意键关闭本窗口。
pause >nul
endlocal

