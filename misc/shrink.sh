shrink() {
  local mode="balanced"
  local -a files
  local argument

  for argument in "$@"; do
    case "$argument" in
      --minimal) mode="minimal" ;;
      --balanced) mode="balanced" ;;
      -h|--help)
        echo "usage: shrink [--minimal|--balanced] INPUT.pdf [OUTPUT.pdf]"
        echo "  make a smaller PDF; --balanced is the default for clearer images."
        echo "  --minimal gives the smallest practical file."
        return 0
        ;;
      --*)
        echo "shrink: unknown option: $argument" >&2
        return 2
        ;;
      *) files+=("$argument") ;;
    esac
  done

  if (( ${#files[@]} < 1 || ${#files[@]} > 2 )); then
    echo "usage: shrink [--minimal|--balanced] INPUT.pdf [OUTPUT.pdf]" >&2
    return 2
  fi

  local input="${files[1]}"
  local output="${files[2]:-${input:r}_small.${input:e}}"
  if [[ ! -f "$input" ]]; then
    echo "shrink: file not found: $input" >&2
    return 1
  fi
  if [[ "${input:e:l}" != "pdf" ]]; then
    echo "shrink: currently supports PDF files only: $input" >&2
    return 1
  fi
  if [[ -e "$output" ]]; then
    echo "shrink: output already exists: $output" >&2
    return 1
  fi
  if ! command -v gs >/dev/null; then
    echo "shrink: Ghostscript (gs) is required" >&2
    return 1
  fi

  local quality="/screen"
  if [[ "$mode" == "balanced" ]]; then
    quality="/ebook"
  fi

  local before after change description
  before=$(stat -f %z "$input") || return 1
  if ! gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS="$quality" \
    -dNOPAUSE -dQUIET -dBATCH -sOutputFile="$output" "$input"; then
    rm -f "$output"
    return 1
  fi
  after=$(stat -f %z "$output") || return 1
  if (( after <= before )); then
    change=$(( (before - after) * 100 / before ))
    description="${change}% smaller"
  else
    change=$(( (after - before) * 100 / before ))
    description="${change}% larger"
  fi
  echo "Created $output ($(du -h "$output" | cut -f1), ${description})."
}

gshrink() {
  if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    echo "usage: gshrink [--minimal|--balanced] [OUTPUT.pdf]"
    echo "  shrink the file selected in the frontmost Finder window."
    return 0
  fi

  local selected
  selected=$(_finderctl selected-file) || return 1
  shrink "$selected" "$@"
}
