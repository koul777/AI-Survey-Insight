from __future__ import annotations

import argparse
from pathlib import Path

from openpyxl import Workbook

from .exports import export_excel, export_powerpoint, export_word
from .pipeline import analyze_file, write_analysis_package


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Survey Insight MVP CLI")
    sub = parser.add_subparsers(dest="command")
    demo = sub.add_parser("demo", help="Create a PRD-like fixture and export reports")
    demo.add_argument("--out", default="out", help="Output directory")
    analyze = sub.add_parser("analyze", help="Analyze an existing XLSX/CSV file")
    analyze.add_argument("--input", required=True)
    analyze.add_argument("--out", default="out")
    analyze.add_argument("--project-name", default="Survey Insight Project")
    analyze.add_argument("--text-column")
    analyze.add_argument("--group-column", action="append", default=[])
    args = parser.parse_args()
    if args.command == "analyze":
        _analyze(args)
    else:
        _demo(args)


def _demo(args: argparse.Namespace) -> None:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    workbook_path = out_dir / "demo_survey.xlsx"
    create_demo_workbook(workbook_path)
    package = analyze_file(workbook_path, project_name="AI Survey Insight Demo")
    _write_outputs(package, out_dir)
    print(f"Demo workbook: {workbook_path}")
    print(f"Analysis package: {out_dir / 'analysis_package.json'}")
    print(f"Excel report: {out_dir / 'survey_insight_report.xlsx'}")
    print(f"Word report: {out_dir / 'survey_insight_report.docx'}")
    print(f"PowerPoint report: {out_dir / 'survey_insight_report.pptx'}")


def _analyze(args: argparse.Namespace) -> None:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    package = analyze_file(
        args.input,
        project_name=args.project_name,
        text_column=args.text_column,
        group_columns=args.group_column or None,
    )
    _write_outputs(package, out_dir)
    print(f"Analysis package: {out_dir / 'analysis_package.json'}")
    print(f"Excel report: {out_dir / 'survey_insight_report.xlsx'}")
    print(f"Word report: {out_dir / 'survey_insight_report.docx'}")
    print(f"PowerPoint report: {out_dir / 'survey_insight_report.pptx'}")


def _write_outputs(package, out_dir: Path) -> None:
    write_analysis_package(package, out_dir / "analysis_package.json")
    export_excel(package, out_dir / "survey_insight_report.xlsx")
    export_word(package, out_dir / "survey_insight_report.docx")
    export_powerpoint(package, out_dir / "survey_insight_report.pptx")


def create_demo_workbook(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Responses"
    headers = [
        "응답ID",
        "응답일시",
        "부서",
        "직종",
        "근속연수",
        "만족도",
    ]
    headers.extend([f"문항_{i:02d}" for i in range(1, 57)])
    headers.append("15. 인사제도 개선을 위한 기타 건의 사항 [의견]")
    ws.append(headers)
    responses = [
        "승진 기준과 평가 기준이 더 투명하게 공유되면 좋겠습니다.",
        "부서 이동 신청 절차가 복잡해서 개선이 필요합니다.",
        "교육 기회가 직무별로 고르게 제공되면 좋겠습니다.",
        "평가 피드백이 늦게 전달되어 다음 업무에 반영하기 어렵습니다.",
        "육아와 병행할 수 있는 유연근무 제도가 더 확대되면 좋겠습니다.",
        "보상 기준이 명확하지 않아 구성원들이 납득하기 어렵습니다.",
        "인사 발령 공지가 갑작스러워 업무 인수인계 시간이 부족합니다.",
        "직급별 교육보다 실제 업무 역량 중심의 교육이 필요합니다.",
        "평가자가 바뀔 때 기준이 달라지는 문제가 있습니다.",
        "성과급 산정 방식과 근거를 더 자세히 안내해 주세요.",
        "휴가 사용 눈치가 있어 제도는 있지만 활용하기 어렵습니다.",
        "팀 간 이동 기회를 정기적으로 공지하면 좋겠습니다.",
        "관리자 리더십 교육이 강화되면 조직문화가 개선될 것 같습니다.",
        "신규 입사자 온보딩 자료와 멘토링이 더 체계적이면 좋겠습니다.",
        "평가 면담 시간이 짧아 실질적인 피드백을 받기 어렵습니다.",
        "사번 20260001 직원처럼 개인 정보가 의견에 들어갈 때는 가려 주세요.",
    ]
    for idx in range(94):
        row = [
            f"R{idx + 1:03d}",
            f"2026-06-{(idx % 28) + 1:02d} 09:00",
            ["HR", "Finance", "Sales", "IT"][idx % 4],
            ["사무직", "기술직", "관리직"][idx % 3],
            ["1년 미만", "1-3년", "3-5년", "5년 이상"][idx % 4],
            (idx % 5) + 1,
        ]
        row.extend([(idx + j) % 5 + 1 for j in range(56)])
        row.append(responses[idx] if idx < len(responses) else ["", "없음", ".", "해당없음"][idx % 4])
        ws.append(row)
    wb.save(path)


if __name__ == "__main__":
    main()
