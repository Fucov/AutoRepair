import sys
from pathlib import Path

# 将项目根目录加入Python路径
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.adapters.github import create_demo_bug_issue
from autorepair.bug_scenarios import BUG_SCENARIOS

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("使用方法: python scripts/create_demo_issue.py <scenario_id>")
        print("可用的scenario_id:")
        for scenario in BUG_SCENARIOS:
            print(f"  {scenario.scenario_id} - {scenario.title}")
        sys.exit(1)
    
    scenario_id = sys.argv[1]
    issue = create_demo_bug_issue(scenario_id)
    if issue:
        print(f"✅ 成功创建GitHub Issue #{issue.number}: {issue.html_url}")
    else:
        print("ℹ️  Issue创建完成（Mock模式或创建失败）")
