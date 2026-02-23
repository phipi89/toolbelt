diskusage() {
  if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    echo "usage: diskusage [PATH|GLOB ...]"
    echo "  list directory content or all glob results sorted by size in human readable form."
    return 0
  fi

  if [ "$#" -eq 1 ] && [ -d "$1" ]; then
    du -sh "$1"
    echo
    du -sh "$1"/* "$1"/.* 2>/dev/null | sort -hr
  else
    du -sh "$@" 2>/dev/null | sort -hr
  fi
}
