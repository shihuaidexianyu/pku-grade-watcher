"""通知模块 - 支持 SMTP 邮件与控制台通知。

已移除 Bark 推送。
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
        html_template = """
        <html>
        <body>
            <h2>北大成绩监控通知</h2>
            <p>{content}</p>
            {course_details}
            <hr>
            <p><small>本邮件由北大成绩监控系统自动发送</small></p>
        </body>
        </html>
        """
        
        course_details = ""
        if course:
            course_details = f"""
            <h3>课程详情</h3>
            <table border="1" style="border-collapse: collapse;">
                <tr><td><strong>课程名称</strong></td><td>{course.course_name}</td></tr>
                <tr><td><strong>成绩</strong></td><td>{course.grade}</td></tr>
                <tr><td><strong>绩点</strong></td><td>{course.gpa}</td></tr>
                <tr><td><strong>学分</strong></td><td>{course.credit}</td></tr>
                <tr><td><strong>学期</strong></td><td>{course.term}</td></tr>
            </table>
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
