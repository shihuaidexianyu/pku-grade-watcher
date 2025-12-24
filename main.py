"""
北大成绩监控主程序
使用面向对象设计，支持课程去重和多种通知方式
"""

import sys
from pathlib import Path

import yaml

from grade_watcher import GradeWatcher
from notifier import create_notifier_from_config


def load_config(config_file: str = "config.yaml") -> dict:
    """加载配置文件"""
    config_path = Path(config_file)
    
    if not config_path.exists():
        print(f"配置文件 {config_file} 不存在，请参考 config_sample.yaml 创建配置文件")
        sys.exit(1)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
        return config
    except Exception as e:
        print(f"读取配置文件失败: {e}")
        sys.exit(1)


def validate_config(config: dict) -> bool:
    """验证配置文件"""
    required_fields = ["username", "password"]
    
    for field in required_fields:
        if not config.get(field):
            print(f"配置文件缺少必要字段: {field}")
            return False
    
    return True


def main():
    """主函数 - 执行完整的成绩监控工作流程"""
    # 加载配置
    config = load_config()
    
    # 验证配置
    if not validate_config(config):
        sys.exit(1)
    
    # 创建通知器
    notifier = create_notifier_from_config(config)
    if notifier:
        print("成功创建通知器")
    else:
        print("未配置通知器或配置无效，将不发送通知")
    
    # 创建成绩监控器
    # 网络请求超时配置：requests 默认可能无限等待，因此提供可选配置，避免“卡住”。
    timeout_cfg = config.get("request_timeout", None)
    request_timeout = (5.0, 20.0)
    try:
        if isinstance(timeout_cfg, (list, tuple)) and len(timeout_cfg) == 2:
            request_timeout = (float(timeout_cfg[0]), float(timeout_cfg[1]))
        elif isinstance(timeout_cfg, (int, float)):
            # 兼容写法：单个数字表示 read timeout；connect timeout 仍取 5s
            request_timeout = (5.0, float(timeout_cfg))
    except Exception:
        # 配置错误时用默认值
        request_timeout = (5.0, 20.0)

    watcher = GradeWatcher(
        username=config["username"],
        password=config["password"],
        notifier=notifier,
        data_file=config.get("data_file", "course_data.json"),
        request_timeout=request_timeout,
        debug_http=bool(config.get("debug_http", False)),
    )
    
    # 执行完整工作流程
    try:
        success = watcher.run_full_workflow()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{'[中断]':<15}: 用户中断程序")
        sys.exit(1)
    except Exception as e:
        print(f"{'[错误]':<15}: 程序执行出错 - {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
