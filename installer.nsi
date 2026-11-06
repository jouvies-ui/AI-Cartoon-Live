Unicode true
!include "MUI2.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
Name "AI-Cartoon-Live"
OutFile "${OUTPUT_FILE}"
InstallDir "$PROGRAMFILES64\WhaleCompanion"
InstallDirRegKey HKLM "Software\WhaleCompanion" "InstallDir"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
SetCompressorDictSize 64
VIProductVersion "${VERSION}.0"
VIAddVersionKey /LANG=2052 "ProductName" "AI-Cartoon-Live"
VIAddVersionKey /LANG=2052 "FileDescription" "鲸鱼娘独立本机部署安装程序"
VIAddVersionKey /LANG=2052 "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=2052 "LegalCopyright" "开源派生作品；各组件版权见随附许可"
!define MUI_ABORTWARNING
!define MUI_ICON "${APP_ICON}"
!define MUI_UNICON "${APP_ICON}"
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchApplication
!define MUI_FINISHPAGE_RUN_TEXT "打开鲸鱼娘，填写 DeepSeek API Key"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${NOTICE_FILE}"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "需要 Windows 10/11 64 位系统。" /SD IDOK
    Abort
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP "需要 Windows 10/11。" /SD IDOK
    Abort
  ${EndIf}
  SetRegView 64
  nsExec::ExecToStack '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -Command "if (Get-Process WhaleCompanion -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }"'
  Pop $0
  Pop $1
  ${If} $0 != 0
    MessageBox MB_ICONSTOP "请先退出正在运行的鲸鱼娘，再启动安装程序。" /SD IDOK
    Abort
  ${EndIf}
  InitPluginsDir
  SetOutPath "$PLUGINSDIR"
  File /oname=check-gpu.ps1 "${GPU_CHECK}"
  nsExec::ExecToStack '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\check-gpu.ps1"'
  Pop $0
  Pop $1
  ${If} $0 != 0
    MessageBox MB_ICONSTOP "安装前显卡检查未通过。需要 NVIDIA GTX 10 系列或更新显卡及正常驱动。本次未安装应用，请更新驱动后再试。" /SD IDOK
    Abort
  ${EndIf}
FunctionEnd

Section "本地数字伙伴" SEC_MAIN
  SetOutPath "$PLUGINSDIR"
  File /oname=vc_redist.x64.exe "${VC_REDIST}"
  ExecWait '"$PLUGINSDIR\vc_redist.x64.exe" /install /quiet /norestart' $0
  ${If} $0 != 0
  ${AndIf} $0 != 1638
  ${AndIf} $0 != 3010
    MessageBox MB_ICONSTOP "Windows 运行库安装失败（$0）。请重启电脑后重新安装。" /SD IDOK
    Abort
  ${EndIf}
  ${If} $0 == 3010
    SetRebootFlag true
  ${EndIf}
  SetOutPath "$INSTDIR"
  File /r "${APP_DIR}/*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  SetShellVarContext all
  CreateDirectory "$SMPROGRAMS\鲸鱼娘"
  CreateShortcut "$SMPROGRAMS\鲸鱼娘\鲸鱼娘.lnk" "$INSTDIR\WhaleCompanion.exe" "" "$INSTDIR\resources\app\assets\whale.ico" 0
  CreateShortcut "$DESKTOP\鲸鱼娘.lnk" "$INSTDIR\WhaleCompanion.exe" "" "$INSTDIR\resources\app\assets\whale.ico" 0
  WriteRegStr HKLM "Software\WhaleCompanion" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WhaleCompanion" "DisplayName" "AI-Cartoon-Live"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WhaleCompanion" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WhaleCompanion" "DisplayIcon" '$\"$INSTDIR\WhaleCompanion.exe$\",0'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WhaleCompanion" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WhaleCompanion" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WhaleCompanion" "NoRepair" 1
SectionEnd

Function LaunchApplication
  Exec '"$WINDIR\explorer.exe" "$INSTDIR\WhaleCompanion.exe"'
FunctionEnd

Section "Uninstall"
  MessageBox MB_OKCANCEL "请先退出鲸鱼娘应用。卸载会删除程序文件，保留本机的角色设置、记忆和加密密钥。" /SD IDOK IDCANCEL cancel
  nsExec::ExecToStack '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -Command "if (Get-Process WhaleCompanion -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }"'
  Pop $0
  Pop $1
  ${If} $0 != 0
    MessageBox MB_ICONSTOP "应用仍在运行。请退出鲸鱼娘后重新卸载。" /SD IDOK
    Abort
  ${EndIf}
  SetRegView 64
  SetShellVarContext all
  Delete "$DESKTOP\鲸鱼娘.lnk"
  Delete "$SMPROGRAMS\鲸鱼娘\鲸鱼娘.lnk"
  RMDir "$SMPROGRAMS\鲸鱼娘"
  DeleteRegKey HKLM "Software\WhaleCompanion"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WhaleCompanion"
  !include "${UNINSTALL_FILES}"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  cancel:
SectionEnd
