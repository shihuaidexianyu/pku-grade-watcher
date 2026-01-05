"""One-off utility: fill missing `gpa` in course_data.json.

This repo originally relied on PKU API field `jd` (绩点). If the API stops returning it,
we compute GPA from numeric grades using:

    GPA(x) = 4 - 3 * (100 - x)^2 / 1600

Non-numeric grades like "合格" are left unchanged.
"""

from __future__ import annotations

import argparse

from models import CourseManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill missing GPA in an existing course_data.json")
    parser.add_argument("--data-file", default="course_data.json", help="Path to course_data.json")
    parser.add_argument("--precision", type=int, default=3, help="Decimal precision to keep")
    args = parser.parse_args()

    mgr = CourseManager(args.data_file)
    mgr.initialize_from_file()
    updated = mgr.ensure_all_gpa(precision=args.precision)
    if updated:
        mgr.save_to_file()
    print(f"[fill_gpa] updated courses: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
