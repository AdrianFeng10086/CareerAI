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

        # AI 分析 (按 Markdown 渲染，支持表格/列表/代码块)
        ai_html = ""
        if result.ai_insights:
            try:
                md = __import__("markdown")
                ai_html = md.markdown(
                    result.ai_insights,
                    extensions=["extra", "tables", "fenced_code", "sane_lists"],
                    output_format="html5",
                )
            except Exception:
                ai_html = html.escape(result.ai_insights).replace("\n", "<br>")

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
        .ai-insights {{ line-height: 1.8; font-size: 15px; }}
        .ai-insights table {{ width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 14px; }}
        .ai-insights th {{ background: #eef2ff; color: #333; border: 1px solid #d7def8; padding: 8px; text-align: left; }}
        .ai-insights td {{ border: 1px solid #e3e7f5; padding: 8px; vertical-align: top; }}
        .ai-insights code {{ background: #f3f5ff; border-radius: 4px; padding: 1px 5px; }}
        .ai-insights pre {{ background: #f7f8ff; border: 1px solid #e4e8fb; border-radius: 6px; padding: 10px; overflow-x: auto; }}
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
        使用 Markdown + WeasyPrint 生成 PDF 报告。

        Returns:
            PDF 文件路径
        """
        def step(pct: int, stage: str, message: str) -> None:
            if callable(progress_callback):
                progress_callback(pct, stage, message)
        try:
            md_module = __import__("markdown")
            weasyprint = __import__("weasyprint")
            HTML = getattr(weasyprint, "HTML")
            CSS = getattr(weasyprint, "CSS")
        except Exception as e:
            raise RuntimeError("缺少 markdown/weasyprint 依赖，请先安装: pip install Markdown weasyprint") from e

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self._build_output_path(f"report_{timestamp}.pdf")

        step(10, "report.init", "正在准备 Markdown 内容...")
        markdown_text = self.generate_markdown(result=result, jobs=jobs, save=False)
        markdown_text = self._inject_mermaid_radar_svg(markdown_text)

        step(45, "report.ai", "正在将 Markdown 渲染为 HTML...")
        html_body = md_module.markdown(
            markdown_text,
            extensions=["extra", "tables", "fenced_code", "sane_lists", "nl2br"],
            output_format="html5",
        )
        charts_html = self._build_weasy_charts_html(result)

        css_string = """
        @page {
            size: A4;
            margin: 12mm;
        }
        body {
            font-family: "Microsoft YaHei", "SimSun", "Noto Sans CJK SC", "DejaVu Sans", sans-serif;
            color: #1f2d3d;
            line-height: 1.65;
            font-size: 12px;
        }
        h1, h2, h3, h4 {
            color: #1f2d3d;
            margin: 10px 0 8px;
        }
        p, li {
            margin: 4px 0;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 10px 0;
            font-size: 11px;
            table-layout: fixed;
        }
        th, td {
            border: 1px solid #b5c0cf;
            padding: 6px 8px;
            vertical-align: top;
            word-wrap: break-word;
            overflow-wrap: anywhere;
        }
        th {
            background: #e9eef5;
            font-weight: 700;
            text-align: left;
        }
        tbody tr:nth-child(even) {
            background: #f9fbff;
        }
        code {
            background: #f3f6fb;
            border-radius: 4px;
            padding: 0 4px;
        }
        pre {
            background: #f8fbff;
            border: 1px solid #d9e2ec;
            border-radius: 6px;
            padding: 8px;
            white-space: pre-wrap;
            word-break: break-word;
        }
        .chart-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 10px;
            margin: 8px 0 14px;
        }
        .chart-card {
            border: 1px solid #d9e2ec;
            border-radius: 6px;
            padding: 8px;
            background: #fcfdff;
        }
        .chart-title {
            font-weight: 700;
            margin-bottom: 6px;
        }
        .chart-svg {
            width: 100%;
            height: auto;
            display: block;
        }
        """

        full_html = f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
    <meta charset=\"utf-8\">
    <title>职探AI_{html.escape(result.query or '')}_分析报告</title>
</head>
<body>
{charts_html}
{html_body}
</body>
</html>"""

        step(78, "report.table", "正在生成 PDF 文件...")
        HTML(string=full_html).write_pdf(filepath, stylesheets=[CSS(string=css_string)])

        step(100, "report.done", "PDF 已生成完成")
        if save:
            print(f"📕 PDF 报告已保存: {filepath}")
        return filepath

    def _build_weasy_charts_html(self, result: AnalysisResult) -> str:
        skill_svg = self._build_weasy_skill_svg(result)
        salary_svg = self._build_weasy_salary_svg(result)
        hex_svg = self._build_weasy_hexagon_svg(result)
        return (
            "<h2>图表洞察</h2>"
            "<div class=\"chart-grid\">"
            f"<div class=\"chart-card\"><div class=\"chart-title\">热门技能直方图</div>{skill_svg}</div>"
            f"<div class=\"chart-card\"><div class=\"chart-title\">薪资分布图</div>{salary_svg}</div>"
            f"<div class=\"chart-card\"><div class=\"chart-title\">六边形竞争力图</div>{hex_svg}</div>"
            "</div>"
        )

    def _inject_mermaid_radar_svg(self, markdown_text: str) -> str:
        """将 mermaid radar-beta 代码块替换为可直接参与 WeasyPrint 渲染的 SVG。"""
        source = str(markdown_text or "")
        pattern = re.compile(r"```mermaid\s*\n(.*?)\n```", flags=re.IGNORECASE | re.DOTALL)

        def _replace(match: re.Match) -> str:
            block = str(match.group(1) or "")
            model = self._parse_mermaid_radar_block(block)
            if not model:
                return match.group(0)
            return self._build_weasy_radar_svg_html(model)

        return pattern.sub(_replace, source)

    def _parse_mermaid_radar_block(self, block: str) -> Optional[Dict[str, Any]]:
        lines = [str(x or "").strip() for x in str(block or "").splitlines() if str(x or "").strip()]
        if not lines:
            return None

        normalized = [
            ln.replace("“", '"').replace("”", '"').replace("：", ":").replace("，", ",")
            for ln in lines
        ]
        if not normalized[0].lower().startswith("radar-beta"):
            return None

        title = "就业能力雷达图"
        axes: List[str] = []
        min_value = 0.0
        max_value = 100.0
        datasets: List[Dict[str, Any]] = []

        for ln in normalized[1:]:
            m_title = re.match(r"^title\s+(.+)$", ln, flags=re.IGNORECASE)
            if m_title:
                title = m_title.group(1).strip().strip('"') or title
                continue

            m_axis = re.match(
                r"^axis\s+\"?([^\"\[]+?)\"?\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]$",
                ln,
                flags=re.IGNORECASE,
            )
            if m_axis:
                axes.append(m_axis.group(1).strip())
                min_value = float(m_axis.group(2))
                max_value = float(m_axis.group(3))
                continue

            m_ds = re.match(r"^\"?([^\":]+?)\"?\s*:\s*\[\s*([^\]]+)\s*\]$", ln)
            if m_ds:
                values: List[float] = []
                for token in m_ds.group(2).split(","):
                    token = token.strip()
                    if not token:
                        continue
                    try:
                        values.append(float(token))
                    except Exception:
                        pass
                if values:
                    datasets.append({"name": m_ds.group(1).strip(), "values": values})

        if len(axes) < 3 or not datasets:
            return None

        axis_count = len(axes)
        fixed_sets: List[Dict[str, Any]] = []
        for ds in datasets[:4]:
            vals = list(ds["values"])[:axis_count]
            while len(vals) < axis_count:
                vals.append(min_value)
            fixed_sets.append({"name": ds["name"], "values": vals})

        if max_value <= min_value:
            max_value = min_value + 100.0

        return {
            "title": title,
            "axes": axes,
            "min_value": min_value,
            "max_value": max_value,
            "datasets": fixed_sets,
        }

    def _build_weasy_radar_svg_html(self, model: Dict[str, Any]) -> str:
        axes = model.get("axes") or []
        datasets = model.get("datasets") or []
        if not axes or not datasets:
            return "<p>雷达图数据不足，未生成图形。</p>"

        min_v = float(model.get("min_value", 0.0))
        max_v = float(model.get("max_value", 100.0))
        span = max(1e-9, max_v - min_v)

        width = 760
        height = 380
        cx = 270
        cy = 190
        radius = 128

        def pt(level: float, idx: int):
            ang = math.radians(90 - idx * (360 / len(axes)))
            return (cx + radius * level * math.cos(ang), cy + radius * level * math.sin(ang))

        parts = [
            "<div class='chart-card'>",
            f"<div class='chart-title'>{self._svg_escape(model.get('title', '就业能力雷达图'))}</div>",
            f"<svg class='chart-svg' viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg'>",
            "<rect x='0' y='0' width='100%' height='100%' fill='#ffffff'/>",
        ]

        for lv in (0.2, 0.4, 0.6, 0.8, 1.0):
            poly = [pt(lv, i) for i in range(len(axes))]
            coords = " ".join(f"{x:.1f},{y:.1f}" for x, y in poly)
            parts.append(f"<polygon points='{coords}' fill='none' stroke='#d9e2ec' stroke-width='1'/>")

        for i, label in enumerate(axes):
            x, y = pt(1.0, i)
            parts.append(f"<line x1='{cx}' y1='{cy}' x2='{x:.1f}' y2='{y:.1f}' stroke='#bcccdc' stroke-width='1'/>")
            lx, ly = pt(1.18, i)
            parts.append(f"<text x='{lx:.1f}' y='{ly:.1f}' font-size='11' fill='#334155'>{self._svg_escape(label)}</text>")

        palette = ["#0ea5e9", "#10b981", "#f59e0b", "#ef4444"]
        for ds_i, ds in enumerate(datasets):
            color = palette[ds_i % len(palette)]
            pts = []
            for i, val in enumerate(ds.get("values") or []):
                norm = (float(val) - min_v) / span
                norm = max(0.0, min(1.0, norm))
                x, y = pt(norm, i)
                pts.append((x, y))
            coords = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            fill = color + "33"
            parts.append(f"<polygon points='{coords}' fill='{fill}' stroke='{color}' stroke-width='2'/>")
            for x, y in pts:
                parts.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='2.2' fill='{color}'/>")

        legend_x = 540
        legend_y = 78
        for ds_i, ds in enumerate(datasets):
            color = palette[ds_i % len(palette)]
            y = legend_y + ds_i * 20
            parts.append(f"<line x1='{legend_x}' y1='{y}' x2='{legend_x + 16}' y2='{y}' stroke='{color}' stroke-width='2'/>")
            parts.append(f"<text x='{legend_x + 22}' y='{y + 4}' font-size='11' fill='#334155'>{self._svg_escape(ds.get('name', f'序列{ds_i + 1}'))}</text>")

        parts.append(f"<text x='520' y='338' font-size='10' fill='#64748b'>刻度范围: {min_v:g} - {max_v:g}</text>")
        parts.append("</svg>")
        parts.append("</div>")
        return "".join(parts)

    def _svg_escape(self, text: str) -> str:
        return html.escape(str(text or "")).replace("\n", " ")

    def _build_weasy_skill_svg(self, result: AnalysisResult) -> str:
        items = list((result.skill_summary or {}).items())[:8]
        if not items:
            return "<p>暂无技能数据</p>"

        width = 760
        row_h = 28
        top = 20
        left = 170
        chart_w = 540
        height = top + row_h * len(items) + 16
        max_v = max(int(v) for _, v in items) or 1

        parts = [f"<svg class=\"chart-svg\" viewBox=\"0 0 {width} {height}\" xmlns=\"http://www.w3.org/2000/svg\">"]
        parts.append("<rect x='0' y='0' width='100%' height='100%' fill='#ffffff'/>")
        for i, (name, val) in enumerate(items):
            y = top + i * row_h
            bar_w = int(chart_w * (int(val) / max_v))
            parts.append(f"<text x='{left - 8}' y='{y + 15}' font-size='11' text-anchor='end' fill='#334155'>{self._svg_escape(name)}</text>")
            parts.append(f"<rect x='{left}' y='{y + 4}' width='{bar_w}' height='12' fill='#4f81bd'/>")
            parts.append(f"<text x='{left + bar_w + 6}' y='{y + 15}' font-size='10' fill='#475569'>{int(val)}</text>")
        parts.append("</svg>")
        return "".join(parts)

    def _build_weasy_salary_svg(self, result: AnalysisResult) -> str:
        sal_dist = (result.salary_summary or {}).get("salary_distribution", {}) or {}
        items = list(sal_dist.items())[:8]
        if not items:
            return "<p>暂无薪资分布数据</p>"

        width = 760
        row_h = 28
        top = 20
        left = 140
        chart_w = 570
        height = top + row_h * len(items) + 16
        max_v = max(int(v) for _, v in items) or 1

        parts = [f"<svg class=\"chart-svg\" viewBox=\"0 0 {width} {height}\" xmlns=\"http://www.w3.org/2000/svg\">"]
        parts.append("<rect x='0' y='0' width='100%' height='100%' fill='#ffffff'/>")
        for i, (name, val) in enumerate(items):
            y = top + i * row_h
            bar_w = int(chart_w * (int(val) / max_v))
            parts.append(f"<text x='{left - 8}' y='{y + 15}' font-size='11' text-anchor='end' fill='#334155'>{self._svg_escape(name)}</text>")
            parts.append(f"<rect x='{left}' y='{y + 4}' width='{bar_w}' height='12' fill='#5d7092'/>")
            parts.append(f"<text x='{left + bar_w + 6}' y='{y + 15}' font-size='10' fill='#475569'>{int(val)}</text>")
        parts.append("</svg>")
        return "".join(parts)

    def _build_weasy_hexagon_svg(self, result: AnalysisResult) -> str:
        user_profile = result.user_profile or {}
        total_jobs = max(1, int(result.total_jobs or 0))
        skills_n = len(result.skill_summary or {})
        goals_n = len(user_profile.get("goals", [])) if user_profile else 0
        strengths_n = len(user_profile.get("strengths", [])) if user_profile else 0
        concerns_n = len(user_profile.get("concerns", [])) if user_profile else 0
        exp_summary = result.experience_summary or {}
        edu_summary = result.education_summary or {}

        skill_match = min(100, int(skills_n / 12 * 100))
        salary_comp = min(100, int((result.salary_summary or {}).get("avg_annual_salary_k", 0) / 300 * 100))
        exp_fit = min(100, int(sum(exp_summary.values()) / total_jobs * 100))
        edu_fit = min(100, int(sum(edu_summary.values()) / total_jobs * 100))
        market_heat = min(100, int(total_jobs / 120 * 100))
        clarity = min(100, int((goals_n * 20 + strengths_n * 10 - concerns_n * 8) + 40))
        clarity = max(0, min(100, clarity))

        values = [skill_match, salary_comp, exp_fit, edu_fit, market_heat, clarity]
        labels = ["Skill", "Salary", "ExpFit", "EduFit", "Heat", "Goal"]
        w, h = 760, 300
        cx, cy, r = 220, 150, 90

        def pt(level: float, idx: int):
            ang = math.radians(90 - idx * 60)
            return (cx + r * level * math.cos(ang), cy + r * level * math.sin(ang))

        parts = [f"<svg class=\"chart-svg\" viewBox=\"0 0 {w} {h}\" xmlns=\"http://www.w3.org/2000/svg\">"]
        parts.append("<rect x='0' y='0' width='100%' height='100%' fill='#ffffff'/>")

        for level in (0.25, 0.5, 0.75, 1.0):
            p = [pt(level, i) for i in range(6)]
            coords = " ".join(f"{x:.1f},{y:.1f}" for x, y in p)
            parts.append(f"<polygon points='{coords}' fill='none' stroke='#d9e2ec' stroke-width='1'/>")

        for i, label in enumerate(labels):
            x, y = pt(1.0, i)
            parts.append(f"<line x1='{cx}' y1='{cy}' x2='{x:.1f}' y2='{y:.1f}' stroke='#bcccdc' stroke-width='1'/>")
            lx, ly = pt(1.2, i)
            parts.append(f"<text x='{lx:.1f}' y='{ly:.1f}' font-size='11' fill='#334155'>{label}</text>")

        data_pts = []
        for i, v in enumerate(values):
            x, y = pt(max(0.0, min(1.0, v / 100.0)), i)
            data_pts.append((x, y))
        data_coords = " ".join(f"{x:.1f},{y:.1f}" for x, y in data_pts)
        parts.append(f"<polygon points='{data_coords}' fill='rgba(47,111,182,0.32)' stroke='#2f6fb6' stroke-width='2'/>")

        legend_x = 400
        parts.append(f"<text x='{legend_x}' y='48' font-size='12' fill='#0f172a'>维度得分</text>")
        for idx, (label, val) in enumerate(zip(labels, values)):
            y = 70 + idx * 20
            parts.append(f"<text x='{legend_x}' y='{y}' font-size='11' fill='#334155'>{label}: {val}</text>")

        parts.append("</svg>")
        return "".join(parts)

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
        # 保留多行文本：将换行转为 ReportLab Paragraph 可识别的换行标签。
        safe = safe.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")
        return safe

    def _sanitize_for_pdf_text(self, text: str) -> str:
        """清理 ReportLab/STSong-Light 不支持的字符，避免 PDF 出现黑框。"""
        text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", str(text or ""))
        text = re.sub(r"(?i)&lt;\s*br\s*/?\s*&gt;", "\n", text)

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
