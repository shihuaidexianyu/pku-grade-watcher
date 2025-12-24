"""
通知模块 - 支持 SMTP 邮件与控制台通知。
"""

import smtplib
import ssl
from abc import ABC, abstractmethod
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any

from models import Course


class BaseNotifier(ABC):
    """通知器基类"""
    
    @abstractmethod
    def send(self, title: str, content: str, course: Optional[Course] = None) -> bool:
        """
        发送通知
        
        Args:
            title: 通知标题
            content: 通知内容
            course: 相关课程信息（可选）
            
        Returns:
            bool: 发送是否成功
        """
        pass


class EmailNotifier(BaseNotifier):
    """邮件通知器"""
    
    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
        to_email: str,
        security: str = "starttls",
        timeout: int = 20,
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.to_email = to_email
        self.security = (security or "starttls").lower()
        self.timeout = timeout
    
    def send(self, title: str, content: str, course: Optional[Course] = None) -> bool:
        """发送邮件通知"""
        try:
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = self.to_email
            msg['Subject'] = title
            
            # 构建邮件内容
            email_content = self._build_email_content(content, course)
            msg.attach(MIMEText(email_content, 'html', 'utf-8'))
            
            # 发送邮件
            # security:
            # - starttls: 先建立明文连接再升级 TLS（常见 587）
            # - ssl: 直接 SSL/TLS（常见 465）
            # - plain: 不加密（不推荐，仅用于内网/调试）
            if self.security == "ssl":
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    self.smtp_server,
                    self.smtp_port,
                    timeout=self.timeout,
                    context=context,
                ) as server:
                    server.login(self.username, self.password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(
                    self.smtp_server,
                    self.smtp_port,
                    timeout=self.timeout,
                ) as server:
                    server.ehlo()
                    if self.security == "starttls":
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                        server.ehlo()
                    server.login(self.username, self.password)
                    server.send_message(msg)
            
            print(f"邮件通知发送成功: {title}")
            return True
            
        except Exception as e:
            print(f"邮件通知发送失败: {e}")
            return False
    
    def _build_email_content(self, content: str, course: Optional[Course] = None) -> str:
        """构建邮件HTML内容"""

        # 邮件客户端对 CSS 支持差异很大，因此尽量使用“内联样式 + 结构简单”的方式。
        # 这里做成卡片式布局，在移动端和桌面端都更易读。
        html_template = """
                <!doctype html>
                <html lang="zh-CN">
                <head>
                    <meta charset="utf-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1" />
                    <meta name="color-scheme" content="light dark" />
                    <title>北大成绩监控通知</title>
                </head>
                <body style="margin:0;padding:0;background:#f5f7fb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;color:#111827;">
                    <div style="max-width:680px;margin:0 auto;padding:24px 12px;">
                        <div style="padding:14px 18px;border-radius:14px;background:linear-gradient(135deg,#2563eb,#7c3aed);color:#ffffff;">
                            <div style="font-size:14px;opacity:0.95;letter-spacing:0.2px;">PKU Grade Watcher</div>
                            <div style="font-size:22px;font-weight:700;margin-top:6px;line-height:1.25;">北大成绩监控通知</div>
                        </div>

                        <div style="margin-top:14px;background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;box-shadow:0 10px 30px rgba(17,24,39,0.08);overflow:hidden;">
                            <div style="padding:16px 18px 6px 18px;">
                                <div style="font-size:13px;color:#6b7280;margin-bottom:10px;">通知内容</div>
                                <div style="font-size:15px;line-height:1.75;white-space:pre-wrap;word-break:break-word;">{content}</div>
                            </div>

                            {course_details}

                            <div style="padding:14px 18px;border-top:1px solid #e5e7eb;background:#fbfdff;">
                                <div style="font-size:12px;color:#6b7280;line-height:1.6;">
                                    凡我不能创造的，我就不能理解。 -- 理查德·费曼<br/>
                                    希望你继续保持对知识的渴望与热爱！<br/>
                                </div>
                            </div>
                        </div>

                        <div style="margin-top:10px;text-align:center;font-size:12px;color:#9ca3af;">
                            © PKU Grade Watcher
                        </div>
                    </div>
                </body>
                </html>
                """

        course_details = ""
        if course:
            # 课程详情：使用更适配邮件客户端的“伪表格”布局（仍保留 table 结构）。
            def _safe(v: object) -> str:
                return "" if v is None else str(v)

            course_details = f"""
                            <div style=\"padding:0 18px 16px 18px;\">
                                <div style=\"margin-top:10px;padding-top:10px;border-top:1px solid #eef2f7;\"></div>
                                <div style=\"display:flex;align-items:center;gap:10px;\">
                                    <div style=\"width:10px;height:10px;border-radius:999px;background:#10b981;\"></div>
                                    <div style=\"font-size:13px;color:#6b7280;\">课程详情</div>
                                </div>
                                <div style=\"margin-top:10px;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;\">
                                    <table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" style=\"width:100%;border-collapse:separate;border-spacing:0;\">
                                        <tr style=\"background:#f9fafb;\">
                                            <td style=\"padding:10px 12px;font-size:13px;color:#374151;width:34%;border-bottom:1px solid #e5e7eb;\"><strong>课程名称</strong></td>
                                            <td style=\"padding:10px 12px;font-size:13px;color:#111827;border-bottom:1px solid #e5e7eb;\">{_safe(course.course_name)}</td>
                                        </tr>
                                        <tr>
                                            <td style=\"padding:10px 12px;font-size:13px;color:#374151;background:#f9fafb;border-bottom:1px solid #e5e7eb;\"><strong>成绩</strong></td>
                                            <td style=\"padding:10px 12px;font-size:13px;color:#111827;border-bottom:1px solid #e5e7eb;\">{_safe(course.grade)}</td>
                                        </tr>
                                        <tr style=\"background:#ffffff;\">
                                            <td style=\"padding:10px 12px;font-size:13px;color:#374151;background:#f9fafb;border-bottom:1px solid #e5e7eb;\"><strong>绩点</strong></td>
                                            <td style=\"padding:10px 12px;font-size:13px;color:#111827;border-bottom:1px solid #e5e7eb;\">{_safe(course.gpa)}</td>
                                        </tr>
                                        <tr>
                                            <td style=\"padding:10px 12px;font-size:13px;color:#374151;background:#f9fafb;border-bottom:1px solid #e5e7eb;\"><strong>学分</strong></td>
                                            <td style=\"padding:10px 12px;font-size:13px;color:#111827;border-bottom:1px solid #e5e7eb;\">{_safe(course.credit)}</td>
                                        </tr>
                                        <tr>
                                            <td style=\"padding:10px 12px;font-size:13px;color:#374151;background:#f9fafb;\"><strong>学期</strong></td>
                                            <td style=\"padding:10px 12px;font-size:13px;color:#111827;\">{_safe(course.term)}</td>
                                        </tr>
                                    </table>
                                </div>
                            </div>
                        """
        
        return html_template.format(content=content, course_details=course_details)


class ConsoleNotifier(BaseNotifier):
    """控制台通知器（用于测试）"""
    
    def send(self, title: str, content: str, course: Optional[Course] = None) -> bool:
        """在控制台输出通知"""
        print(f"\n{'='*50}")
        print(f"通知标题: {title}")
        print(f"通知内容: {content}")
        if course:
            print(f"课程信息: {course.course_name} - {course.grade}")
        print(f"{'='*50}\n")
        return True


class MultiNotifier(BaseNotifier):
    """多通道通知器 - 支持同时使用多种通知方式"""
    
    def __init__(self):
        self.notifiers = []
    
    def add_notifier(self, notifier: BaseNotifier):
        """添加通知器"""
        self.notifiers.append(notifier)
    
    def send(self, title: str, content: str, course: Optional[Course] = None) -> bool:
        """发送通知到所有注册的通知器"""
        success_count = 0
        
        for notifier in self.notifiers:
            try:
                if notifier.send(title, content, course):
                    success_count += 1
            except Exception as e:
                print(f"通知器 {type(notifier).__name__} 发送失败: {e}")
        
        # 只要有一个成功就认为成功
        return success_count > 0


def create_notifier_from_config(config: Dict[str, Any]) -> Optional[BaseNotifier]:
    """根据配置创建通知器"""
    notifier_type = config.get('type', '').lower()

    if notifier_type == 'email' and all(k in config for k in
        ['smtp_server', 'smtp_port', 'email_username', 'email_password', 'from_email', 'to_email']):
        return EmailNotifier(
            smtp_server=config['smtp_server'],
            smtp_port=config['smtp_port'],
            username=config['email_username'],
            password=config['email_password'],
            from_email=config['from_email'],
            to_email=config['to_email'],
            security=config.get('smtp_security', 'starttls'),
            timeout=int(config.get('smtp_timeout', 20)),
        )
    
    elif notifier_type == 'console':
        return ConsoleNotifier()
    
    elif notifier_type == 'multi':
        multi_notifier = MultiNotifier()

        # 添加邮件通知
        if all(k in config for k in ['smtp_server', 'smtp_port', 'email_username', 
                                   'email_password', 'from_email', 'to_email']):
            multi_notifier.add_notifier(EmailNotifier(
                smtp_server=config['smtp_server'],
                smtp_port=config['smtp_port'],
                username=config['email_username'],
                password=config['email_password'],
                from_email=config['from_email'],
                to_email=config['to_email'],
                security=config.get('smtp_security', 'starttls'),
                timeout=int(config.get('smtp_timeout', 20)),
            ))

        # 可选：同时输出到控制台
        if config.get('console'):
            multi_notifier.add_notifier(ConsoleNotifier())
        
        return multi_notifier if multi_notifier.notifiers else None
    
    return None
