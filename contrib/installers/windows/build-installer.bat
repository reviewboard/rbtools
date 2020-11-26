::
:: Build the installer for RBTools for Windows.
::
:: This will fetch Python and build a WiX package for RBTools.
::
:: This requires that curl for Windows (and its ca-bundle) are properly
:: installed and working in order to download files.
::
@echo off
setlocal


::-------------------------------------------------------------------------
:: Build paths
::-------------------------------------------------------------------------

:: Store out the absolute path to the tree root.
pushd ..\..\..
set TREE_ROOT=%CD%
popd

set BUILD_DEST=%TREE_ROOT%\dist
set BUILD_BASE=%TREE_ROOT%\build\windows-pkg
set BUILD_ROOT=%BUILD_BASE%\build
set BUILD_STAGE=%BUILD_BASE%\stage
set DEPS_DIR=%BUILD_BASE%\deps


::-------------------------------------------------------------------------
:: Dependencies
::-------------------------------------------------------------------------
set PYTHON_VERSION=3.8.6
set PYTHON_FILENAME=python-%PYTHON_VERSION%-amd64.exe
set PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/%PYTHON_FILENAME%
set PYTHON_MD5=2acba3117582c5177cdd28b91bbe9ac9
set PYTHON_DEP=%DEPS_DIR%\python-%PYTHON_VERSION%


::-------------------------------------------------------------------------
:: Binaries
::-------------------------------------------------------------------------
set BUNDLED_PYTHON_DIR=%BUILD_ROOT%\Python
set BUNDLED_PYTHON=%BUNDLED_PYTHON_DIR%\python.exe

call :SetMSBuildPath || goto :Abort


::-------------------------------------------------------------------------
:: Signing certificate
::-------------------------------------------------------------------------
set CERT_THUMBPRINT=deee311acc700a6f797018a6cf4075131b6f7198


::-------------------------------------------------------------------------
:: Begin the installation process
::-------------------------------------------------------------------------
if not exist "%DEPS_DIR%" mkdir "%DEPS_DIR%"
if not exist "%BUILD_STAGE%" mkdir "%BUILD_STAGE%"

call :InstallPython || goto :Abort
call :CreateBuildDirectory || goto :Abort
call :InstallPackages || goto :Abort
call :InstallRBTools || goto :Abort
call :RemoveUnwantedFiles || goto :Abort
call :BuildInstaller || goto :Abort

echo Done.

goto :EOF


::-------------------------------------------------------------------------
:: Installs Python
::-------------------------------------------------------------------------
:InstallPython
setlocal

echo.
echo == Installing Python ==

set _PYTHON_INSTALLER=%TEMP%\%PYTHON_FILENAME%

if not exist "%PYTHON_DEP%" (
    if not exist "%_PYTHON_INSTALLER%" (
        echo Preparing to download Python v%PYTHON_VERSION%...
        call :DownloadAndVerify %PYTHON_URL% ^
                                "%_PYTHON_INSTALLER%" ^
                                %PYTHON_MD5% || exit /B 1

        echo Downloaded to %_PYTHON_INSTALLER%
    )

    echo Running the installer...
    "%_PYTHON_INSTALLER%" /quiet ^
        AssociateFiles=0 Include_doc=0 Include_debug=0 Include_launcher=0 ^
        Include_tcltk=0 Include_test=0 InstallAllUsers=0 ^
        InstallLauncherAllUsers=0 Shortcuts=0 TargetDir="%PYTHON_DEP%-temp"
    xcopy /EYI "%PYTHON_DEP%-temp" "%PYTHON_DEP%"

    :: Remove the old install from the temp directory, and clean up the
    :: registry files so future installs aren't impacted.
    "%_PYTHON_INSTALLER%" /quiet /uninstall
)

goto :EOF


::-------------------------------------------------------------------------
:: Populates the build directory from dependencies
::-------------------------------------------------------------------------
:CreateBuildDirectory
setlocal

:: Create a copy of the Python directory. This is where we'll be installing
:: RBTools and dependencies, and what we'll actually be distributing.
echo.
echo == Creating build directory ==

call :DeleteIfExists "%BUILD_ROOT%"
xcopy /EYI "%PYTHON_DEP%" "%BUNDLED_PYTHON_DIR%" >NUL

goto :EOF


::-------------------------------------------------------------------------
:: Install package tools
::-------------------------------------------------------------------------
:InstallPackages
setlocal

echo.
echo == Installing pip and setuptools ==
echo.
echo --------------------------- [Install log] ---------------------------

pushd %TREE_ROOT%
"%BUNDLED_PYTHON%" -m ensurepip --upgrade

if ERRORLEVEL 1 (
    popd
    exit /B 1
)

"%BUNDLED_PYTHON%" -m pip install -U pip setuptools

if ERRORLEVEL 1 (
    popd
    exit /B 1
)

popd

echo ---------------------------------------------------------------------

goto :EOF


::-------------------------------------------------------------------------
:: Install RBTools and all dependencies
::-------------------------------------------------------------------------
:InstallRBTools
setlocal

echo.
echo == Installing RBTools and dependencies ==
echo.
echo --------------------------- [Install log] ---------------------------

pushd %TREE_ROOT%
"%BUNDLED_PYTHON%" setup.py release install >NUL

if ERRORLEVEL 1 (
    popd
    exit /B 1
)

popd

echo ---------------------------------------------------------------------

goto :EOF


::-------------------------------------------------------------------------
:: Remove unwanted files from the build directory.
::-------------------------------------------------------------------------
:RemoveUnwantedFiles
setlocal

echo.
echo == Removing unwanted files ==

call :DeleteIfExists "%BUNDLED_PYTHON_DIR%\Doc"
call :DeleteIfExists "%BUNDLED_PYTHON_DIR%\tcl"
call :DeleteIfExists "%BUNDLED_PYTHON_DIR%\%PYTHON_FILENAME%"

goto :EOF


::-------------------------------------------------------------------------
:: Build the installer
::-------------------------------------------------------------------------
:BuildInstaller
setlocal

echo.
echo == Building the RBTools installer ==

call :GetRBToolsVersion
set _rbtools_version=%_return1%

set _wix_path=%CD%\wix

%MSBUILD% ^
    /p:Version="%_rbtools_version%" ^
    /p:Platform=x64 ^
    /p:ExeSuffix=-amd64 ^
    /p:Root="%BUILD_ROOT%" ^
    /p:OutputPath="%BUILD_STAGE%\\" ^
    /p:SourcePath="%_wix_path%" ^
    /p:CertificateThumbprint=%CERT_THUMBPRINT% ^
    /p:TimestampUrl=http://timestamp.comodoca.com/authenticode ^
    "%_wix_path%\rbtools.sln"

if ERRORLEVEL 1 exit /B 1

mkdir "%BUILD_DEST%" 2>&1
dir "%BUILD_STAGE%" /S
copy "%BUILD_STAGE%\RBTools-%_rbtools_version%*.exe" "%BUILD_DEST%" >NUL

echo Installer published to %BUILD_DEST%

goto :EOF


::-------------------------------------------------------------------------
:: Returns the Python version for RBTools.
::
:: This must be run after installing RBTools in %BUILD_ROOT%.
::-------------------------------------------------------------------------
:GetRBToolsVersion
setlocal

set _version_file=%BUILD_STAGE%\VERSION

"%BUNDLED_PYTHON%" scripts/get-version.py > "%_version_file%"
set /P _version= < "%_version_file%"
del "%_version_file%"

endlocal & set _return1=%_version%
goto :EOF


::-------------------------------------------------------------------------
:: Determines the path to MSBuild.exe
::-------------------------------------------------------------------------
:SetMSBuildPath
setlocal

set _reg_key=HKLM\SOFTWARE\Microsoft\MSBuild\ToolsVersions\4.0
set _reg_query_cmd=reg.exe query "%_reg_key%" /V MSBuildToolsPath

%_reg_query_cmd% >NUL 2>&1

if ERRORLEVEL 1 (
    echo Cannot obtain the MSBuild tools path from the registry.
    exit /B 1
)

for /f "skip=2 tokens=2,*" %%A in ('%_reg_query_cmd%') do (
    SET MSBUILDDIR=%%B
)

if not exist %MSBUILDDIR%nul (
    echo The MSBuild tools path from the registry does not exist.
    echo
    echo The missing path is: %MSBUILDDIR%
    exit /B 1
)

if not exist %MSBUILDDIR%msbuild.exe (
    echo MSBuild.exe is missing from %MSBUILDDIR%.
    exit /B 1
)

endlocal & set MSBUILD=%MSBUILDDIR%msbuild.exe
goto :EOF


::-------------------------------------------------------------------------
:: Downloads and verifies a file from a URL.
::-------------------------------------------------------------------------
:DownloadAndVerify url dest expected_hash
setlocal

set _url=%~1
set _dest=%~2
set _expected_hash=%~3

if not exist "%_dest%" (
    call :DownloadFile %_url% "%_dest%" || exit /B 1
)

call :VerifyMD5 "%_dest%" %_expected_hash% || exit /B 1

goto :EOF


::-------------------------------------------------------------------------
:: Downloads a file from a URL to a given destination.
::-------------------------------------------------------------------------
:DownloadFile url dest
setlocal

set _url=%~1
set _dest=%~2

echo Downloading %_url% to %_dest%...

curl "%_url%" -o "%_dest%" || exit /B 1

echo Downloaded %_url%

goto :EOF


::-------------------------------------------------------------------------
:: Verifies the MD5 checksum of a file.
::-------------------------------------------------------------------------
:VerifyMD5 filename expected_hash
setlocal

set _filename=%~1
set _expected_hash=%~2

echo Verifying that %_filename% has MD5 hash %_expected_hash%...

PowerShell -Command ^
 "$md5 = New-Object Security.Cryptography.MD5CryptoServiceProvider;"^
 "$file = [System.IO.File]::ReadAllBytes('%_filename%');"^
 "$hash = [System.BitConverter]::ToString($md5.ComputeHash($file));"^
 "$hash = $hash.toLower().Replace('-', '');"^
 "Write-Host '%_filename% has a valid hash.';"^
 "if ($hash -eq '%_expected_hash%') {"^
 "    exit 0;"^
 "} else {"^
 "    Write-Host 'Invalid hash for %_filename%.';"^
 "    exit 1;"^
 "}" || exit /B 1

echo Hash verified.

goto :EOF


::-------------------------------------------------------------------------
:: Deletes a file or directory if it exists.
::-------------------------------------------------------------------------
:DeleteIfExists path
setlocal

set _path=%~1

if exist "%_path%" (
    del /F /Q "%_path%" 2>NUL
    rmdir /S /Q "%_path%" 2>NUL
)

goto :EOF


::-------------------------------------------------------------------------
:: Aborts the creation of the installer.
::-------------------------------------------------------------------------
:Abort

echo Installation aborted.
exit /B 1
