"""
课程数据模型定义
"""

import json
from typing import Dict, Set, List, Optional
import math
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class Course:
    """课程数据模型"""

    course_id: str  # 课程ID (bkcjbh)
    course_name: str  # 课程名称 (kcmc)
    grade: str  # 成绩 (xqcj)
    gpa: str  # 绩点 (jd)
    term: str  # 学期
    credit: str = ""  # 学分
    course_type: str = ""  # 课程类型

    def __hash__(self):
        """使用课程ID和学期作为哈希值，支持重复修读"""
        return hash((self.course_id, self.term))

    def __eq__(self, other):
        """判断两个课程是否相同，基于课程ID和学期"""
        if not isinstance(other, Course):
            return False
        return self.course_id == other.course_id and self.term == other.term

    def get_unique_key(self) -> str:
        """获取课程的唯一标识，支持重复修读"""
        return f"{self.course_id}_{self.term}"

    def has_grade_update(self, other: "Course") -> bool:
        """检查是否有成绩更新"""
        if not isinstance(other, Course):
            return False
        return (
            self.course_id == other.course_id
            and self.term == other.term
            and (self.grade != other.grade or self.gpa != other.gpa)
        )

    def to_dict(self):
        """转换为字典格式"""
        return asdict(self)

    @staticmethod
    def _parse_numeric_grade(grade: str) -> Optional[float]:
        """把成绩字符串解析为数值分数。

        - 支持整数/小数，如 "92"、"92.5"
        - 对 "合格"/"通过" 等非数值成绩返回 None
        """
        if grade is None:
            return None
        s = str(grade).strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None

    @staticmethod
    def gpa_from_grade(x: float) -> float:
        """按公式计算 GPA。

        GPA(x) = 4 - 3 * (100 - x)^2 / 1600
        """
        return 4.0 - 3.0 * ((100.0 - float(x)) ** 2) / 1600.0

    def ensure_gpa(self, precision: int = 3) -> bool:
        """若 gpa 为空且成绩可解析为数值，则按公式补全 gpa。

        Returns:
            bool: 是否发生了写入/变更。
        """
        current = "" if self.gpa is None else str(self.gpa).strip()
        if current:
            return False

        x = self._parse_numeric_grade(self.grade)
        if x is None:
            return False

        gpa_val = self.gpa_from_grade(x)

        # 常见约束：GPA 通常落在 [0, 4]。公式在极端分数下可能小于 0。
        # 这里做一个温和的截断，避免出现负数。
        gpa_val = min(4.0, max(0.0, gpa_val))

        if not math.isfinite(gpa_val):
            return False

        # 存储为字符串，保持与现有 JSON 结构一致
        self.gpa = f"{gpa_val:.{int(precision)}f}".rstrip("0").rstrip(".")
        return True

    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建课程对象"""
        return cls(
            course_id=data.get("course_id", ""),
            course_name=data.get("course_name", ""),
            grade=data.get("grade", ""),
            gpa=data.get("gpa", ""),
            term=data.get("term", ""),
            credit=data.get("credit", ""),
            course_type=data.get("course_type", ""),
        )

    @classmethod
    def from_raw_data(cls, raw_course: dict, term: str = ""):
        """从原始API数据创建课程对象"""
        return cls(
            course_id=raw_course.get("bkcjbh", ""),
            course_name=raw_course.get("kcmc", ""),
            grade=raw_course.get("xqcj", ""),
            gpa=raw_course.get("jd", ""),
            term=term,
            credit=raw_course.get("xf", ""),
            course_type=raw_course.get(
                "kctx", ""
            ),  # 课程类型，如"专业必修"、"通选课"等
        )


class CourseManager:
    """课程管理器，使用字典进行课程管理，支持重复修读"""

    def __init__(self, data_file: str = "course_data.json"):
        self.data_file = Path(data_file)
        # 使用字典存储课程，key为课程的唯一标识(course_id_term)，value为Course对象
        self.courses: Dict[str, Course] = {}

    def initialize_from_file(self) -> bool:
        """从文件初始化课程数据"""
        if not self.data_file.exists():
            print(f"数据文件 {self.data_file} 不存在，初始化为空字典")
            return False

        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            courses_data = data.get("courses", [])
            for course_data in courses_data:
                course = Course.from_dict(course_data)
                unique_key = course.get_unique_key()
                self.courses[unique_key] = course

            print(f"成功从文件加载 {len(self.courses)} 门课程")
            return True

        except Exception as e:
            print(f"从文件加载课程数据时出错: {e}")
            return False

    def add_course(self, course: Course) -> tuple[bool, str]:
        """
        尝试添加新课程或更新已有课程

        Args:
            course: 要添加的课程对象

        Returns:
            tuple[bool, str]: (是否需要通知, 变化类型: 'new'|'updated'|'no_change')
        """
        unique_key = course.get_unique_key()
        existing_course = self.courses.get(unique_key)

        if existing_course is None:
            # 新课程
            self.courses[unique_key] = course
            return True, "new"
        else:
            # 检查是否有成绩更新
            if course.has_grade_update(existing_course):
                # 有成绩更新
                self.courses[unique_key] = course
                return True, "updated"
            else:
                # 无变化
                return False, "no_change"

    def get_course_by_key(self, course_id: str, term: str = None) -> Optional[Course]:
        """根据课程ID和学期获取课程"""
        if term:
            unique_key = f"{course_id}_{term}"
            return self.courses.get(unique_key)
        else:
            # 如果没有指定学期，返回最新的课程记录
            matching_courses = [
                course
                for key, course in self.courses.items()
                if course.course_id == course_id
            ]
            if matching_courses:
                # 按学期排序，返回最新的
                return sorted(matching_courses, key=lambda x: x.term, reverse=True)[0]
            return None

    def get_all_courses_for_id(self, course_id: str) -> List[Course]:
        """获取某个课程ID的所有修读记录（支持重复修读）"""
        return [
            course for course in self.courses.values() if course.course_id == course_id
        ]

    def save_to_file(self) -> bool:
        """将当前课程字典保存到文件"""
        try:
            # 创建备份
            if self.data_file.exists():
                backup_file = self.data_file.with_suffix(".json.bak")
                self.data_file.rename(backup_file)

            data = {
                "courses": [course.to_dict() for course in self.courses.values()],
                "total_count": len(self.courses),
            }

            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"成功保存 {len(self.courses)} 门课程到文件")
            return True

        except Exception as e:
            print(f"保存课程数据到文件时出错: {e}")
            # 如果保存失败，尝试恢复备份
            backup_file = self.data_file.with_suffix(".json.bak")
            if backup_file.exists():
                backup_file.rename(self.data_file)
            return False

    def get_all_courses(self) -> List[Course]:
        """获取所有课程列表"""
        return list(self.courses.values())

    def ensure_all_gpa(self, precision: int = 3) -> int:
        """为所有课程补齐 GPA（若可从数值成绩计算）。

        Returns:
            int: 被补齐/更新的课程数量。
        """
        updated = 0
        for course in self.courses.values():
            if course.ensure_gpa(precision=precision):
                updated += 1
        return updated

    def get_course_by_id(self, course_id: str) -> Optional[Course]:
        """根据课程ID获取课程（向后兼容，返回最新记录）"""
        return self.get_course_by_key(course_id)

    def get_courses_count(self) -> int:
        """获取课程总数"""
        return len(self.courses)

    def clear(self):
        """清空所有课程数据"""
        self.courses.clear()
