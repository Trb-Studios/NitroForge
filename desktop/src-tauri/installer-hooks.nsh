; Custom NSIS installer hooks for Nitro Forge.
;
; Adds a Desktop shortcut on install and removes it on uninstall. Tauri runs
; these macros from its generated installer template, so ${PRODUCTNAME} and
; ${MAINBINARYNAME} are already defined.
;
; NOTE: this creates the desktop icon by default. Turning it into an opt-in
; checkbox needs a custom nsDialogs page (a future enhancement); creating +
; cleanly removing the shortcut is the reliable, self-contained baseline.

!macro NSIS_HOOK_POSTINSTALL
  CreateShortcut "$DESKTOP\${PRODUCTNAME}.lnk" "$INSTDIR\${MAINBINARYNAME}.exe"
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  Delete "$DESKTOP\${PRODUCTNAME}.lnk"
!macroend
