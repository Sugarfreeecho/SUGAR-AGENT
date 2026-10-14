; SugarAgent 安装器定制（由 electron-builder 的 nsis.include 引入，被置于生成脚本最前面）
;
; 这里做五件事：
;   1) 只做“仅当前用户”安装：跳过 electron-builder 那个带未本地化英文的“为哪位用户安装”页；
;   2) 增加“快捷方式选项”页，让用户自己决定是否创建桌面/开始菜单快捷方式；
;   3) 安装后回收未勾选的快捷方式，卸载时回收 installer store 缓存（约 200MB）；
;   4) 更新/卸载只删除应用文件，保留与 app/python 同级的 workspace、.config 和 .sugaragent；
;   5) 用户主动卸载时把本产品在本机的其余痕迹一起清掉（应用状态目录、%TEMP% 临时目录、
;      协议与通知注册表键、Electron userData），只留用户数据；升级只替换程序文件，
;      用户数据与状态一律保留。用户工作目录（含自定义到安装目录之外的目录）永远不动。

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

; 升级/卸载分流：安装器覆盖安装时会把旧卸载器以 `--updated` 调用（见 installUtil.nsh 的
; uninstallOldVersion），此时只应替换程序文件；只有用户主动卸载才做彻底清理。
Var sugarUpgradeMode
Var sugarDeleteAppData

!macro customInstall
  ; Stable system-notification identity, independent of legacy exe metadata.
  WriteRegStr HKCU "Software\Classes\AppUserModelId\${APP_ID}" "DisplayName" "SugarAgent"
  WriteRegStr HKCU "Software\Classes\AppUserModelId\${APP_ID}" "IconUri" "$INSTDIR\resources\tray.ico"
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
  ${StdUtils.TestParameter} $sugarUpgradeMode "updated"
  ${StdUtils.TestParameter} $sugarDeleteAppData "delete-app-data"
  StrCmp "$sugarDeleteAppData" "true" sugar_uninstall_thorough 0
  StrCmp "$sugarUpgradeMode" "true" sugar_uninstall_upgrade 0

  ; ---- 用户主动卸载：清掉本产品痕迹（工作目录与用户数据保留策略见 un.SugarAgentRemoveFiles）----
  sugar_uninstall_thorough:
    RMDir /r "$LOCALAPPDATA\${SUGARAGENT_UPDATER_CACHE}"   ; installer store（约 200MB）
    RMDir /r "$LOCALAPPDATA\sugaragent-desktop-updater"    ; 历史包名（sugaragent-desktop）遗留
    RMDir /r "$LOCALAPPDATA\SugarAgent"                    ; 应用状态：安全库（审批/MCP）、用户插件
    Call un.SugarAgentRemoveTempDirs                       ; %TEMP%\sugaragent-*
    DeleteRegKey HKCU "Software\Classes\sugaragent-desktop"
    DeleteRegKey HKCU "Software\Classes\AppUserModelId\${APP_ID}"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Notifications\Settings\${APP_ID}"
    Goto sugar_uninstall_done

  sugar_uninstall_upgrade:
    ; 升级：只清历史包名遗留；本包 store 由正在运行的安装器随后覆盖为新的安装包
    RMDir /r "$LOCALAPPDATA\sugaragent-desktop-updater"

  sugar_uninstall_done:
!macroend

; 清理 %TEMP% 下本产品的临时目录（sugaragent-plugin-runtime-*、sugaragent-egress-nonces 等）。
; 只删目录、不删同名文件；被占用而删不掉的项忽略错误，交给系统磁盘清理。
Function un.SugarAgentRemoveTempDirs
  Push $R0
  Push $R1
  Push $R2

  SetOutPath $TEMP
  FindFirst $R1 $R2 "$TEMP\sugaragent-*"
  sugar_temp_loop:
    StrCmp $R2 "" sugar_temp_done
    IfFileExists "$TEMP\$R2\*.*" 0 sugar_temp_next
      RMDir /r "$TEMP\$R2"
    Goto sugar_temp_next
  sugar_temp_next:
    FindNext $R1 $R2
    Goto sugar_temp_loop
  sugar_temp_done:
    FindClose $R1

  Pop $R2
  Pop $R1
  Pop $R0
FunctionEnd

; patch-nsis.mjs 保留升级时的原子移动/失败回滚，排除用户工作目录和配置。
; 最终删除阶段从模板回调到这里，仅递归进入用户数据的两级祖先，
; 其余应用目录用原生 RMDir /r 清理，保留目录本身不遍历、不移动。
Function un.SugarAgentRemoveFiles
  Exch $R0
  Push $R1
  Push $R2
  Push $R3
  FindFirst $R1 $R2 "$INSTDIR$R0\*.*"

  sugar_remove_loop:
    StrCmp $R2 "" sugar_remove_done
    StrCmp $R2 "." sugar_remove_next
    StrCmp $R2 ".." sugar_remove_next
    StrCmp "$R0\$R2" "\resources\runtime\workspace" sugar_remove_next
    StrCmp "$R0\$R2" "\resources\runtime\.config" sugar_remove_next
    StrCmp "$R0\$R2" "\resources\runtime\.sugaragent" sugar_remove_next
    StrCmp "$R0\$R2" "\resources" sugar_remove_ancestor
    StrCmp "$R0\$R2" "\resources\runtime" sugar_remove_ancestor
    IfFileExists "$INSTDIR$R0\$R2\*.*" 0 sugar_remove_file
    RMDir /r "$INSTDIR$R0\$R2"
    Goto sugar_remove_next

  sugar_remove_file:
    Delete "$INSTDIR$R0\$R2"
    Goto sugar_remove_next

  sugar_remove_ancestor:
    Push "$R0\$R2"
    Call un.SugarAgentRemoveFiles

  sugar_remove_next:
    FindNext $R1 $R2
    Goto sugar_remove_loop

  sugar_remove_done:
    FindClose $R1
    ; 不使用 /r：保留包含 workspace/.config 的 runtime/resources/安装目录。
    RMDir "$INSTDIR$R0"
    Pop $R3
    Pop $R2
    Pop $R1
    Pop $R0
FunctionEnd
