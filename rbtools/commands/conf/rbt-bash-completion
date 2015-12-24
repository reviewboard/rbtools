_rbt_get_all_commands()
{
    opts=""

    for opt in `rbt --help | grep -o "^  [A-Za-z\-]*\S"`
    do
        if [[ $opt != "command"* && $opt != "-"* ]]; then
            opts+=" ${opt}"
        fi
    done

    echo ${opts}
}

_rbt_commands()
{
    local cur opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    opts=$(_rbt_get_all_commands)

    if [ "$COMP_CWORD" -eq 1 ]; then
        COMPREPLY=( $(compgen -W "${opts}" -- ${cur}))
    else
        COMPREPLY=()
    fi

}
complete -o default -F _rbt_commands rbt