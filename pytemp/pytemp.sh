pynit() {
    local target="${1:-.}"

    if [[ "$target" != "." ]]; then
        echo "…creating directory $target"
        mkdir -p "$target"
        cd "$target" || return
    fi

    echo "…initializing project"
    uv init --bare --no-workspace "$1" >/dev/null 2>&1

    echo "…installing libraries"
    uv add scipy matplotlib tqdm >/dev/null 2>&1
    echo "…done."
}

nbinit() {
    pynit $1
    cd $1
    uv add jupyter >/dev/null 2>&1
    uv run jupyter lab --log-level=WARN
}

alias pyinit=pynit


pytemp() {
    dir=$(mktemp -d)
    cd "$dir"
    pynit .
}

nbtemp() {
    dir=$(mktemp -d)
    cd "$dir"
    nbinit "temp_env"
}
