"""
职探AI - 主程序入口
爬取Boss直聘职位数据，进行AI分析，生成职业建议报告
"""

import sys
import os
import argparse

# 确保可以 import src 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config
from src.scraper import BossZhipinScraper
from src.analyzer import JobAnalyzer
from src.report import ReportGenerator
from src.models import SearchQuery, CITY_CODES


def main():
    parser = argparse.ArgumentParser(
        description="🔍 职探AI - Boss直聘职位分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 搜索 Python 开发岗位并分析
  python main.py search --keyword "Python开发" --city 北京 --pages 3

    # 搜索并生成 HTML 可视化报告
  python main.py search --keyword "前端工程师" --city 上海 --html

  # 获取推荐职位并分析
  python main.py recommend --pages 2

  # 从已保存的数据生成报告
  python main.py analyze --file data/jobs_20260302.json

  # 初始化配置
  python main.py init

  # 设置Cookie
  python main.py set-cookie --cookie "your_cookie_string" --bst "your_bst"
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # search 命令
    sp_search = subparsers.add_parser("search", help="按关键词搜索职位并分析")
    sp_search.add_argument("--keyword", "-k", required=True, help="搜索关键词 (如 'Python开发')")
    sp_search.add_argument("--city", "-c", default="北京", help="城市名称 (默认:北京)")
    sp_search.add_argument("--experience", "-e", default="", help="经验要求: 不限/应届生/1-3年/3-5年/5-10年/10年以上")
    sp_search.add_argument("--education", "-d", default="", help="学历要求: 不限/大专/本科/硕士/博士")
    sp_search.add_argument("--salary", "-s", default="", help="薪资范围: 不限/3K以下/3-5K/5-10K/10-20K/20-50K/50K以上")
    sp_search.add_argument("--pages", "-p", type=int, default=3, help="爬取页数 (默认:3)")
    sp_search.add_argument("--html", action="store_true", help="生成 HTML 富文本报告")
    sp_search.add_argument("--save", action="store_true", default=True, help="保存职位数据 (默认:True)")

    # recommend 命令
    sp_rec = subparsers.add_parser("recommend", help="获取推荐职位并分析")
    sp_rec.add_argument("--pages", "-p", type=int, default=3, help="获取页数 (默认:3)")
    sp_rec.add_argument("--html", action="store_true", help="生成 HTML 报告")

    # analyze 命令 (从文件分析)
    sp_analyze = subparsers.add_parser("analyze", help="从已保存的数据文件分析")
    sp_analyze.add_argument("--file", "-f", required=True, help="JSON 数据文件路径")
    sp_analyze.add_argument("--keyword", "-k", default="", help="搜索关键词 (用于报告标题)")
    sp_analyze.add_argument("--html", action="store_true", help="生成 HTML 报告")

    # set-cookie 命令
    sp_cookie = subparsers.add_parser("set-cookie", help="设置登录 Cookie")
    sp_cookie.add_argument("--cookie", required=True, help="Cookie 字符串")
    sp_cookie.add_argument("--bst", default="", help="BST Token")

    # init 命令
    sp_init = subparsers.add_parser("init", help="交互式初始化配置")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 加载配置
    config = Config.load()

    if args.command == "init":
        interactive_init(config)
    elif args.command == "set-cookie":
        cmd_set_cookie(config, args)
    elif args.command == "search":
        cmd_search(config, args)
    elif args.command == "recommend":
        cmd_recommend(config, args)
    elif args.command == "analyze":
        cmd_analyze(config, args)


def interactive_init(config: Config):
    """交互式初始化配置"""
    print("\n🔧 职探AI 配置向导\n")

    # AI API 配置
    print("== AI 分析配置 (可选，留空跳过) ==")
    print("支持 OpenAI / DeepSeek / 其他兼容 API")
    api_key = input(f"  AI API Key [{config.ai_api_key[:8] + '...' if config.ai_api_key else '未设置'}]: ").strip()
    if api_key:
        config.ai_api_key = api_key

    base_url = input(f"  AI Base URL [{config.ai_base_url}]: ").strip()
    if base_url:
        config.ai_base_url = base_url

    model = input(f"  AI Model [{config.ai_model}]: ").strip()
    if model:
        config.ai_model = model

    # 爬取配置
    print("\n== 爬取配置 ==")
    delay = input(f"  请求间隔(秒) [{config.request_delay}]: ").strip()
    if delay:
        config.request_delay = float(delay)

    max_pages = input(f"  每次搜索最大页数 [{config.max_pages_per_search}]: ").strip()
    if max_pages:
        config.max_pages_per_search = int(max_pages)
    
    config.save()
    print("\n✅ 配置完成!")

    use_mcp = input("\n 是否使用 MCP 服务器登录 Boss 直聘? (y/N): ").lower().strip() == 'y'
    if use_mcp:
        scraper = BossZhipinScraper(config)
        success = scraper.load_cookie_from_mcp()
        if success:
            config.save() # 保存获取到的 cookie 到 config
            print("✅ MCP 登录成功，配置已保存。")
        else:
            print("❌ MCP 登录失败。")

def cmd_set_cookie(config: Config, args):
    """设置 Cookie"""
    config.cookie = args.cookie
    config.bst = args.bst
    config.save()
    print("✅ Cookie 已保存")


def cmd_search(config: Config, args):
    """搜索职位并分析"""
    if not config.cookie:
        print("❌ 未设置 Cookie，请先登录")
        print("   方式1: 运行 mcp-bosszp 服务器扫码登录，然后 python main.py set-cookie --cookie '...'")
        print("   方式2: 从浏览器直接复制 Boss直聘的 Cookie")
        return

    scraper = BossZhipinScraper(config)
    analyzer = JobAnalyzer(config)
    reporter = ReportGenerator(config)

    # 构建搜索参数
    city_code = CITY_CODES.get(args.city, CITY_CODES.get("北京"))
    query = SearchQuery(
        keyword=args.keyword,
        city=city_code,
        city_name=args.city,
        experience=args.experience,
        education=args.education,
        salary=args.salary,
        max_pages=args.pages,
    )

    # 搜索
    jobs = scraper.search_jobs(query)

    if not jobs:
        print("😅 没有找到任何职位，请检查关键词或登录状态")
        return

    # 保存数据
    if args.save:
        scraper.save_jobs(jobs)

    # 分析
    result = analyzer.analyze(jobs, query=args.keyword)

    # 生成报告
    reporter.generate_console_report(result)
    reporter.generate_pdf(result, jobs)

    if args.html:
        filepath = reporter.generate_html(result, jobs)
        print(f"\n🌐 用浏览器打开 HTML 报告查看可视化图表")


def cmd_recommend(config: Config, args):
    """获取推荐职位并分析"""
    if not config.cookie:
        print("❌ 未设置 Cookie，请先登录")
        return

    scraper = BossZhipinScraper(config)
    analyzer = JobAnalyzer(config)
    reporter = ReportGenerator(config)

    jobs = scraper.get_recommend_jobs(max_pages=args.pages)

    if not jobs:
        print("😅 没有获取到推荐职位")
        return

    scraper.save_jobs(jobs)
    result = analyzer.analyze(jobs, query="推荐职位")

    reporter.generate_console_report(result)
    reporter.generate_pdf(result, jobs)

    if args.html:
        reporter.generate_html(result, jobs)


def cmd_analyze(config: Config, args):
    """从文件分析"""
    scraper = BossZhipinScraper(config)
    analyzer = JobAnalyzer(config)
    reporter = ReportGenerator(config)

    jobs = scraper.load_jobs(args.file)

    if not jobs:
        print("😅 文件中没有职位数据")
        return

    keyword = args.keyword or os.path.basename(args.file).replace(".json", "")
    result = analyzer.analyze(jobs, query=keyword)

    reporter.generate_console_report(result)
    reporter.generate_pdf(result, jobs)

    if args.html:
        filepath = reporter.generate_html(result, jobs)


if __name__ == "__main__":
    main()
