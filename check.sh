#!/usr/bin/env bash

# 适用于 crontab 的运行脚本：
# - 使用脚本所在目录作为项目目录（避免写死路径）
# - 使用 uv 管理依赖并运行项目（uv sync 后可直接运行）
# - 使用 flock 防止定时任务重叠执行

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

timestamp() {
	date "+%Y-%m-%d %H:%M:%S"
}

echo "[$(timestamp)] [check.sh] start: ${PROJECT_DIR}"

# 尽量找到 uv：cron 下 PATH 可能很短
UV_BIN="${UV_BIN:-}"
if [[ -z "${UV_BIN}" ]]; then
	if command -v uv >/dev/null 2>&1; then
		UV_BIN="$(command -v uv)"
	elif [[ -x "$HOME/.local/bin/uv" ]]; then
		UV_BIN="$HOME/.local/bin/uv"
	else
		echo "[$(timestamp)] [check.sh] ERROR: 找不到 uv，请确保已安装并在 cron 的 PATH 中，或在 crontab 里设置 UV_BIN。" >&2
		exit 127
	fi
fi

LOCK_FILE="${LOCK_FILE:-${PROJECT_DIR}/.check.lock}"

# 若系统没有 flock，就退化为无锁执行（仍可运行）
if command -v flock >/dev/null 2>&1; then
	exec 9>"$LOCK_FILE"
	if ! flock -n 9; then
		echo "[$(timestamp)] [check.sh] another run is in progress, exit"
		exit 0
	fi
fi

# 可选：如你希望 cron 每次都确保依赖已同步，可取消注释下一行（通常不需要每次都 sync）
# "$UV_BIN" sync

"$UV_BIN" run python main.py

echo "[$(timestamp)] [check.sh] done"
