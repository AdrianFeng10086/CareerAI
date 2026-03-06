"""
AI 职位分析模块
对爬取的职位数据进行统计分析 + AI 深度洞察
"""

import json
from typing import List, Dict, Any, Optional, Tuple, Callable
from collections import Counter
from datetime import datetime

from .models import JobDetail, AnalysisResult
from .config import Config


class JobAnalyzer:
    """职位数据分析器"""

    def __init__(self, config: Config):
        self.config = config

    def analyze(
        self,
        jobs: List[JobDetail],
        query: str = "",
        user_profile: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> AnalysisResult:
        """
        对职位数据进行全面分析

        Args:
            jobs: 职位列表
            query: 搜索关键词

        Returns:
            分析结果
        """
        def step(pct: int, stage: str, message: str) -> None:
            if progress_callback:
                progress_callback(pct, stage, message)

        if not jobs:
            print("⚠️ 没有可分析的职位数据")
            return AnalysisResult(query=query, analyzed_at=datetime.now().isoformat())

        print(f"\n📊 正在分析 {len(jobs)} 个职位数据...\n")
        step(8, "analyze.aggregate", "正在聚合薪资、技能、经验分布...")

        salary_summary, skill_counter, location_counter, edu_counter, exp_counter, industry_counter = self._aggregate_stats(jobs)

        result = AnalysisResult(
            query=query,
            total_jobs=len(jobs),
            salary_summary=salary_summary,
            skill_summary=dict(skill_counter.most_common(30)),
            location_summary=dict(location_counter.most_common(20)),
            education_summary=dict(edu_counter.most_common()),
            experience_summary=dict(exp_counter.most_common()),
            industry_summary=dict(industry_counter.most_common(15)),
            user_profile=user_profile or {},
            analyzed_at=datetime.now().isoformat(),
        )

        # AI 深度分析
        if self.config.ai_api_key:
            step(45, "ai.deep.start", "统计完成，正在调用 AI 进行深度分析...")
        else:
            step(45, "ai.deep.start", "未配置 AI，正在使用本地规则进行深度分析...")

        ai_insights = self._generate_ai_insights(result, jobs)
        result.ai_insights = ai_insights

        step(88, "ai.deep.done", "深度分析已完成，正在整理报告数据...")

        step(100, "analyze.done", "分析已完成，准备生成报告...")

        print("✅ 分析完成!\n")
        return result

    def _aggregate_stats(self, jobs: List[JobDetail]) -> Tuple[Dict[str, Any], Counter, Counter, Counter, Counter, Counter]:
        """单次遍历汇总统计，减少重复循环带来的开销。"""
        skill_counter = Counter()
        location_counter = Counter()
        edu_counter = Counter()
        exp_counter = Counter()
        industry_counter = Counter()

        min_salaries: List[int] = []
        max_salaries: List[int] = []
        annual_salaries: List[float] = []
        salary_ranges = Counter()

        for job in jobs:
            if job.skills:
                skill_counter.update(job.skills)

            loc = job.area_district or job.city_name
            if loc:
                location_counter[loc] += 1

            if job.education:
                edu_counter[job.education] += 1
            if job.experience:
                exp_counter[job.experience] += 1
            if job.industry:
                industry_counter[job.industry] += 1

            if job.salary_min > 0 and job.salary_max > 0:
                min_salaries.append(job.salary_min)
                max_salaries.append(job.salary_max)
                avg_sal = (job.salary_min + job.salary_max) / 2
                annual_salaries.append(avg_sal * job.salary_months)

                if avg_sal < 5:
                    salary_ranges["<5K"] += 1
                elif avg_sal < 10:
                    salary_ranges["5-10K"] += 1
                elif avg_sal < 15:
                    salary_ranges["10-15K"] += 1
                elif avg_sal < 20:
                    salary_ranges["15-20K"] += 1
                elif avg_sal < 30:
                    salary_ranges["20-30K"] += 1
                elif avg_sal < 50:
                    salary_ranges["30-50K"] += 1
                else:
                    salary_ranges["50K+"] += 1

        salary_summary = self._build_salary_summary(min_salaries, max_salaries, annual_salaries, salary_ranges)
        return salary_summary, skill_counter, location_counter, edu_counter, exp_counter, industry_counter

    def _build_salary_summary(
        self,
        min_salaries: List[int],
        max_salaries: List[int],
        annual_salaries: List[float],
        salary_ranges: Counter,
    ) -> Dict[str, Any]:
        """根据聚合后的薪资数据计算汇总结果。"""
        if not min_salaries or not max_salaries:
            return {"error": "无有效薪资数据"}

        min_sorted = sorted(min_salaries)
        max_sorted = sorted(max_salaries)
        avg_min = sum(min_salaries) / len(min_salaries)
        avg_max = sum(max_salaries) / len(max_salaries)
        avg_annual = sum(annual_salaries) / len(annual_salaries) if annual_salaries else 0

        return {
            "valid_count": len(min_salaries),
            "avg_min_salary_k": round(avg_min, 1),
            "avg_max_salary_k": round(avg_max, 1),
            "median_min_salary_k": min_sorted[len(min_sorted) // 2],
            "median_max_salary_k": max_sorted[len(max_sorted) // 2],
            "min_salary_k": min(min_salaries),
            "max_salary_k": max(max_salaries),
            "avg_annual_salary_k": round(avg_annual, 1),
            "salary_distribution": dict(salary_ranges.most_common()),
        }

    def _analyze_salary(self, jobs: List[JobDetail]) -> Dict[str, Any]:
        """薪资统计分析"""
        valid_jobs = [j for j in jobs if j.salary_min > 0 and j.salary_max > 0]
        if not valid_jobs:
            return {"error": "无有效薪资数据"}

        min_salaries = [j.salary_min for j in valid_jobs]
        max_salaries = [j.salary_max for j in valid_jobs]
        avg_min = sum(min_salaries) / len(min_salaries)
        avg_max = sum(max_salaries) / len(max_salaries)

        # 年薪计算 (考虑月数)
        annual_salaries = []
        for j in valid_jobs:
            avg_monthly = (j.salary_min + j.salary_max) / 2
            annual = avg_monthly * j.salary_months
            annual_salaries.append(annual)

        avg_annual = sum(annual_salaries) / len(annual_salaries)

        # 薪资区间分布
        salary_ranges = Counter()
        for j in valid_jobs:
            avg_sal = (j.salary_min + j.salary_max) / 2
            if avg_sal < 5:
                salary_ranges["<5K"] += 1
            elif avg_sal < 10:
                salary_ranges["5-10K"] += 1
            elif avg_sal < 15:
                salary_ranges["10-15K"] += 1
            elif avg_sal < 20:
                salary_ranges["15-20K"] += 1
            elif avg_sal < 30:
                salary_ranges["20-30K"] += 1
            elif avg_sal < 50:
                salary_ranges["30-50K"] += 1
            else:
                salary_ranges["50K+"] += 1

        return {
            "valid_count": len(valid_jobs),
            "avg_min_salary_k": round(avg_min, 1),
            "avg_max_salary_k": round(avg_max, 1),
            "median_min_salary_k": sorted(min_salaries)[len(min_salaries) // 2],
            "median_max_salary_k": sorted(max_salaries)[len(max_salaries) // 2],
            "min_salary_k": min(min_salaries),
            "max_salary_k": max(max_salaries),
            "avg_annual_salary_k": round(avg_annual, 1),
            "salary_distribution": dict(salary_ranges.most_common()),
        }

    def _analyze_skills(self, jobs: List[JobDetail]) -> Dict[str, int]:
        """技能需求分析"""
        skill_counter = Counter()
        for job in jobs:
            for skill in job.skills:
                skill_counter[skill] += 1

        # 返回 Top 30 技能
        return dict(skill_counter.most_common(30))

    def _analyze_locations(self, jobs: List[JobDetail]) -> Dict[str, int]:
        """工作地点分析"""
        location_counter = Counter()
        for job in jobs:
            loc = job.area_district or job.city_name
            if loc:
                location_counter[loc] += 1

        return dict(location_counter.most_common(20))

    def _analyze_education(self, jobs: List[JobDetail]) -> Dict[str, int]:
        """学历要求分析"""
        edu_counter = Counter()
        for job in jobs:
            if job.education:
                edu_counter[job.education] += 1

        return dict(edu_counter.most_common())

    def _analyze_experience(self, jobs: List[JobDetail]) -> Dict[str, int]:
        """经验要求分析"""
        exp_counter = Counter()
        for job in jobs:
            if job.experience:
                exp_counter[job.experience] += 1

        return dict(exp_counter.most_common())

    def _analyze_industry(self, jobs: List[JobDetail]) -> Dict[str, int]:
        """行业分布分析"""
        industry_counter = Counter()
        for job in jobs:
            if job.industry:
                industry_counter[job.industry] += 1

        return dict(industry_counter.most_common(15))

    def _generate_ai_insights(self, result: AnalysisResult, jobs: List[JobDetail]) -> str:
        """
        使用 AI 生成深度分析和建议

        如果未配置 AI API Key，则使用本地规则生成基础分析
        """
        if self.config.ai_api_key:
            return self._call_ai_api(result, jobs)
        else:
            return self._generate_local_insights(result, jobs)

    def _call_ai_api(self, result: AnalysisResult, jobs: List[JobDetail]) -> str:
        """调用 AI API 生成分析"""
        try:
            import requests as req

            # 构建 prompt
            top_skills = list(result.skill_summary.items())[:20]
            top_locations = list(result.location_summary.items())[:12]
            salary = result.salary_summary
            sample_jobs = jobs[:15]
            user_profile = result.user_profile or {}

            prompt = f"""你是一位资深的职业规划顾问和人力资源分析专家。请根据以下Boss直聘的职位数据分析，给出详细的职业建议。

## 数据概览
- 搜索关键词: {result.query}
- 职位总数: {result.total_jobs}
- 分析时间: {result.analyzed_at}

## 薪资统计
- 平均薪资范围: {salary.get('avg_min_salary_k', 'N/A')}K - {salary.get('avg_max_salary_k', 'N/A')}K/月
- 中位数薪资: {salary.get('median_min_salary_k', 'N/A')}K - {salary.get('median_max_salary_k', 'N/A')}K/月
- 薪资极值: {salary.get('min_salary_k', 'N/A')}K - {salary.get('max_salary_k', 'N/A')}K/月
- 平均年薪: {salary.get('avg_annual_salary_k', 'N/A')}K
- 薪资分布: {json.dumps(salary.get('salary_distribution', {}), ensure_ascii=False)}

## Top 技能需求
{chr(10).join(f"- {skill}: {count}个职位需要" for skill, count in top_skills)}

## 工作地点分布
{chr(10).join(f"- {loc}: {count}个职位" for loc, count in top_locations)}

## 学历要求
{json.dumps(result.education_summary, ensure_ascii=False)}

## 经验要求
{json.dumps(result.experience_summary, ensure_ascii=False)}

## 行业分布
{json.dumps(result.industry_summary, ensure_ascii=False)}

## 部分职位样本 (前15个)
{self._format_job_samples(sample_jobs)}

## 用户背景与诉求
{json.dumps(user_profile, ensure_ascii=False)[:4000]}

---

请从以下几个维度给出详细分析和建议（使用中文）：

1. **薪资分析**：当前市场薪资水平如何？不同经验水平的薪资差异？值得期望的薪资范围？
2. **核心技能**：哪些技能最受欢迎？哪些是必备技能？哪些是加分技能？建议学习路线是什么？
3. **就业地图**：哪些地区/商圈职位集中？通勤建议？
4. **行业趋势**：哪些行业在招人？整体就业前景如何？
5. **求职建议**：针对应聘'{result.query}'相关岗位，给出具体的准备建议、简历优化方向、面试重点。
    必须结合用户背景与诉求，指出哪些建议是“短期优先”，哪些是“中期补齐”。
6. **风险提示**：市场上有哪些需要注意的点？
"""

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.ai_api_key}",
            }

            payload = {
                "model": self.config.ai_model,
                "messages": [
                    {"role": "system", "content": "你是一位资深的职业规划顾问，擅长数据分析和职业建议。请用中文回答，给出有洞察力和可操作性的建议。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": self.config.ai_temperature,
                # 放宽输出上限，减少回答被截断导致的信息不完整。
                "max_tokens": min(max(self.config.ai_max_tokens, 3000), 7000),
            }

            url = f"{self.config.ai_base_url}"
            print("   🤖 正在调用 AI 生成深度分析...")

            resp = req.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()

            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            print("   ✅ AI 分析完成")
            return content

        except Exception as e:
            print(f"   ⚠️ AI 分析失败: {e}")
            print("   📝 使用本地规则生成分析...")
            return self._generate_local_insights(result, jobs)

    def _generate_local_insights(self, result: AnalysisResult, jobs: List[JobDetail]) -> str:
        """本地规则生成分析（无需AI API）"""
        salary = result.salary_summary
        skills = result.skill_summary
        locations = result.location_summary
        education = result.education_summary
        experience = result.experience_summary
        user_profile = result.user_profile or {}

        lines = []
        lines.append(f"# 📊 {result.query} 职位市场分析报告\n")
        lines.append(f"*基于 {result.total_jobs} 个职位数据的分析*\n")

        # 薪资分析
        lines.append("## 💰 薪资分析\n")
        if salary and "error" not in salary:
            lines.append(f"- **平均薪资**: {salary.get('avg_min_salary_k', '?')}K - {salary.get('avg_max_salary_k', '?')}K/月")
            lines.append(f"- **中位数薪资**: {salary.get('median_min_salary_k', '?')}K - {salary.get('median_max_salary_k', '?')}K/月")
            lines.append(f"- **薪资范围**: {salary.get('min_salary_k', '?')}K - {salary.get('max_salary_k', '?')}K/月")
            lines.append(f"- **预计平均年薪**: {salary.get('avg_annual_salary_k', '?')}K\n")

            dist = salary.get("salary_distribution", {})
            if dist:
                lines.append("**薪资分布:**")
                for range_name, count in dist.items():
                    pct = round(count / salary.get("valid_count", 1) * 100, 1)
                    bar = "█" * int(pct / 3)
                    lines.append(f"  {range_name:>8}: {bar} {count}个 ({pct}%)")
                lines.append("")
        else:
            lines.append("暂无有效薪资数据\n")

        # 技能分析
        lines.append("## 🛠️ 热门技能需求\n")
        if skills:
            top_skills = list(skills.items())[:15]
            max_count = top_skills[0][1] if top_skills else 1
            lines.append("**排名 | 技能 | 需求量**")
            for i, (skill, count) in enumerate(top_skills, 1):
                bar = "▓" * int(count / max_count * 15)
                lines.append(f"  {i:>2}. {skill:<15} {bar} {count}个")
            lines.append("")

            lines.append("**建议:**")
            must_have = [s for s, c in top_skills[:5]]
            nice_to_have = [s for s, c in top_skills[5:10]]
            lines.append(f"- 必备技能: {', '.join(must_have)}")
            if nice_to_have:
                lines.append(f"- 加分技能: {', '.join(nice_to_have)}")
            lines.append("")

        # 地区分析
        lines.append("## 📍 热门工作地点\n")
        if locations:
            for loc, count in list(locations.items())[:10]:
                pct = round(count / result.total_jobs * 100, 1)
                lines.append(f"  - {loc}: {count}个职位 ({pct}%)")
            lines.append("")

        # 学历分析
        lines.append("## 🎓 学历要求\n")
        if education:
            for edu, count in education.items():
                pct = round(count / result.total_jobs * 100, 1)
                lines.append(f"  - {edu}: {count}个 ({pct}%)")
            lines.append("")

        # 经验分析
        lines.append("## ⏰ 经验要求\n")
        if experience:
            for exp, count in experience.items():
                pct = round(count / result.total_jobs * 100, 1)
                lines.append(f"  - {exp}: {count}个 ({pct}%)")
            lines.append("")

        # 行业分析
        lines.append("## 🏢 行业分布\n")
        if result.industry_summary:
            for ind, count in list(result.industry_summary.items())[:10]:
                lines.append(f"  - {ind}: {count}个")
            lines.append("")

        # 建议
        lines.append("## 💡 求职建议\n")
        lines.append("1. **优先掌握热门技能**: 重点学习排名前5的技能")
        lines.append("2. **关注高薪区间**: 瞄准中位数以上的薪资进行谈判")
        lines.append("3. **多投热门区域**: 职位集中的区域机会更多")
        lines.append("4. **简历定制**: 针对目标岗位的技能关键词优化简历")

        if user_profile:
            lines.append("")
            lines.append("## 🙋 与你的经历匹配建议\n")
            if user_profile.get("years_of_experience"):
                lines.append(f"- 你的经验年限约为 **{user_profile['years_of_experience']}年**，建议在简历中突出可量化成果，以匹配同级岗位薪资区间。")
            if user_profile.get("strengths"):
                lines.append(f"- 你提到的优势: {', '.join(user_profile['strengths'][:4])}，建议放在项目描述首段形成差异化亮点。")
            if user_profile.get("concerns"):
                lines.append(f"- 你当前顾虑: {', '.join(user_profile['concerns'][:3])}，建议优先补齐这些短板并准备对应面试话术。")
            if user_profile.get("goals"):
                lines.append(f"- 你的目标: {', '.join(user_profile['goals'][:3])}，建议拆解为 2-4 周可执行任务，逐步达成。")
        lines.append("")
        lines.append("> 💡 配置 AI API Key (如 OpenAI) 可以获得更深度的个性化分析建议")
        lines.append(f"> 设置环境变量 `AI_API_KEY` 或在 config.json 中配置")

        return "\n".join(lines)

    def _format_job_samples(self, jobs: List[JobDetail]) -> str:
        """格式化职位样本，用于发送给AI"""
        lines = []
        for i, job in enumerate(jobs, 1):
            lines.append(f"{i}. {job.job_name} | {job.company_name} | {job.salary_desc} | {job.city_name}{job.area_district} | 经验:{job.experience} | 学历:{job.education} | 技能:{','.join(job.skills[:5])}")
        return "\n".join(lines)
