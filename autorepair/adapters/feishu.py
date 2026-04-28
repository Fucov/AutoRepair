import logging
import json
from typing import Dict, Optional, Any
import httpx
from autorepair.config import config
from autorepair.schemas import Incident

logger = logging.getLogger(__name__)

# 飞书卡片模板ID配置
FEISHU_CARD_TEMPLATES = {
    "incident_detected": "AAqee8J5gdip5",
    "repair_plan_ready": "AAqeNCqwaHHLt",
    "fix_pr_ready": "AAqeNCm0UQQnK",
    "manual_intervention": "AAqeeVyVrY5hw",
    "periodic_digest": "AAqeNCqwaHHLt"
}



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
                "content": f"**服务名称**\n{incident.service_name or incident.service}"
            }
        },
        {
            "is_short": True,
            "text": {
                "tag": "lark_md",
                "content": f"**服务ID**\n{incident.service_id or 'unknown'}"
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
            "is_short": True,
            "text": {
                "tag": "lark_md",
                "content": f"**发生次数**\n{incident.occurrence_count}"
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
            "content": "ℹ️ **当前阶段**：diagnosed\n系统已完成基础核查，后续将由 Doubao Agent 生成修复计划。"
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


def _get_tenant_access_token() -> Optional[str]:
    """获取飞书tenant_access_token"""
    try:
        token_url = f"{config.FEISHU_API_BASE_URL}/auth/v3/tenant_access_token/internal"
        token_response = httpx.post(
            token_url,
            json={
                "app_id": config.FEISHU_APP_ID,
                "app_secret": config.FEISHU_APP_SECRET
            },
            timeout=5
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        return token_data.get("tenant_access_token")
    except Exception as e:
        logger.error(f"获取飞书tenant_access_token失败: {str(e)}")
        return None


def send_template_card(card_type: str, variables: Dict[str, Any]) -> Optional[Dict]:
    """
    通用飞书模板卡片发送方法
    :param card_type: 卡片类型，对应FEISHU_CARD_TEMPLATES中的key
    :param variables: 卡片模板变量
    :return: 发送结果或None
    """
    template_id = FEISHU_CARD_TEMPLATES.get(card_type)
    if not template_id:
        logger.error(f"未知的卡片类型: {card_type}")
        return None

    # 检查配置是否完整
    if not config.is_feishu_ready():
        # 配置不完整，输出模拟卡片
        logger.info("Feishu mode: mock, reason: missing configuration")
        print("\n" + "=" * 80)
        print(f"📧 Mock Feishu Template Card (配置不完整，仅模拟发送)")
        print(f"卡片类型: {card_type}")
        print(f"模板ID: {template_id}")
        print(f"变量数量: {len(variables)}")
        print("=" * 80)
        for key, value in variables.items():
            print(f"{key}: {value}")
        print("=" * 80 + "\n")
        return {"mock": True, "card_type": card_type, "variables": variables}

    try:
        logger.info(f"Feishu mode: real, 发送{card_type}卡片")
        access_token = _get_tenant_access_token()
        if not access_token:
            return None

        # 构造卡片内容
        card_content = json.dumps({
            "type": "template",
            "data": {
                "template_id": template_id,
                "template_variable": variables
            }
        })

        # 发送消息
        send_url = f"{config.FEISHU_API_BASE_URL}/im/v1/messages?receive_id_type=chat_id"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        payload = {
            "receive_id": config.FEISHU_CHAT_ID,
            "content": card_content,
            "msg_type": "interactive"
        }

        send_response = httpx.post(
            send_url,
            headers=headers,
            json=payload,
            timeout=10
        )
        send_response.raise_for_status()
        result = send_response.json()
        logger.info(f"飞书卡片发送成功，message_id: {result.get('data', {}).get('message_id')}")
        return result

    except Exception as e:
        logger.error(f"发送飞书卡片失败: {str(e)}")
        return None


def send_incident_card(incident: Incident) -> Optional[Dict]:
    """
    发送飞书告警卡片（兼容旧版接口，内部使用新的模板卡片发送）
    配置缺失时打印模拟卡片，不中断流程
    返回发送结果或None
    """
    # 导入变量构造器，避免循环导入
    try:
        from autorepair.cards import build_incident_detected_variables
        
        summary = incident.error_summary
        variables = build_incident_detected_variables(
            incident_id=incident.incident_id,
            service_name=incident.service_name or incident.service,
            severity="P2",  # 默认P2级别，后续可根据错误类型动态调整
            error_type=summary.error_type,
            error_message=summary.message,
            occurrence_count=incident.occurrence_count,
            issue_url=incident.issue_url or "",
            report_url=""
        )
        
        return send_template_card("incident_detected", variables)

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
        return None


def get_tenant_access_token() -> tuple[Optional[str], Optional[str]]:
    """获取飞书tenant_access_token，用于测试"""
    if not config.is_feishu_ready():
        return None, "Missing Feishu configuration"
    
    try:
        token_url = f"{config.FEISHU_API_BASE_URL}/auth/v3/tenant_access_token/internal"
        token_response = httpx.post(
            token_url,
            json={
                "app_id": config.FEISHU_APP_ID,
                "app_secret": config.FEISHU_APP_SECRET
            },
            timeout=5
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        
        if token_data.get("code") == 0:
            return token_data.get("tenant_access_token"), None
        else:
            return None, f"Feishu API error: {token_data.get('code')} {token_data.get('msg')}"
    
    except Exception as e:
        return None, f"Request failed: {str(e)}"


def send_text_message(content: str) -> tuple[Optional[Dict], Optional[str]]:
    """发送纯文本消息，用于测试"""
    if not config.is_feishu_ready():
        return {"mock": True, "content": content}, None
    
    token, err = get_tenant_access_token()
    if err:
        return None, err
    
    try:
        send_url = f"{config.FEISHU_API_BASE_URL}/im/v1/messages?receive_id_type=chat_id"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        payload = {
            "receive_id": config.FEISHU_CHAT_ID,
            "content": json.dumps({"text": content}),
            "msg_type": "text"
        }
        
        send_response = httpx.post(
            send_url,
            headers=headers,
            json=payload,
            timeout=10
        )
        send_response.raise_for_status()
        return send_response.json(), None
    
    except Exception as e:
        return None, str(e)
