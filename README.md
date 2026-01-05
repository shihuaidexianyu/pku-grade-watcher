# 北京大学成绩监控工具

一个自动监控北京大学学生成绩变化并发送通知的 Python 工具。

## 特性

- **自动监控**: 定期检查成绩更新
- **多种通知方式**: 支持 SMTP 邮件通知、控制台输出
- **智能去重**: 自动处理重复修读的课程
- **详细记录**: 记录历史成绩数据和变化
- **易于配置**: 基于 YAML 的简单配置
- **安全可靠**: 本地存储，保护隐私
- **定时运行**: 支持 crontab 定时任务

## 快速开始

### 环境要求

- Python 3.7+
- 网络连接

### 安装依赖

推荐使用 `uv` 管理依赖和虚拟环境。

```bash
# 克隆项目
git clone <repository-url>
cd pku-grade-watcher

# 安装/同步依赖（会在项目下创建 .venv）
uv sync
```

### 配置设置

1. 复制配置模板：

```bash
cp config_sample.yaml config.yaml
```

1. 编辑 `config.yaml` 文件，填入您的信息：

```yaml
# 北大成绩监控配置文件

# 登录信息（必需）
username: 2100000000  # 您的学号
password: your_password      # 您的密码

# 数据文件路径（可选，默认为 course_data.json）
data_file: course_data.json

# 通知配置
# 支持的通知类型：email, console, multi

# 方式1: SMTP 邮件通知（推荐）
type: email
smtp_server: smtp.qq.com
smtp_port: 587
smtp_security: starttls   # starttls | ssl | plain
smtp_timeout: 20          # 秒（可选）
email_username: your_email@qq.com
email_password: your_app_password
from_email: your_email@qq.com
to_email: target@example.com

# 方式2: 同时使用多种通知方式（邮件 + 控制台）
# type: multi
# console: true
# smtp_server: smtp.qq.com
# smtp_port: 587
# smtp_security: starttls
# smtp_timeout: 20
# email_username: your_email@qq.com
# email_password: your_app_password
# from_email: your_email@qq.com
# to_email: target@example.com

# 方式3: 控制台输出（用于测试）
# type: console
```

### 运行程序

```bash
# 手动运行一次
uv run python main.py

# 或使用提供的脚本
./check.sh
```

也可以用脚本入口：

```bash
uv run pku-grade-watcher
```

## 通知方式配置

### 1. 邮件通知（SMTP）

支持各种邮箱服务商的 SMTP 服务。

```yaml
type: email
smtp_server: smtp.qq.com
smtp_port: 587
smtp_security: starttls   # starttls | ssl | plain
smtp_timeout: 20          # 秒（可选）
email_username: your_email@qq.com
email_password: your_app_password  # 使用应用专用密码
from_email: your_email@qq.com
to_email: target@example.com
```

#### 安全模式说明

- `starttls`：先明文连接再升级 TLS（常用 587）
- `ssl`：直接 SSL/TLS（常用 465）
- `plain`：不加密（不推荐，仅用于内网/调试）

### 2. 多种通知方式（邮件 + 控制台）

可以同时配置多种通知方式：

```yaml
type: multi
console: true
smtp_server: smtp.qq.com
smtp_port: 587
smtp_security: starttls
smtp_timeout: 20
email_username: your_email@qq.com
email_password: your_app_password
from_email: your_email@qq.com
to_email: target@example.com
```

### 3. 控制台输出

用于调试和测试：

```yaml
type: console
```

## 定时运行

### 使用 crontab

编辑 crontab：

```bash
crontab -e
```

添加定时任务（例如每小时检查一次）：

```bash
0 * * * * /home/hw/tasks/pku-grade-watcher/check.sh >> /home/hw/tasks/pku-grade-watcher/check.log 2>&1
```

如果你的 cron 环境里找不到 `uv`（PATH 很短），推荐在 crontab 顶部显式设置：

```bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
UV_BIN=/home/hw/.local/bin/uv
```

`check.sh` 默认会清理常见代理环境变量（`http_proxy/https_proxy/all_proxy` 等），避免代理导致教务系统请求或 SMTP 连接异常。
如果你确实需要代理访问外网，可以在 crontab 里加：

```bash
KEEP_PROXY=1
```

### 修改脚本路径

`check.sh` 已支持在 cron 环境下运行（自动定位项目目录、用 uv 运行、避免重复并发执行）。



##  安全说明

-  所有数据均存储在本地，不会上传到第三方服务器
-  密码仅用于登录教务系统，不会保存在明文日志中
-  支持配置文件权限控制，保护敏感信息
-  建议定期更改密码，并确保配置文件安全

##  功能说明

### 核心功能

1. **自动登录**: 使用学号和密码自动登录北大教务系统
2. **成绩获取**: 自动抓取最新的成绩信息
3. **智能对比**: 与历史数据对比，识别新增和更新的成绩
4. **去重处理**: 自动处理重复修读课程的成绩记录
5. **通知推送**: 当发现成绩变化时，立即发送通知

### 数据处理

- **课程去重**: 基于课程 ID 和学期进行去重，支持重复修读
- **增量更新**: 只处理新增或变化的成绩记录
- **历史记录**: 保留完整的成绩变化历史
- **数据备份**: 自动备份重要数据文件

##  故障排除

### 常见问题

1. **登录失败**
   - 检查学号和密码是否正确
   - 确认网络连接正常
   - 查看是否需要验证码（目前不支持验证码）

   如果程序卡在 `"[登录] : 开始登录PKU门户..."` 不动，通常是某个网络请求在等待。
   你可以在 `config.yaml` 中添加超时与调试输出，帮助判断是超时、网络不通、还是被重定向：

   ```yaml
   # (connect_timeout, read_timeout)
   request_timeout: [5, 20]
   debug_http: true
   ```

2. **通知发送失败**
   - 检查通知配置是否正确
   - 验证邮箱 SMTP、端口、安全模式与授权码是否正确
   - 查看网络连接是否正常

3. **定时任务不执行**
   - 检查 crontab 配置是否正确
   - 确认脚本路径和 Python 路径
   - 查看系统日志和程序日志
  
4. **log内容为无权限**
   - 使用下面的脚本赋予你的脚本执行权限

```bash
     chmod +x check.sh
```

### 调试方法

1. **手动运行**: 先手动运行程序，确认基本功能正常
2. **日志查看**: 检查 `check.log` 文件中的运行日志
3. **配置验证**: 使用控制台输出模式测试配置
4. **逐步调试**: 逐一测试登录、获取数据、通知等功能