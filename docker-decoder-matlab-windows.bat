@echo off
REM Docker Compose script for Windows

REM Define the decoder configuration file
set "DECODER_IMAGE_TAG=%~2"
if not defined DECODER_IMAGE_TAG set "DECODER_IMAGE_TAG=066a"

REM Define a fake user (no matter for windows)
set "USER_ID=1000"
set "GROUP_ID=1000"

REM Define float to decode
set "FLOAT_WMO=%~1"
if not defined FLOAT_WMO (
    echo [ERROR] FLOAT_WMO required ! please execute script with FLOAT_WMO as parameter. >&2
    pause
    exit /b 1
)

REM Get current date and time in the required format
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set "formattedDateTime=%datetime:~0,4%%datetime:~4,2%%datetime:~6,2%T%datetime:~8,2%%datetime:~10,2%%datetime:~12,2%Z"

REM Define script command
set "DECODER_COMMAND=/mnt/runtime 'rsynclog' 'all' 'configfile' '/mnt/data/config/decoder_conf.json' 'xmlreport' 'co041404_%formattedDateTime%_%FLOAT_WMO%.xml' 'floatwmo' '%FLOAT_WMO%' 'PROCESS_REMAINING_BUFFERS' '1'""

REM Bring down the containers
docker compose -f compose.yaml -f compose.matlab-runtime.yaml down

REM Bring up the containers
docker compose -f compose.yaml -f compose.matlab-runtime.yaml up

REM Pause to keep the window open
pause
