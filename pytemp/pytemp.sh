pynit() {
    local target="${1:-.}"
    local libraries=(scipy matplotlib tqdm)

    echo "…starting in $PWD"

    if [[ "$target" != "." ]]; then
        echo "…creating directory $target"
        mkdir -p "$target"
        echo "…entering directory $target"
        cd "$target" || return
    fi

    echo "…initializing project"
    if ! uv init --bare --no-workspace . >/dev/null 2>&1; then
        echo "…failed to initialize project"
        return 1
    fi

    echo "…installing libraries: ${libraries[*]}"
    if ! uv add "${libraries[@]}" >/dev/null 2>&1; then
        echo "…failed to install libraries"
        return 1
    fi
    echo "…project ready at $PWD"
    echo "…done."
}

nbinit() {
    pynit "$1" || return
    echo "…installing libraries: jupyter"
    uv add jupyter >/dev/null 2>&1 || return
    uv run jupyter lab --log-level=WARN
}

alias pyinit=pynit


pytemp() {
    local dir=$(mktemp -d)
    cd "$dir"
    pynit .
}

nbtemp() {
    local dir=$(mktemp -d)
    cd "$dir"
    nbinit "temp_env"
}
