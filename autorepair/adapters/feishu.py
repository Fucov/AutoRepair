import logging
from typing import Dict, Optional
import httpx

from autorepair.config import (
    FEISHU_API_BASE_URL,
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    FEISHU_CHAT_ID
)
from autorepair.schemas import Incident

logger = logging.getLogger(__name__)


def build_incident_card_payload(incident: Incident) -> Dict:
    """构造飞书消息卡片Payload"""
    summary = incident.error_summary
    elements = []
    
    # 基础信息
    base_fields = [
        {
            "is_short": True,
            "text": {
                "tag": "lark_md",
                "content": f"**来源**\n{incident.source}"
            }
        },
        {
            "is_short": True,
            "text": {
                "tag": "lark_md",
                "content": f"**服务名称**\n{incident.service}"
            }
        },
        {
            "is_short": True,
            "text": {
                "tag": "lark_md",
                "content": f"**状态**\n{incident.status}"
            }
        },
        {
            "is_short": True,
            "text": {
                "tag": "lark_md",
                "content": f"**错误类型**\n{summary.error_type}"
            }
        },
        {
            "is_short": True,
            "text": {
                "tag": "lark_md",
                "content": f"**错误位置**\n{summary.suspected_file}:{summary.line_no}"
            }
        },
        {
            "is_short": False,
            "text": {
                "tag": "lark_md",
                "content": f"**错误信息**\n{summary.message}"
            }
        }
    ]
    
    # 场景信息
    if incident.scenario_id:
        base_fields.append({
            "is_short": True,
            "text": {
                "tag": "lark_md",
                "content": f"**场景**\n{incident.scenario_id}"
            }
        })
    
    # Issue链接
    if incident.issue_url:
        base_fields.append({
            "is_short": False,
            "text": {
                "tag": "lark_md",
                "content": f"**Issue链接**\n[{incident.issue_url}]({incident.issue_url})"
            }
        })
    
    elements.append({
        "tag": "div",
        "fields": base_fields
    })
    
    # 分割线
    elements.append({"tag": "hr"})
    
    # 阶段说明
    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": "ℹ️ **当前阶段**：已接收问题，等待 Agent 分析与自动修复"
        }
    })
    
    # 创建时间
    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": f"**创建时间**\n{incident.created_at}"
        }
    })
    
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🚨 服务异常告警 {incident.incident_id}"
                },
                "template": "red"
            },
            "elements": elements
        }
    }


def send_incident_card(incident: Incident) -> None:
    """
    发送飞书告警卡片
    配置缺失时打印模拟卡片，不中断流程
    """
    # 检查配置是否完整
    if not all([FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_CHAT_ID]):
        # 配置不完整，输出模拟卡片
        summary = incident.error_summary
        print("\n" + "=" * 60)
        print("📧 Mock Feishu Card (配置不完整，仅模拟发送)")
        print("=" * 60)
        print(f"🚨 服务异常告警 {incident.incident_id}")
        print(f"来源: {incident.source}")
        print(f"服务名称: {incident.service}")
        print(f"状态: {incident.status}")
        if incident.scenario_id:
            print(f"场景: {incident.scenario_id}")
        print(f"错误类型: {summary.error_type}")
        print(f"错误位置: {summary.suspected_file}:{summary.line_no}")
        print(f"错误信息: {summary.message}")
        if incident.issue_url:
            print(f"Issue链接: {incident.issue_url}")
        print(f"创建时间: {incident.created_at}")
        print("ℹ️ 当前阶段：已接收问题，等待 Agent 分析与自动修复")
        print("=" * 60 + "\n")
        return

    try:
        # 第一步：获取tenant_access_token
        token_url = f"{FEISHU_API_BASE_URL}/auth/v3/tenant_access_token/internal"
        token_response = httpx.post(
            token_url,
            json={
                "app_id": FEISHU_APP_ID,
                "app_secret": FEISHU_APP_SECRET
            },
            timeout=5
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        access_token = token_data.get("tenant_access_token")
        if not access_token:
            logger.error("获取飞书tenant_access_token失败")
            return

        # 第二步：发送消息
        send_url = f"{FEISHU_API_BASE_URL}/im/v1/messages?receive_id_type=chat_id"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        payload = {
            "receive_id": FEISHU_CHAT_ID,
            "content": build_incident_card_payload(incident),
            "msg_type": "interactive"
        }

        send_response = httpx.post(
            send_url,
            headers=headers,
            json=payload,
            timeout=10
        )
        send_response.raise_for_status()
        logger.info(f"飞书告警卡片发送成功，Incident ID: {incident.incident_id}")

    except Exception as e:
        logger.error(f"发送飞书卡片失败: {str(e)}，已降级为本地通知")
        # 发送失败也降级为模拟输出
        summary = incident.error_summary
        print("\n" + "=" * 60)
        print("📧 Fallback Local Notification (飞书发送失败)")
        print("=" * 60)
        print(f"🚨 服务异常告警 {incident.incident_id}")
        print(f"错误类型: {summary.error_type}")
        print(f"错误位置: {summary.suspected_file}:{summary.line_no}")
        print(f"错误信息: {summary.message}")
        print("=" * 60 + "\n")
