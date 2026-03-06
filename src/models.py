"""
数据模型定义 - 职位信息、分析结果等
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
import json


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
    security_id: str = ""               # 安全ID (用于打招呼)
    encrypt_boss_id: str = ""           # 加密Boss ID
    encrypt_brand_id: str = ""          # 加密品牌ID
    boss_name: str = ""                 # HR/Boss名称
    boss_title: str = ""                # HR/Boss职位
    job_description: str = ""           # 职位描述
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
            security_id=data.get("securityId", ""),
            encrypt_boss_id=data.get("encryptBossId", ""),
            encrypt_brand_id=data.get("encryptBrandId", ""),
            boss_name=data.get("bossName", ""),
            boss_title=data.get("bossTitle", ""),
            address=data.get("address", ""),
            scraped_at=datetime.now().isoformat(),
        )

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

            salary_part = salary_part.upper().replace("K", "").replace("元/月", "").replace("元/天", "")

            if "-" in salary_part:
                min_str, max_str = salary_part.split("-", 1)
                salary_min = int(float(min_str.strip()))
                salary_max = int(float(max_str.strip()))
            elif salary_part.strip().isdigit():
                salary_min = salary_max = int(salary_part.strip())

        except Exception:
            pass

        return salary_min, salary_max, months


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
    "全国": "100010000",
}

# 经验代码映射
EXPERIENCE_CODES = {
    "不限": "",
    "在校生": "108",
    "应届生": "102",
    "一年以内": "103",
    "1-3年": "104",
    "3-5年": "105",
    "5-10年": "106",
    "10年以上": "107",
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
