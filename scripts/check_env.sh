#!/usr/bin/env bash
set -u

# P1-T01 environment gate. This script is intentionally read-only: it reports
# the host tools and versions but does not install packages or alter the repo.

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
lock_file="$repo_root/config/tool_versions.env"
json=0
if [ "${1:-}" = "--json" ]; then
    json=1
fi

tools=(qemu-system-arm arm-none-eabi-gcc python3 cmake make)
optional_tools=(ollama)
failed=0

if [ "$json" -eq 0 ]; then
    echo "Environment check for freertos-local-llm-debugger"
    echo "Repository: $repo_root"
fi

report_tool() {
    local name="$1"
    local required="$2"
    local path=""
    local version="missing"

    if path="$(command -v "$name" 2>/dev/null)"; then
        case "$name" in
            qemu-system-arm) version="$("$name" --version 2>/dev/null | head -n 1)" ;;
            arm-none-eabi-gcc) version="$("$name" --version 2>/dev/null | head -n 1)" ;;
            python3) version="$("$name" --version 2>/dev/null)" ;;
            cmake) version="$("$name" --version 2>/dev/null | head -n 1)" ;;
            make) version="$("$name" --version 2>/dev/null | head -n 1)" ;;
            ollama) version="$("$name" --version 2>/dev/null | head -n 1)" ;;
        esac
    elif [ "$required" = "required" ]; then
        failed=1
    fi

    if [ "$json" -eq 1 ]; then
        printf '{"tool":"%s","required":%s,"path":"%s","version":"%s"}\n' \
            "$name" "$([ "$required" = required ] && echo true || echo false)" \
            "$path" "$version"
    else
        if [ -n "$path" ]; then
            printf '%-20s OK       %s\n  %s\n' "$name" "$path" "$version"
        elif [ "$required" = "required" ]; then
            printf '%-20s MISSING  required\n' "$name"
        else
            printf '%-20s MISSING  optional\n' "$name"
        fi
    fi
}

for tool in "${tools[@]}"; do
    report_tool "$tool" required
done
for tool in "${optional_tools[@]}"; do
    report_tool "$tool" optional
done

if [ -f "$lock_file" ]; then
    if [ "$json" -eq 0 ]; then
        echo "Version lock: $lock_file"
        # The lock is metadata only until concrete versions are recorded.
        sed -n '/^[A-Z_].*=/{p}' "$lock_file"
    fi
else
    failed=1
    if [ "$json" -eq 0 ]; then
        echo "Version lock: MISSING ($lock_file)"
    fi
fi

if [ "$json" -eq 0 ]; then
    if [ "$failed" -eq 0 ]; then
        echo "RESULT: PASS"
    else
        echo "RESULT: BLOCKED — install or expose required tools, then rerun"
    fi
fi
exit "$failed"
