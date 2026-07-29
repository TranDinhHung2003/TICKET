' Chay Token Shop an, khong hien cua so CMD
Option Explicit
Dim sh, fso, dir, bat
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
bat = dir & "\start_shop.bat"
' 0 = an cua so, True = khong cho script VBS doi
sh.Run """" & bat & """", 0, False
WScript.Sleep 4000
sh.Run "http://localhost:8080", 1, False
