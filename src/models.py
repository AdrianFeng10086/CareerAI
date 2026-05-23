"""
数据模型定义 - 职位信息、分析结果等
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import re
from urllib.parse import urlencode


@dataclass
class JobDetail:
    """职位详细信息"""
    job_id: str = ""
    job_name: str = ""                  # 职位名称
    salary_desc: str = ""               # 薪资描述 (如 "15-25K·14薪")
    salary_min: int = 0                 # 最低薪资 (K)
    salary_max: int = 0                 # 最高薪资 (K)
    salary_months: int = 12             # 薪资月数
    city_name: str = ""                 # 城市
    area_district: str = ""             # 区域
    business_district: str = ""         # 商圈
    experience: str = ""                # 经验要求
    education: str = ""                 # 学历要求
    job_type: str = ""                  # 工作类型(全职/兼职)
    skills: List[str] = field(default_factory=list)     # 技能标签
    job_labels: List[str] = field(default_factory=list) # 职位标签
    company_name: str = ""              # 公司名称
    company_scale: str = ""             # 公司规模
    industry: str = ""                  # 行业
    job_description: str = ""           # 职位描述
    url: str = ""                       # 招聘链接
    address: str = ""                   # 详细地址
    scraped_at: str = ""                # 爬取时间

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_api_response(cls, data: dict) -> "JobDetail":
        """从Boss直聘API响应解析职位信息"""
        salary_desc = data.get("salaryDesc", "")
        salary_min, salary_max, salary_months = cls._parse_salary(salary_desc)

        return cls(
            job_id=data.get("encryptJobId", ""),
            job_name=data.get("jobName", ""),
            salary_desc=salary_desc,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_months=salary_months,
            city_name=data.get("cityName", ""),
            area_district=data.get("areaDistrict", ""),
            business_district=data.get("businessDistrict", ""),
            experience=data.get("jobExperience", ""),
            education=data.get("jobDegree", ""),
            skills=data.get("skills", []),
            job_labels=data.get("jobLabels", []),
            company_name=data.get("brandName", ""),
            company_scale=data.get("brandScaleName", ""),
            industry=data.get("brandIndustry", "") or data.get("industry", ""),
            address=data.get("address", ""),
            url=cls._build_job_url(data),
            scraped_at=datetime.now().isoformat(),
        )

    @staticmethod
    def _build_job_url(data: dict) -> str:
        existing = (
            str(data.get("jobUrl", "") or "").strip()
            or str(data.get("postUrl", "") or "").strip()
            or str(data.get("jobHref", "") or "").strip()
            or str(data.get("href", "") or "").strip()
        )
        job_id = str(data.get("encryptJobId", "") or "").strip()
        security_id = str(data.get("securityId", "") or "").strip()
        ka_value = str(data.get("ka", "") or "").strip()

        if existing and "job_detail" in existing and ("securityId=" in existing or not security_id):
            return existing

        if not job_id:
            return existing

        base = f"https://www.zhipin.com/job_detail/{job_id}.html"
        params: Dict[str, str] = {}
        if security_id:
            params["securityId"] = security_id
        if ka_value:
            params["ka"] = ka_value
        if params:
            return f"{base}?{urlencode(params)}"
        return base

    @staticmethod
    def _parse_salary(salary_desc: str) -> tuple:
        """解析薪资描述，返回 (最低K, 最高K, 月数)"""
        salary_min, salary_max, months = 0, 0, 12
        if not salary_desc:
            return salary_min, salary_max, months

        try:
            # 处理 "15-25K·14薪" 格式
            parts = salary_desc.split("·")
            salary_part = parts[0].strip()

            if len(parts) > 1:
                month_str = parts[1].replace("薪", "").strip()
                try:
                    months = int(month_str)
                except ValueError:
                    months = 12

            salary_norm = salary_part.lower().replace("／", "/")
            salary_norm = salary_norm.replace("每月", "").replace("元/月", "")

            # 统一换算到“月薪K”：时薪按 8 小时/天、21.75 天/月折算，日薪按 21.75 天/月折算
            multiplier = 1.0
            if "元/时" in salary_norm or "元/小时" in salary_norm:
                multiplier = (8.0 * 21.75) / 1000.0
            elif "元/天" in salary_norm or "元/日" in salary_norm:
                multiplier = 21.75 / 1000.0

            salary_norm = (
                salary_norm.replace("元/时", "")
                .replace("元/小时", "")
                .replace("元/天", "")
                .replace("元/日", "")
                .replace("元", "")
            )

            # 统一分隔符，兼容 15~25k / 15至25k / 15-25k
            salary_norm = salary_norm.replace("~", "-").replace("至", "-")

            # 区间模式，支持两侧各自带单位，如 35k-50k / 1.5万-2万
            m_range = re.search(
                r"(\d+(?:\.\d+)?)\s*([kw万千]?)\s*-\s*(\d+(?:\.\d+)?)\s*([kw万千]?)",
                salary_norm,
            )
            if m_range:
                left = float(m_range.group(1))
                left_unit = m_range.group(2)
                right = float(m_range.group(3))
                right_unit = m_range.group(4)
                if not left_unit and right_unit:
                    left_unit = right_unit
                if not right_unit and left_unit:
                    right_unit = left_unit
                salary_min = int(JobDetail._to_k(left, left_unit) * multiplier)
                salary_max = int(JobDetail._to_k(right, right_unit) * multiplier)
            else:
                m_single = re.search(r"(\d+(?:\.\d+)?)\s*([kw万千]?)", salary_norm)
                if m_single:
                    value = float(m_single.group(1))
                    unit = m_single.group(2)
                    parsed = int(JobDetail._to_k(value, unit) * multiplier)
                    salary_min = salary_max = parsed

            if salary_min > 0 and salary_max > 0 and salary_min > salary_max:
                salary_min, salary_max = salary_max, salary_min

        except Exception:
            pass

        return salary_min, salary_max, months

    @staticmethod
    def _to_k(value: float, unit: str) -> int:
        unit = (unit or "").lower()
        if unit in {"w", "万"}:
            return int(value * 10)
        if unit in {"k", "千"}:
            return int(value)
        # 无单位时做容错:
        # 1) >=1000 通常是“元”写法(如 8000-12000)，换算为 K；
        # 2) 否则按 K 处理，兼容 8-15 这类写法。
        if value >= 1000:
            return int(round(value / 1000.0))
        return int(value)


@dataclass
class SearchQuery:
    """搜索查询参数"""
    keyword: str = ""           # 搜索关键词 (如 "Python开发")
    city: str = "101010100"     # 城市代码 (默认北京)
    city_name: str = "北京"     # 城市名称
    experience: str = ""        # 经验要求
    education: str = ""         # 学历要求
    salary: str = ""            # 薪资范围
    job_type: str = ""          # 工作类型
    page: int = 1               # 页码
    page_size: int = 15         # 每页数量
    max_pages: int = 3          # 最大爬取页数


@dataclass
class AnalysisResult:
    """AI分析结果"""
    query: str = ""                                     # 搜索关键词
    total_jobs: int = 0                                 # 职位总数
    salary_summary: Dict[str, Any] = field(default_factory=dict)  # 薪资统计
    skill_summary: Dict[str, int] = field(default_factory=dict)   # 技能统计
    location_summary: Dict[str, int] = field(default_factory=dict) # 地区统计
    education_summary: Dict[str, int] = field(default_factory=dict) # 学历统计
    experience_summary: Dict[str, int] = field(default_factory=dict) # 经验统计
    industry_summary: Dict[str, int] = field(default_factory=dict)  # 行业统计
    user_profile: Dict[str, Any] = field(default_factory=dict)       # 用户经历/偏好画像
    ai_insights: str = ""           # AI 深度分析建议
    analyzed_at: str = ""           # 分析时间

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent=2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# 城市代码映射
CITY_CODES = {
    "全国": "100010000",
    "北京": "101010100",
    "上海": "101020100",
    "广州": "101280100",
    "深圳": "101280600",
    "杭州": "101210100",
    "成都": "101270100",
    "南京": "101190100",
    "武汉": "101200100",
    "西安": "101110100",
    "苏州": "101190400",
    "长沙": "101250100",
    "郑州": "101180100",
    "青岛": "101120200",
    "大连": "101070200",
    "厦门": "101230200",
    "重庆": "101040100",
    "天津": "101030100",
    "珠海": "101280700",
    "佛山": "101280800",
    "东莞": "101281600",
    "合肥": "101220100",
    "济南": "101120100",
    "福州": "101230100",
    "昆明": "101290100",
    "沈阳": "101070100",
    "哈尔滨": "101050100",
    "长春": "101060100",
    "太原": "101100100",
    "石家庄": "101090100",
    "南昌": "101240100",
    "南宁": "101300100",
    "贵阳": "101260100",
    "兰州": "101160100",
    "乌鲁木齐": "101130100",
    "呼和浩特": "101150100",
    "海口": "101310100",
    "宁波": "101210400",
    "无锡": "101190200",
    "温州": "101210700",
    "金华": "101210900",
    "嘉兴": "101210300",
    "台州": "101210600",
    "绍兴": "101210500",
    "常州": "101191100",
    "南通": "101190600",
    "扬州": "101190800",
    "徐州": "101191000",
    "烟台": "101120500",
    "潍坊": "101120600",
    "临沂": "101121300",
    "淄博": "101120300",
    "泉州": "101230500",
    "漳州": "101230600",
    "莆田": "101230400",
    "惠州": "101280300",
    "中山": "101281700",
    "江门": "101281100",
    "湛江": "101281500",
    "保定": "101090200",
    "唐山": "101090500",
    "邯郸": "101090600",
    "洛阳": "101180300",
    "南阳": "101180700",
    "襄阳": "101200200",
    "宜昌": "101200400",
    "岳阳": "101250200",
    "衡阳": "101250300",
    "株洲": "101250400",
    "赣州": "101240700",
    "九江": "101240200",
    "芜湖": "101220300",
    "马鞍山": "101220400",
    "桂林": "101300300",
    "柳州": "101300400",
    "三亚": "101310200",
    "泸州": "101270300",
    "绵阳": "101270400",
    "南充": "101270600",
    "遵义": "101260300",
    "咸阳": "101110200",
    "宝鸡": "101110300",
    "榆林": "101110400",
    "银川": "101170100",
    "西宁": "101140100",
    "拉萨": "101140200"
}

# 经验代码映射
EXPERIENCE_CODES = {
    "不限": "",
    "在校生": "108",
    "应届生": "102",
    "经验不限": "101",
    "1年以内": "103",
    "一年以内": "103",
    "1-3年": "104",
    "一到三年": "104",
    "3-5年": "105",
    "三到五年": "105",
    "5-10年": "106",
    "五到十年": "106",
    "10年以上": "107",
    "十年以上": "107",
}

# 学历代码映射
EDUCATION_CODES = {
    "不限": "",
    "初中及以下": "209",
    "中专/中技": "208",
    "高中": "206",
    "大专": "202",
    "本科": "203",
    "硕士": "204",
    "博士": "205",
}

# 薪资代码映射
SALARY_CODES = {
    "不限": "",
    "3K以下": "402",
    "3-5K": "403",
    "5-10K": "404",
    "10-20K": "405",
    "20-50K": "406",
    "50K以上": "407",
}
