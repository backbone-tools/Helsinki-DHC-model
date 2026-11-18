:: Run settings, whole numbers: the first day solved (1 = the first day of the time-series
:: window set in RunSetup of the input workbook) and how many days
set /a START=1
set /a D=365
set "TAG=day%START%_%D%d"
Title Helsinki DHC, %D%d from day %START%

:: running backbone from the repository root, wherever this file is started from
cd /d "%~dp0.."
gams Backbone.gms ^
--input_dir=./Helsinki-DHC-model/inputData ^
--input_file_excel=HelsinkiDHC-inputData.xlsx ^
--input_excel_index=INDEX ^
--input_excel_checkdate=checkDate ^
--output_dir=./Helsinki-DHC-model/results ^
--output_file=results_%TAG%.gdx ^
--init_file=scheduleInit.gms ^
--debug=0 ^
--startDay=%START% ^
--modelledDays=%D%

cmd
