pynit() {
    echo "…creating directory $1"
    echo "…initializing project"
    uv init --bare --no-workspace "$1" >/dev/null 2>&1
    cd "$1"
    echo "…installing libraries"
    uv add scipy matplotlib tqdm >/dev/null 2>&1
    echo "…done."
}

nbinit() {
    pynit()
    uv add jupyter >/dev/null 2>&1
    uv run jupyter lab --log-level=WARN
}

alias pyinit=pynit


pytemp() {
    dir=$(mktemp -d)
    cd "$dir"
    pynit "temp_env"
}

nbtemp() {
    dir=$(mktemp -d)
    cd "$dir"
    nbinit "temp_env"
}