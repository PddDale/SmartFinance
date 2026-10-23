Unicode true
RequestExecutionLevel user

!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"
!include "WinMessages.nsh"

!ifndef APP_DIR
  !define APP_DIR "${__FILEDIR__}\..\dist\SmartFinance"
!endif
!ifndef OUTPUT_EXE
  !define OUTPUT_EXE "${__FILEDIR__}\..\dist\SmartFinance-Setup.exe"
!endif

Name "SmartFinance"
OutFile "${OUTPUT_EXE}"
InstallDir "$LOCALAPPDATA\Programs\SmartFinance"
ShowInstDetails show
ShowUnInstDetails show

Var InstallMode
Var ExistingInstallDir
Var UpgradeMode
Var ModeDialog
Var RadioInstalled
Var RadioPortable
Var RadioUpdate
Var ShortcutsDialog
Var StartMenuCheckbox
Var DesktopCheckbox
Var CreateStartMenuShortcut
Var CreateDesktopShortcut
Var MigrationDialog
Var MigrationExistingRadio
Var MigrationFolderRadio
Var MigrationEmptyRadio
Var MigrationFolderEdit
Var MigrationFolderButton
Var MigrationChoice
Var MigrationPath
Var MigrationSourceCandidate

!insertmacro MUI_PAGE_WELCOME
Page custom ModePageCreate ModePageLeave
Page custom ShortcutsPageCreate ShortcutsPageLeave
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE DirectoryPageLeave
!insertmacro MUI_PAGE_DIRECTORY
Page custom MigrationPageCreate MigrationPageLeave
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "PortugueseBR"

Function .onInit
  StrCpy $InstallMode "installed"
  StrCpy $UpgradeMode "0"
  ReadRegStr $ExistingInstallDir HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SmartFinance" "InstallLocation"
  IfFileExists "$ExistingInstallDir\SmartFinance.exe" existing_install_found
  StrCpy $ExistingInstallDir ""
existing_install_found:
  ${If} $ExistingInstallDir != ""
    StrCpy $INSTDIR "$ExistingInstallDir"
  ${Else}
    StrCpy $INSTDIR "$LOCALAPPDATA\Programs\SmartFinance"
  ${EndIf}
  StrCpy $MigrationPath ""
  StrCpy $MigrationChoice "empty"
  StrCpy $MigrationSourceCandidate "$DOCUMENTS\SmartFinance\Recursos\Dados\finance.db"
  IfFileExists "$MigrationSourceCandidate" migration_found
  StrCpy $MigrationSourceCandidate "$EXEDIR\..\Recursos\Dados\finance.db"
  IfFileExists "$MigrationSourceCandidate" migration_found
  StrCpy $MigrationSourceCandidate ""
migration_found:
FunctionEnd

Function ModePageCreate
  !insertmacro MUI_HEADER_TEXT "Tipo de uso" "Escolha a instalacao local ou o modo portatil."
  nsDialogs::Create 1018
  Pop $ModeDialog
  ${If} $ExistingInstallDir != ""
    ${NSD_CreateRadioButton} 0 0 100% 14u "Atualizar a instalacao local existente, preservando os dados."
    Pop $RadioUpdate
    ${NSD_SetState} $RadioUpdate ${BST_CHECKED}
    ${NSD_CreateRadioButton} 0 22u 100% 14u "Instalacao local em outra pasta."
    Pop $RadioInstalled
    ${NSD_CreateRadioButton} 0 44u 100% 14u "Portatil: instalar ou atualizar uma pasta portatil existente."
    Pop $RadioPortable
  ${Else}
    ${NSD_CreateRadioButton} 0 0 100% 14u "Instalacao local: instalar para este usuario e permitir atalhos."
    Pop $RadioInstalled
    ${NSD_CreateRadioButton} 0 22u 100% 14u "Portatil: instalar ou atualizar uma pasta portatil existente."
    Pop $RadioPortable
    ${NSD_SetState} $RadioInstalled ${BST_CHECKED}
  ${EndIf}
  nsDialogs::Show
FunctionEnd

Function ModePageLeave
  ${If} $ExistingInstallDir != ""
    ${NSD_GetState} $RadioUpdate $0
    ${If} $0 == ${BST_CHECKED}
      StrCpy $InstallMode "installed"
      StrCpy $UpgradeMode "1"
      StrCpy $INSTDIR "$ExistingInstallDir"
      Return
    ${EndIf}
  ${EndIf}
  ${NSD_GetState} $RadioPortable $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $InstallMode "portable"
    StrCpy $INSTDIR "$DOCUMENTS\SmartFinance-Portable"
    StrCpy $UpgradeMode "0"
  ${Else}
    StrCpy $InstallMode "installed"
    StrCpy $INSTDIR "$LOCALAPPDATA\Programs\SmartFinance"
    StrCpy $UpgradeMode "0"
  ${EndIf}
FunctionEnd

Function ShortcutsPageCreate
  ${If} $InstallMode == "portable"
    Abort
  ${EndIf}
  ${If} $UpgradeMode == "1"
    Abort
  ${EndIf}

  !insertmacro MUI_HEADER_TEXT "Atalhos" "Escolha onde deseja criar atalhos do SmartFinance."
  nsDialogs::Create 1018
  Pop $ShortcutsDialog
  ${NSD_CreateCheckbox} 0 0 100% 14u "Menu Iniciar"
  Pop $StartMenuCheckbox
  ${NSD_SetState} $StartMenuCheckbox ${BST_CHECKED}
  ${NSD_CreateCheckbox} 0 22u 100% 14u "Area de trabalho"
  Pop $DesktopCheckbox
  ${NSD_SetState} $DesktopCheckbox ${BST_UNCHECKED}
  nsDialogs::Show
FunctionEnd

Function ShortcutsPageLeave
  ${NSD_GetState} $StartMenuCheckbox $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $CreateStartMenuShortcut "1"
  ${Else}
    StrCpy $CreateStartMenuShortcut "0"
  ${EndIf}

  ${NSD_GetState} $DesktopCheckbox $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $CreateDesktopShortcut "1"
  ${Else}
    StrCpy $CreateDesktopShortcut "0"
  ${EndIf}
FunctionEnd

Function DirectoryPageLeave
  ${If} $InstallMode == "portable"
    IfFileExists "$INSTDIR\.portable" portable_marker_found
    IfFileExists "$INSTDIR\SmartFinance.exe" invalid_portable_folder
    StrCpy $UpgradeMode "0"
    Return
  portable_marker_found:
    IfFileExists "$INSTDIR\SmartFinance.exe" portable_update_valid invalid_portable_folder
  portable_update_valid:
    StrCpy $UpgradeMode "1"
    Return
  invalid_portable_folder:
    MessageBox MB_ICONEXCLAMATION|MB_OK "A pasta portatil existente nao foi reconhecida. Selecione uma pasta SmartFinance portatil valida ou uma pasta nova."
    Abort
  ${Else}
    ${If} $ExistingInstallDir != ""
      StrCmp $INSTDIR $ExistingInstallDir installed_update_selected
    ${EndIf}
    IfFileExists "$INSTDIR\SmartFinance.exe" invalid_installed_folder
    StrCpy $UpgradeMode "0"
    Return
  installed_update_selected:
    StrCpy $UpgradeMode "1"
    Return
  invalid_installed_folder:
    MessageBox MB_ICONEXCLAMATION|MB_OK "A pasta selecionada ja contem arquivos do SmartFinance, mas nao corresponde a instalacao registrada. Escolha a pasta registrada ou uma pasta nova."
    Abort
  ${EndIf}
FunctionEnd

Function MigrationPageCreate
  ; Em uma atualização, o aplicativo já possui a configuração do último
  ; local escolhido. Não recrie nem substitua essa configuração.
  ${If} $UpgradeMode == "1"
    Abort
  ${EndIf}
  ${If} $MigrationSourceCandidate != ""
    StrCpy $MigrationChoice "existing"
  ${EndIf}
  !insertmacro MUI_HEADER_TEXT "Migrar dados existentes" "Informe, se disponivel, o banco antigo do SmartFinance."
  nsDialogs::Create 1018
  Pop $MigrationDialog
  ${NSD_CreateLabel} 0 0 100% 24u "Escolha como o SmartFinance deve iniciar. Se ja existir um banco, ele sera preservado. Tambem e possivel escolher uma pasta para procurar finance.db."
  Pop $0
  ${If} $MigrationSourceCandidate != ""
    ${NSD_CreateRadioButton} 0 30u 100% 14u "Usar o banco encontrado: $MigrationSourceCandidate"
    Pop $MigrationExistingRadio
    ${NSD_SetState} $MigrationExistingRadio ${BST_CHECKED}
  ${EndIf}
  ${NSD_CreateRadioButton} 0 52u 100% 14u "Comecar sem dados"
  Pop $MigrationEmptyRadio
  ${If} $MigrationSourceCandidate == ""
    ${NSD_SetState} $MigrationEmptyRadio ${BST_CHECKED}
  ${EndIf}
  ${NSD_CreateRadioButton} 0 74u 100% 14u "Escolher uma pasta"
  Pop $MigrationFolderRadio
  ${NSD_CreateText} 0 96u 78% 14u ""
  Pop $MigrationFolderEdit
  ${NSD_CreateButton} 80% 96u 20% 14u "Selecionar pasta"
  Pop $MigrationFolderButton
  ${NSD_OnClick} $MigrationFolderButton MigrationBrowseFolder
  ${NSD_CreateLabel} 0 118u 100% 26u "A pasta escolhida pode conter finance.db. Se nao contiver, um banco vazio sera criado nela."
  Pop $0
  nsDialogs::Show
FunctionEnd

Function MigrationBrowseFolder
  nsDialogs::SelectFolderDialog "Selecione a pasta que contem finance.db" "$DOCUMENTS"
  Pop $0
  ${If} $0 != "error"
    ${If} $0 != ""
      StrCpy $MigrationPath "$0\finance.db"
      ${NSD_SetText} $MigrationFolderEdit "$0"
      ${NSD_SetState} $MigrationFolderRadio ${BST_CHECKED}
    ${EndIf}
  ${EndIf}
FunctionEnd

Function MigrationPageLeave
  ${If} $MigrationSourceCandidate != ""
    ${NSD_GetState} $MigrationExistingRadio $0
    ${If} $0 == ${BST_CHECKED}
      StrCpy $MigrationChoice "existing"
      StrCpy $MigrationPath "$MigrationSourceCandidate"
      Return
    ${EndIf}
  ${EndIf}
  ${NSD_GetState} $MigrationFolderRadio $0
  ${If} $0 == ${BST_CHECKED}
    ${NSD_GetText} $MigrationFolderEdit $MigrationPath
    ${If} $MigrationPath == ""
      MessageBox MB_ICONEXCLAMATION|MB_OK "Selecione uma pasta ou escolha Comecar sem dados."
      Abort
    ${EndIf}
    StrCpy $MigrationPath "$MigrationPath\finance.db"
    IfFileExists "$MigrationPath" migration_path_valid
    StrCpy $MigrationChoice "folder"
    Return
  migration_path_valid:
    StrCpy $MigrationChoice "folder"
    Return
  ${EndIf}
  StrCpy $MigrationChoice "empty"
  StrCpy $MigrationPath ""
FunctionEnd

Section "SmartFinance"
  ${If} $UpgradeMode == "1"
    ClearErrors
    RMDir /r "$INSTDIR\_internal.old"
    Delete "$INSTDIR\SmartFinance.exe.old"
    IfErrors update_previous_cleanup_failed

    ClearErrors
    RMDir /r "$INSTDIR\_smartfinance_update_stage"
    IfErrors update_stage_failed
    ClearErrors
    SetOutPath "$INSTDIR\_smartfinance_update_stage"
    File /r "${APP_DIR}\*"
    IfErrors update_stage_failed

    ClearErrors
    Rename "$INSTDIR\SmartFinance.exe" "$INSTDIR\SmartFinance.exe.old"
    IfErrors update_files_locked

    ClearErrors
    Rename "$INSTDIR\_internal" "$INSTDIR\_internal.old"
    IfErrors restore_old_executable

    ClearErrors
    Rename "$INSTDIR\_smartfinance_update_stage\_internal" "$INSTDIR\_internal"
    IfErrors restore_old_installation

    ClearErrors
    Rename "$INSTDIR\_smartfinance_update_stage\SmartFinance.exe" "$INSTDIR\SmartFinance.exe"
    IfErrors restore_previous_internal

    Delete "$INSTDIR\SmartFinance.exe.old"
    RMDir /r "$INSTDIR\_internal.old"
    RMDir /r "$INSTDIR\_smartfinance_update_stage"
    Goto update_files_ready

  restore_previous_internal:
    RMDir /r "$INSTDIR\_internal"
  restore_old_installation:
    Rename "$INSTDIR\_internal.old" "$INSTDIR\_internal"
  restore_old_executable:
    Rename "$INSTDIR\SmartFinance.exe.old" "$INSTDIR\SmartFinance.exe"
  update_files_locked:
    RMDir /r "$INSTDIR\_smartfinance_update_stage"
    MessageBox MB_ICONEXCLAMATION|MB_OK "Nao foi possivel atualizar os arquivos. Feche o SmartFinance e tente novamente. Os dados nao foram alterados."
    Abort

  update_previous_cleanup_failed:
    MessageBox MB_ICONEXCLAMATION|MB_OK "Nao foi possivel limpar uma tentativa anterior de atualizacao. Feche o SmartFinance e tente novamente. Os dados nao foram alterados."
    Abort

  update_stage_failed:
    RMDir /r "$INSTDIR\_smartfinance_update_stage"
    MessageBox MB_ICONEXCLAMATION|MB_OK "Nao foi possivel preparar os arquivos da atualizacao. Os dados nao foram alterados."
    Abort
  ${EndIf}

  ${If} $UpgradeMode != "1"
    SetOutPath "$INSTDIR"
    File /r "${APP_DIR}\*"
  ${EndIf}

update_files_ready:
  SetOutPath "$INSTDIR"
  ; Backups do usuário ficam fora da instalação. Remova apenas resíduos JSON
  ; que eventualmente tenham sido incluídos em versões antigas do programa.
  Delete "$INSTDIR\BackupSmartFin - *.json"
  Delete "$INSTDIR\database.json"
  Delete "$INSTDIR\backup_*.json"
  Delete "$INSTDIR\*_backup.json"
  Delete "$INSTDIR\*_export.json"

  ${If} $InstallMode == "portable"
    FileOpen $0 "$INSTDIR\.portable" w
    FileWrite $0 "portable"
    FileClose $0
    Delete "$INSTDIR\Uninstall.exe"
    Delete "$SMPROGRAMS\SmartFinance\SmartFinance.lnk"
    Delete "$DESKTOP\SmartFinance.lnk"
    RMDir "$SMPROGRAMS\SmartFinance"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SmartFinance"
  ${Else}
    Delete "$INSTDIR\.portable"
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    ${If} $UpgradeMode != "1"
      Delete "$SMPROGRAMS\SmartFinance\SmartFinance.lnk"
      Delete "$DESKTOP\SmartFinance.lnk"
      RMDir "$SMPROGRAMS\SmartFinance"
      ${If} $CreateStartMenuShortcut == "1"
        CreateDirectory "$SMPROGRAMS\SmartFinance"
        CreateShortcut "$SMPROGRAMS\SmartFinance\SmartFinance.lnk" "$INSTDIR\SmartFinance.exe"
      ${EndIf}
      ${If} $CreateDesktopShortcut == "1"
        CreateShortcut "$DESKTOP\SmartFinance.lnk" "$INSTDIR\SmartFinance.exe"
      ${EndIf}
    ${EndIf}
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SmartFinance" "DisplayName" "SmartFinance"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SmartFinance" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SmartFinance" "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SmartFinance" "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SmartFinance" "NoRepair" 1
  ${EndIf}

  ${If} $MigrationPath != ""
    FileOpen $0 "$INSTDIR\legacy-db-path.txt" w
    FileWrite $0 "$MigrationPath"
    FileClose $0
  ${EndIf}
  ${If} $MigrationChoice == "folder"
    ${If} $InstallMode == "portable"
      CreateDirectory "$INSTDIR\Dados"
      FileOpen $0 "$INSTDIR\Dados\database-location.txt" w
    ${Else}
      CreateDirectory "$LOCALAPPDATA\SmartFinance"
      FileOpen $0 "$LOCALAPPDATA\SmartFinance\database-location.txt" w
    ${EndIf}
    FileWrite $0 "$MigrationPath"
    FileClose $0
  ${EndIf}
SectionEnd

Section "Uninstall"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SmartFinance"
  Delete "$SMPROGRAMS\SmartFinance\SmartFinance.lnk"
  Delete "$DESKTOP\SmartFinance.lnk"
  RMDir "$SMPROGRAMS\SmartFinance"
  SetOutPath "$TEMP"
  Delete "$INSTDIR\*.*"
  RMDir /r "$INSTDIR"
SectionEnd
