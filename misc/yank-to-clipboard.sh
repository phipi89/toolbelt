copy-and-clear-line() {
  echo -n "$BUFFER" | pbcopy && exit
  BUFFER=""
  zle redisplay
}

zle -N copy-and-clear-line
bindkey '^X' copy-and-clear-line


move-to-editor() {
  echo -n "$BUFFER" | subl && exit
  BUFFER=""
  zle redisplay
}

zle -N move-to-editor
bindkey '^T' move-to-editor
