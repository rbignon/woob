@echo off
call settings.cmd
"Bat_To_Exe_Converter_%LOCAL_ARCHITECTURE%.exe" -bat "setup-woob.bat" -save "setup-woob-%WOOB_VERSION%-%ARCHITECTURE%.exe" -icon "ICON\woobtxt.ico" -include "Bat_To_Exe_Converter_%ARCHITECTURE%.exe" -include "wget-%ARCHITECTURE%.exe" -include "convertPNG2ICO.py" -include "get-pip.py" -include "settings.cmd"
