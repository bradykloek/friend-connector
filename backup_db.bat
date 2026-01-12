set PROJECT_DIR=C:\Users\brady\Code\friend-connector
set BACKUP_DIR=C:\Users\brady\Code\friend-connector\backups
set TIMESTAMP=%DATE:~10,4%-%DATE:~4,2%-%DATE:~7,2%

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

sqlite3 "%PROJECT_DIR%\friends.db" ".backup '%BACKUP_DIR%\friends_backup_%TIMESTAMP%.db'"

forfiles /p "%BACKUP_DIR%" /m *.db /d -14 /c "cmd /c del @path"