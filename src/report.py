"""
报告生成模块
生成 Markdown / 终端 / HTML / PDF 格式的分析报告
"""

import os
import json
import html
import re
import math
import unicodedata
from typing import List, Optional, Dict, Any
from datetime import datetime

from .models import JobDetail, AnalysisResult
from .config import Config


class ReportGenerator:
    """分析报告生成器"""

    def __init__(self, config: Config):
        self.config = config

    def generate_markdown(self, result: AnalysisResult, jobs: List[JobDetail],
                          save: bool = True) -> str:
        """
        生成 Markdown 格式的分析报告

        Args:
            result: 分析结果
            jobs: 原始职位数据
            save: 是否保存到文件

        Returns:
            Markdown 文本
        """
        lines = []

        # 标题
        lines.append(f"# 🔍 Boss直聘职位分析报告")
        lines.append(f"")
        lines.append(f"> 搜索关键词: **{result.query}** | 职位总数: **{result.total_jobs}** | 分析时间: {result.analyzed_at}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # AI 分析
        if result.ai_insights:
            lines.append(result.ai_insights)
            lines.append("")
            lines.append("---")
            lines.append("")

        # 职位列表
        lines.append("## 📋 职位列表\n")
        lines.append("| # | 职位 | 公司 | 薪资 | 城市/区域 | 经验 | 学历 | 技能 |")
        lines.append("|---|------|------|------|-----------|------|------|------|")

        for i, job in enumerate(jobs, 1):
            skills_str = ", ".join(job.skills[:4])
            if len(job.skills) > 4:
                skills_str += "..."
            location = f"{job.city_name}/{job.area_district}" if job.area_district else job.city_name
            lines.append(
                f"| {i} | {job.job_name} | {job.company_name} | {job.salary_desc} | "
                f"{location} | {job.experience} | {job.education} | {skills_str} |"
            )

        lines.append("")
        lines.append("---")
        lines.append(f"*报告由 职探AI 自动生成 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        md_content = "\n".join(lines)

        if save:
            filepath = self._save_report(md_content, "md")
            print(f"📄 Markdown 报告已保存: {filepath}")

        return md_content

    def generate_console_report(self, result: AnalysisResult) -> str:
        """
        生成终端可读的简洁报告

        Returns:
            格式化文本
        """
        lines = []
        salary = result.salary_summary

        lines.append("")
        lines.append("=" * 60)
        lines.append(f"  📊 职位分析报告: {result.query}")
        lines.append(f"  共分析 {result.total_jobs} 个职位")
        lines.append("=" * 60)

        # 薪资
        lines.append("")
        lines.append("  💰 薪资概览")
        lines.append("  " + "-" * 40)
        if salary and "error" not in salary:
            lines.append(f"  平均薪资: {salary.get('avg_min_salary_k', '?')}K - {salary.get('avg_max_salary_k', '?')}K/月")
            lines.append(f"  中位数:   {salary.get('median_min_salary_k', '?')}K - {salary.get('median_max_salary_k', '?')}K/月")
            lines.append(f"  范围:     {salary.get('min_salary_k', '?')}K - {salary.get('max_salary_k', '?')}K/月")
            lines.append(f"  预计年薪: {salary.get('avg_annual_salary_k', '?')}K")

        # Top 技能
        lines.append("")
        lines.append("  🛠️  热门技能 Top 10")
        lines.append("  " + "-" * 40)
        for i, (skill, count) in enumerate(list(result.skill_summary.items())[:10], 1):
            bar = "█" * min(count, 20)
            lines.append(f"  {i:>2}. {skill:<15} {bar} ({count})")

        # Top 地区
        lines.append("")
        lines.append("  📍 热门地点 Top 5")
        lines.append("  " + "-" * 40)
        for loc, count in list(result.location_summary.items())[:5]:
            pct = round(count / result.total_jobs * 100, 1)
            lines.append(f"  • {loc}: {count}个 ({pct}%)")

        # 学历
        lines.append("")
        lines.append("  🎓 学历要求")
        lines.append("  " + "-" * 40)
        for edu, count in result.education_summary.items():
            pct = round(count / result.total_jobs * 100, 1)
            lines.append(f"  • {edu}: {count}个 ({pct}%)")

        lines.append("")
        lines.append("=" * 60)

        text = "\n".join(lines)
        print(text)
        return text

    def generate_html(self, result: AnalysisResult, jobs: List[JobDetail],
                      save: bool = True) -> str:
        """
        生成 HTML 格式的可视化报告

        Returns:
            HTML 文本
        """
        salary = result.salary_summary

        # 技能数据
        skill_labels = json.dumps(list(result.skill_summary.keys())[:15], ensure_ascii=False)
        skill_values = json.dumps(list(result.skill_summary.values())[:15])

        # 地区数据
        loc_labels = json.dumps(list(result.location_summary.keys())[:10], ensure_ascii=False)
        loc_values = json.dumps(list(result.location_summary.values())[:10])

        # 薪资分布
        sal_dist = salary.get("salary_distribution", {})
        sal_labels = json.dumps(list(sal_dist.keys()), ensure_ascii=False)
        sal_values = json.dumps(list(sal_dist.values()))

        # 六边形竞争力图（雷达）
        user_profile = result.user_profile or {}
        total_jobs = max(1, int(result.total_jobs or 0))
        skills_n = len(result.skill_summary or {})
        goals_n = len(user_profile.get("goals", []))
        strengths_n = len(user_profile.get("strengths", []))
        concerns_n = len(user_profile.get("concerns", []))
        exp_summary = result.experience_summary or {}
        edu_summary = result.education_summary or {}

        skill_match = min(100, int(skills_n / 12 * 100))
        salary_comp = min(100, int((result.salary_summary or {}).get("avg_annual_salary_k", 0) / 300 * 100))
        exp_fit = min(100, int(sum(exp_summary.values()) / total_jobs * 100))
        edu_fit = min(100, int(sum(edu_summary.values()) / total_jobs * 100))
        market_heat = min(100, int(total_jobs / 120 * 100))
        clarity = min(100, int((goals_n * 20 + strengths_n * 10 - concerns_n * 8) + 40))
        clarity = max(0, min(100, clarity))

        radar_labels = json.dumps(["Skill", "Salary", "ExpFit", "EduFit", "Heat", "Goal"])
        radar_values = json.dumps([skill_match, salary_comp, exp_fit, edu_fit, market_heat, clarity])

        # 职位表格
        job_rows = ""
        for i, job in enumerate(jobs, 1):
            skills_str = ", ".join(job.skills[:4])
            location = f"{job.city_name}/{job.area_district}" if job.area_district else job.city_name
            job_rows += f"""
            <tr>
                <td>{i}</td>
                <td>{job.job_name}</td>
                <td>{job.company_name}</td>
                <td><strong>{job.salary_desc}</strong></td>
                <td>{location}</td>
                <td>{job.experience}</td>
                <td>{job.education}</td>
                <td><small>{skills_str}</small></td>
            </tr>"""

        # AI 分析 (转换 Markdown 为简单 HTML)
        ai_html = result.ai_insights.replace("\n", "<br>") if result.ai_insights else ""

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>职探AI - {result.query} 分析报告</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f7fa; color: #333; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }}
        .header h1 {{ font-size: 28px; margin-bottom: 10px; }}
        .header .meta {{ opacity: 0.9; font-size: 14px; }}
        .card {{ background: white; border-radius: 10px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .card h2 {{ font-size: 20px; margin-bottom: 16px; color: #444; border-bottom: 2px solid #667eea; padding-bottom: 8px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px; }}
        .stat-item {{ background: #f8f9ff; padding: 16px; border-radius: 8px; text-align: center; }}
        .stat-item .value {{ font-size: 28px; font-weight: bold; color: #667eea; }}
        .stat-item .label {{ font-size: 13px; color: #666; margin-top: 4px; }}
        .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        .chart-container {{ position: relative; height: 300px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        table th {{ background: #667eea; color: white; padding: 10px 8px; text-align: left; }}
        table td {{ padding: 8px; border-bottom: 1px solid #eee; }}
        table tr:hover {{ background: #f0f3ff; }}
        .ai-insights {{ white-space: pre-wrap; line-height: 1.8; font-size: 15px; }}
        @media (max-width: 768px) {{ .charts-grid {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🔍 职探AI 分析报告</h1>
        <div class="meta">
            关键词: <strong>{result.query}</strong> &nbsp;|&nbsp;
            职位数: <strong>{result.total_jobs}</strong> &nbsp;|&nbsp;
            时间: {result.analyzed_at}
        </div>
    </div>

    <!-- 薪资概览 -->
    <div class="card">
        <h2>💰 薪资概览</h2>
        <div class="stats-grid">
            <div class="stat-item">
                <div class="value">{salary.get('avg_min_salary_k', '?')}K-{salary.get('avg_max_salary_k', '?')}K</div>
                <div class="label">平均月薪</div>
            </div>
            <div class="stat-item">
                <div class="value">{salary.get('median_min_salary_k', '?')}K-{salary.get('median_max_salary_k', '?')}K</div>
                <div class="label">中位数月薪</div>
            </div>
            <div class="stat-item">
                <div class="value">{salary.get('avg_annual_salary_k', '?')}K</div>
                <div class="label">预计平均年薪</div>
            </div>
            <div class="stat-item">
                <div class="value">{salary.get('min_salary_k', '?')}K-{salary.get('max_salary_k', '?')}K</div>
                <div class="label">薪资范围</div>
            </div>
        </div>
    </div>

    <!-- 图表 -->
    <div class="charts-grid">
        <div class="card">
            <h2>🛠️ 热门技能需求</h2>
            <div class="chart-container">
                <canvas id="skillChart"></canvas>
            </div>
        </div>
        <div class="card">
            <h2>📍 工作地点分布</h2>
            <div class="chart-container">
                <canvas id="locationChart"></canvas>
            </div>
        </div>
        <div class="card">
            <h2>💰 薪资分布</h2>
            <div class="chart-container">
                <canvas id="salaryChart"></canvas>
            </div>
        </div>
        <div class="card">
            <h2>🎓 学历 & 经验</h2>
            <div class="chart-container">
                <canvas id="eduChart"></canvas>
            </div>
        </div>
        <div class="card">
            <h2>🧭 六边形竞争力图</h2>
            <div class="chart-container">
                <canvas id="radarChart"></canvas>
            </div>
        </div>
    </div>

    <!-- AI 分析 -->
    <div class="card">
        <h2>🤖 AI 深度分析</h2>
        <div class="ai-insights">{ai_html}</div>
    </div>

    <!-- 职位列表 -->
    <div class="card">
        <h2>📋 职位详情 ({result.total_jobs}个)</h2>
        <table>
            <thead>
                <tr><th>#</th><th>职位</th><th>公司</th><th>薪资</th><th>地点</th><th>经验</th><th>学历</th><th>技能</th></tr>
            </thead>
            <tbody>{job_rows}</tbody>
        </table>
    </div>
</div>

<script>
// 技能图表
new Chart(document.getElementById('skillChart'), {{
    type: 'bar',
    data: {{
        labels: {skill_labels},
        datasets: [{{ label: '需求量', data: {skill_values}, backgroundColor: 'rgba(102, 126, 234, 0.7)' }}]
    }},
    options: {{ indexAxis: 'y', responsive: true, maintainAspectRatio: false }}
}});

// 地区图表
new Chart(document.getElementById('locationChart'), {{
    type: 'doughnut',
    data: {{
        labels: {loc_labels},
        datasets: [{{ data: {loc_values}, backgroundColor: ['#667eea','#764ba2','#f093fb','#f5576c','#4facfe','#00f2fe','#43e97b','#fa709a','#fee140','#30cfd0'] }}]
    }},
    options: {{ responsive: true, maintainAspectRatio: false }}
}});

// 薪资分布图表
new Chart(document.getElementById('salaryChart'), {{
    type: 'bar',
    data: {{
        labels: {sal_labels},
        datasets: [{{ label: '职位数', data: {sal_values}, backgroundColor: 'rgba(118, 75, 162, 0.7)' }}]
    }},
    options: {{ responsive: true, maintainAspectRatio: false }}
}});

// 学历图表
new Chart(document.getElementById('eduChart'), {{
    type: 'pie',
    data: {{
        labels: {json.dumps(list(result.education_summary.keys()), ensure_ascii=False)},
        datasets: [{{ data: {json.dumps(list(result.education_summary.values()))}, backgroundColor: ['#667eea','#764ba2','#f093fb','#f5576c','#4facfe','#00f2fe'] }}]
    }},
    options: {{ responsive: true, maintainAspectRatio: false }}
}});

// 六边形竞争力图
new Chart(document.getElementById('radarChart'), {{
    type: 'radar',
    data: {{
        labels: {radar_labels},
        datasets: [{{
            label: '竞争力评分',
            data: {radar_values},
            backgroundColor: 'rgba(47, 111, 182, 0.25)',
            borderColor: 'rgba(47, 111, 182, 0.95)',
            borderWidth: 2,
            pointBackgroundColor: 'rgba(47, 111, 182, 0.95)'
        }}]
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: false,
        scales: {{
            r: {{
                suggestedMin: 0,
                suggestedMax: 100,
                ticks: {{ stepSize: 20 }}
            }}
        }}
    }}
}});
</script>
</body>
</html>"""

        if save:
            filepath = self._save_report(html, "html")
            print(f"🌐 HTML 报告已保存: {filepath}")

        return html

    def generate_pdf(
        self,
        result: AnalysisResult,
        jobs: List[JobDetail],
        save: bool = True,
        progress_callback=None,
    ) -> str:
        """
        生成 PDF 格式报告。

        Returns:
            PDF 文件路径
        """
        def step(pct: int, stage: str, message: str) -> None:
            if callable(progress_callback):
                progress_callback(pct, stage, message)

        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError as e:
            raise RuntimeError("缺少 reportlab 依赖，请先安装: pip install reportlab") from e

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self._build_output_path(f"report_{timestamp}.pdf")
        step(10, "report.init", "正在初始化 PDF 文档结构...")

        # 使用内置中文 CID 字体，避免 Windows 环境中文乱码。
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ZhTitle",
            parent=styles["Heading1"],
            fontName="STSong-Light",
            fontSize=18,
            leading=24,
        )
        text_style = ParagraphStyle(
            "ZhBody",
            parent=styles["BodyText"],
            fontName="STSong-Light",
            fontSize=10.5,
            leading=16,
        )
        section_style = ParagraphStyle(
            "ZhSection",
            parent=styles["Heading2"],
            fontName="STSong-Light",
            fontSize=13,
            leading=18,
        )
        ai_heading_style = ParagraphStyle(
            "ZhAIHeading",
            parent=section_style,
            fontSize=12,
            leading=16,
        )
        table_header_style = ParagraphStyle(
            "ZhTableHeader",
            parent=text_style,
            fontName="STSong-Light",
            fontSize=9,
            leading=12,
            alignment=1,
        )
        table_cell_style = ParagraphStyle(
            "ZhTableCell",
            parent=text_style,
            fontName="STSong-Light",
            fontSize=8.6,
            leading=11,
            wordWrap="CJK",
        )

        salary = result.salary_summary or {}
        user_profile = result.user_profile or {}
        story = []
        story.append(Paragraph(self._sanitize_for_pdf_text("职探AI 职位分析报告"), title_style))
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(f"关键词: {html.escape(self._sanitize_for_pdf_text(result.query or '未指定'))}", text_style))
        story.append(Paragraph(f"职位总数: {result.total_jobs}", text_style))
        story.append(Paragraph(f"分析时间: {html.escape(self._sanitize_for_pdf_text(result.analyzed_at or ''))}", text_style))
        story.append(Spacer(1, 4 * mm))

        story.append(Paragraph("薪资概览", section_style))
        if salary and "error" not in salary:
            story.append(Paragraph(
                f"平均月薪: {salary.get('avg_min_salary_k', '?')}K - {salary.get('avg_max_salary_k', '?')}K", text_style
            ))
            story.append(Paragraph(
                f"中位数月薪: {salary.get('median_min_salary_k', '?')}K - {salary.get('median_max_salary_k', '?')}K", text_style
            ))
            story.append(Paragraph(f"平均年薪: {salary.get('avg_annual_salary_k', '?')}K", text_style))
        else:
            story.append(Paragraph("暂无有效薪资数据", text_style))
        story.append(Spacer(1, 4 * mm))
        step(26, "report.summary", "已完成报告摘要与薪资概览...")

        if user_profile:
            story.append(Paragraph("用户背景摘要", section_style))
            years = user_profile.get("years_of_experience")
            if years:
                story.append(Paragraph(f"经验年限: {html.escape(str(years))} 年", text_style))

            if user_profile.get("goals"):
                story.append(Paragraph(f"目标方向: {html.escape('；'.join(user_profile['goals'][:4]))}", text_style))

            strengths_summary = str(user_profile.get("personal_strengths_summary", "")).strip()
            if strengths_summary:
                story.append(Paragraph(f"已有优势: {html.escape(strengths_summary)}", text_style))
            elif user_profile.get("strengths"):
                story.append(Paragraph(f"已有优势: {html.escape('；'.join(user_profile['strengths'][:8]))}", text_style))

            if user_profile.get("concerns"):
                story.append(Paragraph(f"当前顾虑: {html.escape('；'.join(user_profile['concerns'][:4]))}", text_style))

            story.append(Spacer(1, 4 * mm))

        # 图表洞察：使用适配数据特征的图形（直方图 / 饼图 / 六边形雷达图）
        story.append(Paragraph("图表洞察", section_style))

        skill_chart, skill_legend = self._build_skill_histogram_drawing(result)
        if skill_chart is not None:
            story.append(Paragraph("1) 热门技能直方图", text_style))
            story.append(skill_chart)
            if skill_legend:
                story.append(Paragraph(f"技能映射: {html.escape(skill_legend)}", text_style))
            story.append(Spacer(1, 3 * mm))

        salary_chart = self._build_salary_pie_drawing(result)
        if salary_chart is not None:
            story.append(Paragraph("2) 薪资分布饼图", text_style))
            story.append(salary_chart)
            story.append(Spacer(1, 3 * mm))

        hex_chart = self._build_competency_hexagon_drawing(result, user_profile)
        if hex_chart is not None:
            story.append(Paragraph("3) 六边形竞争力图", text_style))
            story.append(hex_chart)
            story.append(Spacer(1, 4 * mm))

        step(42, "report.charts", "图表洞察已生成，正在继续排版正文...")

        story.append(Paragraph("热门技能 Top 10", section_style))
        for i, (skill, count) in enumerate(list(result.skill_summary.items())[:10], 1):
            story.append(Paragraph(f"{i}. {html.escape(str(skill))}: {count}", text_style))
        story.append(Spacer(1, 4 * mm))

        story.append(Paragraph("职位样本 (最多 50 条)", section_style))
        table_data = [[
            Paragraph("<b>#</b>", table_header_style),
            Paragraph("<b>职位</b>", table_header_style),
            Paragraph("<b>公司</b>", table_header_style),
            Paragraph("<b>薪资</b>", table_header_style),
            Paragraph("<b>地点</b>", table_header_style),
            Paragraph("<b>经验</b>", table_header_style),
            Paragraph("<b>学历</b>", table_header_style),
        ]]
        for i, job in enumerate(jobs[:50], 1):
            location = f"{job.city_name}/{job.area_district}" if job.area_district else job.city_name
            table_data.append([
                Paragraph(html.escape(str(i)), table_cell_style),
                Paragraph(html.escape(self._sanitize_for_pdf_text(str(job.job_name or "-"))), table_cell_style),
                Paragraph(html.escape(self._sanitize_for_pdf_text(str(job.company_name or "-"))), table_cell_style),
                Paragraph(html.escape(self._sanitize_for_pdf_text(str(job.salary_desc or "-"))), table_cell_style),
                Paragraph(html.escape(self._sanitize_for_pdf_text(str(location or "-"))), table_cell_style),
                Paragraph(html.escape(self._sanitize_for_pdf_text(str(job.experience or "-"))), table_cell_style),
                Paragraph(html.escape(self._sanitize_for_pdf_text(str(job.education or "-"))), table_cell_style),
            ])

        table = Table(
            table_data,
            repeatRows=1,
            colWidths=[11 * mm, 35 * mm, 35 * mm, 24 * mm, 26 * mm, 22 * mm, 18 * mm],
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9EEF5")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B5C0CF")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(table)
        step(52, "report.table", "职位样本表格已排版，正在写入分析正文...")

        if result.ai_insights:
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph("AI 洞察", section_style))
            for line in str(result.ai_insights).splitlines()[:140]:
                stripped = line.strip()
                if not stripped:
                    story.append(Spacer(1, 1.5 * mm))
                    continue

                if stripped.startswith("### "):
                    story.append(Paragraph(self._markdown_inline_to_reportlab(stripped[4:]), ai_heading_style))
                    continue

                if stripped.startswith("## ") or stripped.startswith("# "):
                    heading_text = stripped.lstrip("#").strip()
                    story.append(Paragraph(self._markdown_inline_to_reportlab(heading_text), ai_heading_style))
                    continue

                if stripped.startswith("- ") or stripped.startswith("* "):
                    content = stripped[2:].strip()
                    story.append(Paragraph(f"• {self._markdown_inline_to_reportlab(content)}", text_style))
                    continue

                story.append(Paragraph(self._markdown_inline_to_reportlab(stripped), text_style))
            step(78, "report.ai", "AI 洞察已排版，正在生成 PDF 文件...")

        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
            title=f"职探AI_{result.query}_分析报告",
        )
        doc.build(story)
        step(100, "report.done", "PDF 已生成完成")

        if save:
            print(f"📕 PDF 报告已保存: {filepath}")

        return filepath

    def _build_skill_histogram_drawing(self, result: AnalysisResult):
        """构建技能直方图（Top 8）。"""
        try:
            from reportlab.graphics.shapes import Drawing, String
            from reportlab.graphics.charts.barcharts import VerticalBarChart
            from reportlab.lib import colors
        except Exception:
            return None, ""

        top_items = list(result.skill_summary.items())[:8]
        if not top_items:
            return None, ""

        values = [int(c) for _, c in top_items]
        labels = [f"S{i}" for i in range(1, len(top_items) + 1)]
        legend_text = "；".join([f"S{i}={name}" for i, (name, _) in enumerate(top_items, 1)])

        drawing = Drawing(470, 220)
        chart = VerticalBarChart()
        chart.x = 45
        chart.y = 45
        chart.height = 130
        chart.width = 390
        chart.data = [values]
        chart.strokeColor = colors.HexColor("#6B7C93")
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = max(values) + max(2, int(max(values) * 0.15))
        chart.valueAxis.valueStep = max(1, int(chart.valueAxis.valueMax / 5))
        chart.categoryAxis.categoryNames = labels
        chart.categoryAxis.labels.angle = 0
        chart.categoryAxis.labels.dy = -10
        chart.barWidth = 24
        chart.groupSpacing = 12
        chart.bars[0].fillColor = colors.HexColor("#4F81BD")

        drawing.add(chart)
        drawing.add(String(45, 188, "Skills Demand Histogram (Top 8)", fontName="Helvetica", fontSize=9))
        return drawing, legend_text

    def _build_salary_pie_drawing(self, result: AnalysisResult):
        """构建薪资分布饼图。"""
        try:
            from reportlab.graphics.shapes import Drawing, String
            from reportlab.graphics.charts.piecharts import Pie
            from reportlab.lib import colors
        except Exception:
            return None

        sal_dist = (result.salary_summary or {}).get("salary_distribution", {}) or {}
        if not sal_dist:
            return None

        raw_items = list(sal_dist.items())[:8]
        raw_items.sort(key=lambda x: int(x[1]), reverse=True)
        # 切片过多时把尾部小项合并为“其他”，降低标签拥挤。
        if len(raw_items) > 6:
            major = raw_items[:5]
            other_sum = sum(int(v) for _, v in raw_items[5:])
            raw_items = major + [("其他", other_sum)]

        labels = [str(k) for k, _ in raw_items]
        values = [int(v) for _, v in raw_items]
        if not values or sum(values) <= 0:
            return None

        palette = [
            colors.HexColor("#5B8FF9"),
            colors.HexColor("#5AD8A6"),
            colors.HexColor("#5D7092"),
            colors.HexColor("#F6BD16"),
            colors.HexColor("#E8684A"),
            colors.HexColor("#6DC8EC"),
            colors.HexColor("#9270CA"),
            colors.HexColor("#FF9D4D"),
        ]

        drawing = Drawing(470, 230)
        pie = Pie()
        pie.x = 130
        pie.y = 24
        pie.width = 190
        pie.height = 190
        pie.data = values
        pie.labels = labels
        pie.slices.strokeWidth = 0.5
        # 使用内置简单标签，减少导线和外侧文本重叠。
        pie.sideLabels = False
        pie.simpleLabels = True
        pie.startAngle = 110

        for idx in range(len(values)):
            pie.slices[idx].fillColor = palette[idx % len(palette)]

        drawing.add(pie)
        return drawing

    def _build_competency_hexagon_drawing(self, result: AnalysisResult, user_profile: Dict[str, Any]):
        """构建六边形竞争力图（雷达样式）。"""
        try:
            from reportlab.graphics.shapes import Drawing, Line, String, Polygon
            from reportlab.lib import colors
        except Exception:
            return None

        total_jobs = max(1, int(result.total_jobs or 0))
        skills_n = len(result.skill_summary or {})
        goals_n = len(user_profile.get("goals", [])) if user_profile else 0
        strengths_n = len(user_profile.get("strengths", [])) if user_profile else 0
        concerns_n = len(user_profile.get("concerns", [])) if user_profile else 0
        exp_summary = result.experience_summary or {}
        edu_summary = result.education_summary or {}

        # 6 维指标，统一映射到 0-100
        skill_match = min(100, int(skills_n / 12 * 100))
        salary_comp = min(100, int((result.salary_summary or {}).get("avg_annual_salary_k", 0) / 300 * 100))
        exp_fit = min(100, int(sum(exp_summary.values()) / total_jobs * 100))
        edu_fit = min(100, int(sum(edu_summary.values()) / total_jobs * 100))
        market_heat = min(100, int(total_jobs / 120 * 100))
        clarity = min(100, int((goals_n * 20 + strengths_n * 10 - concerns_n * 8) + 40))
        clarity = max(0, min(100, clarity))

        values = [skill_match, salary_comp, exp_fit, edu_fit, market_heat, clarity]
        labels = ["Skill", "Salary", "ExpFit", "EduFit", "Heat", "Goal"]

        drawing = Drawing(470, 260)
        cx, cy, r = 230, 125, 78

        # 背景六边形网格
        for level in (0.25, 0.5, 0.75, 1.0):
            pts = []
            for i in range(6):
                angle = math.radians(90 - i * 60)
                x = cx + r * level * math.cos(angle)
                y = cy + r * level * math.sin(angle)
                pts.extend([x, y])
            grid = Polygon(points=pts)
            grid.fillColor = None
            grid.strokeColor = colors.HexColor("#D9E2EC")
            grid.strokeWidth = 0.7
            drawing.add(grid)

        # 轴线 + 标签
        for i, label in enumerate(labels):
            angle = math.radians(90 - i * 60)
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            drawing.add(Line(cx, cy, x, y, strokeColor=colors.HexColor("#BCCCDC"), strokeWidth=0.6))
            lx = cx + (r + 18) * math.cos(angle)
            ly = cy + (r + 18) * math.sin(angle)
            drawing.add(String(lx - 12, ly - 3, label, fontName="Helvetica", fontSize=8))

        # 数据多边形
        data_pts = []
        for i, val in enumerate(values):
            scale = max(0.0, min(1.0, val / 100.0))
            angle = math.radians(90 - i * 60)
            x = cx + r * scale * math.cos(angle)
            y = cy + r * scale * math.sin(angle)
            data_pts.extend([x, y])

        poly = Polygon(points=data_pts)
        poly.fillColor = colors.Color(0.24, 0.51, 0.88, alpha=0.30)
        poly.strokeColor = colors.HexColor("#2F6FB6")
        poly.strokeWidth = 1.1
        drawing.add(poly)
        drawing.add(String(45, 230, "Career Competency Hexagon", fontName="Helvetica", fontSize=9))
        return drawing

    def _extract_advantages_from_ai_insights(self, ai_text: str) -> str:
        """从 AI 洞察文本中提取“已有优势/个人优势”段，避免报告里优势信息被截断。"""
        text = str(ai_text or "")
        if not text.strip():
            return ""

        lines = [x.strip() for x in text.splitlines()]
        candidates = []
        capturing = False

        for line in lines:
            if not line:
                if capturing and candidates:
                    break
                continue

            normalized = line.lstrip("#").strip()
            if any(key in normalized for key in ("已有优势", "个人优势", "优势分析", "优势", "匹配优势")):
                capturing = True
                continue

            if capturing:
                # 遇到新的章节标题则停止。
                if line.startswith("#") or re.match(r"^\d+\.", normalized):
                    break

                content = normalized
                if content.startswith(('- ', '* ', '• ')):
                    content = content[2:].strip()
                if content:
                    candidates.append(content)
                if len(candidates) >= 6:
                    break

        if not candidates:
            return ""
        return "；".join(candidates)

    def _markdown_inline_to_reportlab(self, text: str) -> str:
        """将常见 Markdown 行内语法转换为 ReportLab 可识别标签。"""
        safe = html.escape(self._sanitize_for_pdf_text(str(text or "")))

        # 先处理粗体，再处理斜体，避免相互干扰。
        safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
        safe = re.sub(r"__(.+?)__", r"<b>\1</b>", safe)

        # 避免把粗体标记中的单个 * 误判为斜体。
        safe = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", safe)
        safe = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"<i>\1</i>", safe)

        # 行内代码不切换英文字体，避免中英文混排时字距异常。
        safe = re.sub(r"`([^`]+)`", r"「\1」", safe)
        return safe

    def _sanitize_for_pdf_text(self, text: str) -> str:
        """清理 ReportLab/STSong-Light 不支持的字符，避免 PDF 出现黑框。"""
        cleaned = []
        for ch in text:
            cp = ord(ch)

            # 去掉常见 emoji、变体选择符和零宽字符。
            if 0x1F000 <= cp <= 0x1FAFF:
                continue
            if 0xFE00 <= cp <= 0xFE0F:
                continue
            if cp in (0x200B, 0x200C, 0x200D):
                continue

            cat = unicodedata.category(ch)
            if cat.startswith("C") and ch not in ("\n", "\t", "\r"):
                continue

            cleaned.append(ch)

        normalized = "".join(cleaned)
        # 将部分特殊符号转为稳定可显示字符。
        normalized = normalized.replace("•", "-")
        normalized = normalized.replace("→", "->")
        normalized = normalized.replace("·", "-")
        return normalized

    def _save_report(self, content: str, ext: str) -> str:
        """保存报告文件"""
        filepath = self._build_output_path(f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return filepath

    def _build_output_path(self, filename: str) -> str:
        """构建输出文件路径并确保目录存在。"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(base_dir, self.config.output_dir)
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, filename)
