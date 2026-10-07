; SugarAgent 安装器定制（由 electron-builder 的 nsis.include 引入，被置于生成脚本最前面）
;
; 这里做三件事：
;   1) 只做“仅当前用户”安装：跳过 electron-builder 那个带未本地化英文的“为哪位用户安装”页；
;   2) 增加“快捷方式选项”页，让用户自己决定是否创建桌面/开始菜单快捷方式；
;   3) 安装后回收未勾选的快捷方式，卸载时回收 installer store 缓存（约 200MB）。

; ---- 1) 仅当前用户安装 ----------------------------------------------------
; 安装模式页在 Pre 回调里先读 $isForceMachineInstall / $isForceCurrentInstall，
; 命中后设置模式并 Abort（即跳过本页），于是向导从“选定安装位置”页开始。

!macro customInstallMode
  StrCpy $isForceCurrentInstall "1"
!macroend

; ---- 2) 快捷方式选项页 ----------------------------------------------------
; template 顺序（installSection.nsh）：installApplicationFiles → addStartMenuLink
; → addDesktopLink → customInstall，因此这里只记录选择，安装后再按选择回收。

Var SugarDesktopShortcut     ; "1" 创建 / "0" 不创建
Var SugarStartMenuShortcut
Var SugarDesktopBox
Var SugarStartMenuBox
Var SugarShortcutPageInit

!ifndef ONE_CLICK

; 我们的 include 被放在生成脚本最前面，早于模板自己的 !include nsDialogs.nsh，
; 所以这里自行引入（nsDialogs.nsh 自带重复包含保护）。
!include nsDialogs.nsh

!macro customPageAfterChangeDir
  Page custom SugarShortcutOptionsCreate SugarShortcutOptionsLeave
!macroend

Function SugarShortcutOptionsCreate
  nsDialogs::Create 1018
  Pop $0
  StrCmp $0 "error" 0 +2
    Abort

  ; 自定义页默认沿用上一页的页眉，这里直接改 MUI2 的头部标题(1037)/副标题(1038)控件。
  ; 不能用 !insertmacro MUI_HEADER_TEXT：本 include 在 MUI2.nsh 之前编译，该宏尚未定义。
  GetDlgItem $0 $HWNDPARENT 1037
  SendMessage $0 0x000C 0 "STR:快捷方式选项"
  GetDlgItem $0 $HWNDPARENT 1038
  SendMessage $0 0x000C 0 "STR:选择要创建哪些快捷方式。"

  ${NSD_CreateLabel} 0 0 100% 24u "请选择要创建的快捷方式，安装完成后可在系统里随时增删："
  Pop $0

  ${NSD_CreateCheckBox} 0 30u 100% 12u "创建桌面快捷方式"
  Pop $SugarDesktopBox
  ${NSD_CreateCheckBox} 0 48u 100% 12u "在开始菜单中创建快捷方式"
  Pop $SugarStartMenuBox

  StrCmp $SugarShortcutPageInit "1" +5
    ${NSD_SetState} $SugarDesktopBox ${BST_CHECKED}
    ${NSD_SetState} $SugarStartMenuBox ${BST_CHECKED}
    StrCpy $SugarShortcutPageInit "1"

  nsDialogs::Show
FunctionEnd

Function SugarShortcutOptionsLeave
  ${NSD_GetState} $SugarDesktopBox $0
  StrCpy $SugarDesktopShortcut $0
  ${NSD_GetState} $SugarStartMenuBox $1
  StrCpy $SugarStartMenuShortcut $1
FunctionEnd

!endif

; ---- 3) 安装/卸载阶段的清理 ----------------------------------------------
; electron-builder 会把安装器自身复制到 %LOCALAPPDATA%\<包名>-updater\installer.exe
; （约 200MB，用于原地升级/修复）；它的卸载器默认不清理，这里补上，并顺手清掉旧包名遗留。

!define SUGARAGENT_UPDATER_CACHE "sugaragent-updater"

!macro customInstall
  ; 覆盖安装时清掉历史包名（sugaragent-desktop）留下的 installer store
  RMDir /r "$LOCALAPPDATA\sugaragent-desktop-updater"

  ; 用户取消勾选的快捷方式：安装段已按默认创建好，这里回收
  StrCmp $SugarStartMenuShortcut "0" 0 sugar_keep_start_menu
    Delete "$newStartMenuLink"
  sugar_keep_start_menu:

  StrCmp $SugarDesktopShortcut "0" 0 sugar_keep_desktop
    Delete "$newDesktopLink"
  sugar_keep_desktop:
!macroend

!macro customUnInstall
  ; 卸载时回收本包的 installer store
  RMDir /r "$LOCALAPPDATA\${SUGARAGENT_UPDATER_CACHE}"
!macroend
