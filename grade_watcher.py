"""
成绩监控核心类
"""

import json
import os
import random
import re
from typing import List, Optional
from datetime import datetime
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from models import Course, CourseManager
from notifier import BaseNotifier


class GradeWatcher(requests.Session):
    """成绩监控器 - 负责数据获取和处理"""
    
    def __init__(self, username: str, password: str, notifier: Optional[BaseNotifier] = None,
                 data_file: str = "course_data.json",
                 request_timeout: tuple[float, float] = (5.0, 20.0),
                 debug_http: bool = False,
                 max_retries: int = 3,
                 backoff_factor: float = 0.6):
        super().__init__()
        self.username = username
        self.password = password
        self.notifier = notifier
        self.course_manager = CourseManager(data_file)
        self.is_first_run = False  # 标记是否是首次运行
        self.request_timeout = request_timeout
        self.debug_http = debug_http
        self.max_retries = int(max_retries)
        self.backoff_factor = float(backoff_factor)

        # 给 Session 配置连接池级别的重试：
        # - 对 502/503/504 等短暂服务异常自动重试
        # - 对 connect/read 阶段的短暂错误进行重试
        # 说明：这解决的是“网络/服务瞬时抖动导致偶发失败”的场景。
        retry = Retry(
            total=self.max_retries,
            connect=self.max_retries,
            read=self.max_retries,
            status=self.max_retries,
            status_forcelist=(429, 502, 503, 504),
            allowed_methods=("HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS"),
            backoff_factor=self.backoff_factor,
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        self.mount("https://", adapter)
        self.mount("http://", adapter)
        
        # 设置请求头
        self.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
            "TE": "Trailers",
            "Pragma": "no-cache",
            "Referer": "https://portal.pku.edu.cn/publicQuery/",
        })
    
    def __del__(self):
        self.close()
    
    def get(self, url, *args, **kwargs):
        """重写 get 方法，验证状态码"""
        return self._request_with_default_timeout("GET", url, *args, **kwargs)
    
    def post(self, url, *args, **kwargs):
        """重写 post 方法，验证状态码"""
        return self._request_with_default_timeout("POST", url, *args, **kwargs)

    def _request_with_default_timeout(self, method: str, url: str, *args, **kwargs):
        """统一给 requests 请求加默认 timeout，并在 debug 模式下打印关键信息。

        说明：requests 在不传 timeout 时可能无限等待，cron 场景下会表现为“卡住”。
        """
        if "timeout" not in kwargs or kwargs["timeout"] is None:
            kwargs["timeout"] = self.request_timeout

        start = time.monotonic()
        try:
            res = super().request(method, url, *args, **kwargs)
            res.raise_for_status()
            if self.debug_http:
                cost_ms = int((time.monotonic() - start) * 1000)
                final_url = getattr(res, "url", url)
                print(f"{'[HTTP]':<15}: {method} {url} -> {res.status_code} ({cost_ms}ms) {final_url}")
            return res
        except requests.exceptions.Timeout as e:
            cost_ms = int((time.monotonic() - start) * 1000)
            print(f"{'[HTTP]':<15}: {method} {url} 超时（{cost_ms}ms），可能是网络不通/代理问题/服务端缓慢。timeout={kwargs.get('timeout')}")
            raise
        except requests.exceptions.RequestException as e:
            # 即使不打开 debug_http，也输出最关键的失败信息（避免 cron 里只有“登录失败”）。
            cost_ms = int((time.monotonic() - start) * 1000)
            print(f"{'[HTTP]':<15}: {method} {url} 请求失败（{cost_ms}ms）: {e}")
            raise
    
    def initialize(self) -> bool:
        """
        步骤1: 读取已保存的数据构建类对象集合完成初始化
        
        Returns:
            bool: 初始化是否成功
        """
        print(f"{'[初始化]':<15}: 开始从文件加载课程数据...")
        
        success = self.course_manager.initialize_from_file()
        
        if success:
            count = self.course_manager.get_courses_count()
            print(f"{'[初始化]':<15}: 成功加载 {count} 门课程")
            self.is_first_run = False
        else:
            print(f"{'[初始化]':<15}: 文件不存在或为空，这是首次运行，将创建新的数据文件")
            self.is_first_run = True
            # 首次运行时发送初始化通知
            if self.notifier:
                self.notifier.send(
                    title="[成绩监控] 系统初始化",
                    content="北大成绩监控系统已成功初始化，开始监控您的成绩变化。"
                )
        
        return True
    
    def login(self) -> bool:
        """登录门户系统"""
        try:
            print(f"{'[登录]':<15}: 开始登录PKU门户...")
            
            # IAAA 登录
            login_response = self.post(
                "https://iaaa.pku.edu.cn/iaaa/oauthlogin.do",
                data={
                    "userName": self.username,
                    "appid": "portal2017",
                    "password": self.password,
                    "redirUrl": "https://portal.pku.edu.cn/portal2017/ssoLogin.do",
                    "randCode": "",
                    "smsCode": "",
                    "optCode": "",
                },
            ).json()
            
            if not login_response.get("success"):
                raise ValueError(f"登录失败: {login_response}")
            
            # 门户 token 验证
            self.get(
                "https://portal.pku.edu.cn/portal2017/ssoLogin.do",
                params={"_rand": random.random(), "token": login_response["token"]},
            )
            
            # 成绩查询重定向
            redirect_response = self.get(
                "https://portal.pku.edu.cn/portal2017/util/portletRedir.do?portletId=myscores"
            )
            
            # 获取鉴权 JSESSION ID
            jsessionid = re.search(r"jsessionid=([^#;]+)", redirect_response.url).group(1)
            self.cookies.set("JSESSIONID", jsessionid)
            
            print(f"{'[登录]':<15}: 登录成功")
            return True
            
        except Exception as e:
            print(f"{'[登录]':<15}: 登录失败 - {e}")
            return False
    
    def fetch_latest_grades(self) -> List[Course]:
        """
        步骤2: 获取最新的数据
        
        Returns:
            List[Course]: 最新的课程数据列表
        """
        try:
            print(f"{'[获取数据]':<15}: 开始获取最新成绩数据...")
            
            # 获取成绩数据
            response = self.get(
                "https://portal.pku.edu.cn/publicQuery/ctrl/topic/myScore/retrScores.do",
            ).json()
            
            # 保存原始数据（用于调试）
            with open("current.json", "w", encoding="utf-8") as f:
                json.dump(response, f, ensure_ascii=False, indent=4)
            
            # 解析课程数据
            courses = []
            total_courses = 0
            
            for term_data in response.get("cjxx", []):
                term_name = term_data.get("xq", "未知学期")
                
                for course_data in term_data.get("list", []):
                    total_courses += 1
                    
                    # 检查必要字段
                    if not course_data.get("bkcjbh"):
                        continue
                    
                    course = Course.from_raw_data(course_data, term_name)
                    courses.append(course)
            
            print(f"{'[获取数据]':<15}: 成功获取 {len(courses)} 门有效课程（总共 {total_courses} 条记录）")
            return courses
            
        except Exception as e:
            print(f"{'[获取数据]':<15}: 获取数据失败 - {e}")
            return []
    
    def process_new_data(self, new_courses: List[Course]) -> tuple[List[Course], List[Course]]:
        """
        步骤3: 逐条尝试向课程字典中加入新元素，如果成功，则触发通知流程
        
        Args:
            new_courses: 最新获取的课程列表
            
        Returns:
            tuple[List[Course], List[Course]]: (新增课程列表, 更新课程列表)
        """
        print(f"{'[处理数据]':<15}: 开始处理 {len(new_courses)} 门课程...")
        
        new_courses_list = []
        updated_courses_list = []
        
        for course in new_courses:
            # 新版接口可能不再返回 jd（绩点）；若为空且成绩为数值，则按公式补齐。
            # 这样本地 course_data.json 与通知内容都能带上 gpa。
            course.ensure_gpa()

            # 尝试添加到字典中
            should_notify, change_type = self.course_manager.add_course(course)
            
            if should_notify:
                if change_type == 'new':
                    new_courses_list.append(course)
                    # 首次运行时不发送新课程通知，避免大量通知
                    if not self.is_first_run:
                        self._send_course_notification(course, is_new=True)
                elif change_type == 'updated':
                    updated_courses_list.append(course)
                    # 成绩更新始终需要通知
                    self._send_course_notification(course, is_new=False)
        
        total_changes = len(new_courses_list) + len(updated_courses_list)
        if self.is_first_run:
            print(f"{'[处理数据]':<15}: 首次运行，加载了 {len(new_courses_list)} 门现有课程（未发送通知）")
        elif total_changes > 0:
            print(f"{'[处理数据]':<15}: 发现 {len(new_courses_list)} 门新课程，{len(updated_courses_list)} 门课程有更新")
        else:
            print(f"{'[处理数据]':<15}: 没有发现新的课程或更新")
        
        return new_courses_list, updated_courses_list
    
    def save_data(self) -> bool:
        """
        步骤4: 所有数据完成处理之后，读取类对象集合中的所有元素，将其保存在本地的文件中
        
        Returns:
            bool: 保存是否成功
        """
        print(f"{'[保存数据]':<15}: 开始保存课程数据到本地文件...")
        
        success = self.course_manager.save_to_file()
        
        if success:
            count = self.course_manager.get_courses_count()
            print(f"{'[保存数据]':<15}: 成功保存 {count} 门课程数据")
        else:
            print(f"{'[保存数据]':<15}: 保存失败")
        
        return success
    
    def _send_course_notification(self, course: Course, is_new: bool = True):
        """发送课程通知"""
        if not self.notifier:
            return
        
        try:
            if is_new:
                title = f"[成绩更新] 新增课程: {course.course_name}"
                content = f"发现新的课程成绩！\n课程：{course.course_name}\n学期：{course.term}\n成绩：{course.grade}\n绩点：{course.gpa}"
            else:
                title = f"[成绩更新] 课程更新: {course.course_name}"
                content = f"课程成绩有更新！\n课程：{course.course_name}\n学期：{course.term}\n成绩：{course.grade}\n绩点：{course.gpa}"
            
            self.notifier.send(title, content, course)
            
        except Exception as e:
            print(f"{'[通知]':<15}: 发送通知失败 - {e}")
    
    def run_full_workflow(self) -> bool:
        """运行完整的工作流程"""
        print(f"{'[开始]':<15}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        try:
            # 步骤1: 初始化
            if not self.initialize():
                print(f"{'[错误]':<15}: 初始化失败")
                return False
            
            # 登录
            if not self.login():
                print(f"{'[错误]':<15}: 登录失败")
                return False
            
            # 步骤2: 获取最新数据
            new_courses = self.fetch_latest_grades()
            if not new_courses:
                print(f"{'[错误]':<15}: 获取数据失败")
                return False
            
            # 步骤3: 处理新数据
            new_courses_list, updated_courses_list = self.process_new_data(new_courses)
            total_changes = len(new_courses_list) + len(updated_courses_list)
            
            # 步骤4: 保存数据
            if not self.save_data():
                print(f"{'[错误]':<15}: 保存数据失败")
                return False
            
            print("="*60)
            print(f"{'[完成]':<15}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'[统计]':<15}: 总课程 {len(new_courses)} 门，新增 {len(new_courses_list)} 门，更新 {len(updated_courses_list)} 门")
            
            return True
            
        except Exception as e:
            print(f"{'[错误]':<15}: 工作流程执行失败 - {e}")
            return False
