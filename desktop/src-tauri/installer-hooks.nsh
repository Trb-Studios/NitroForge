; Custom NSIS installer hooks for Nitro Forge.
;
; PREINSTALL: kill any running instance (old versions could linger in the
;   background; a locked exe would break the upgrade) - combined with Tauri's
;   built-in previous-version uninstall, this makes "install new over old"
;   fully automatic: old app closed, old files removed, new files in.
; POSTINSTALL: desktop shortcut (removed again on uninstall).
; PREUNINSTALL: also kill running instances so uninstall never hits
;   file-in-use, and clean up the shortcut.
;
; ${PRODUCTNAME} / ${MAINBINARYNAME} are defined by Tauri's template.

!macro NSIS_HOOK_PREINSTALL
  DetailPrint "Closing running Nitro Forge instances..."
  nsExec::Exec 'taskkill /F /T /IM "nitro-forge.exe"'
  nsExec::Exec 'taskkill /F /T /IM "nitro-forge-sidecar.exe"'
  Sleep 400
!macroend

!macro NSIS_HOOK_POSTINSTALL
  CreateShortcut "$DESKTOP\${PRODUCTNAME}.lnk" "$INSTDIR\${MAINBINARYNAME}.exe"
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  nsExec::Exec 'taskkill /F /T /IM "nitro-forge.exe"'
  nsExec::Exec 'taskkill /F /T /IM "nitro-forge-sidecar.exe"'
  Sleep 400
  Delete "$DESKTOP\${PRODUCTNAME}.lnk"
!macroend
