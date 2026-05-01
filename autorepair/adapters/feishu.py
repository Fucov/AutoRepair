import logging
import json
from typing import Dict, Optional, Any
import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from autorepair.config import config
from autorepair.schemas import Incident

logger = logging.getLogger(__name__)

# 飞书卡片模板ID配置
FEISHU_CARD_TEMPLATES = {
    "incident_detected": "AAqee8J5gdip5",
    "repair_plan_ready": "AAqeNCqwaHHLt",
    "fix_pr_ready": "AAqeNCm0UQQnK",
    "manual_intervention": "AAqeeVyVrY5hw",
    "periodic_digest": "AAqeeV3GS2JUd"
}

# 初始化飞书客户端
_lark_client: Optional[lark.Client] = None

def _get_lark_client() -> Optional[lark.Client]:
    """获取飞书客户端实例"""
    global _lark_client
    if not _lark_client:
        if not config.FEISHU_APP_ID or not config.FEISHU_APP_SECRET:
            logger.error("飞书APP ID或SECRET未配置")
            return None
        _lark_client = lark.Client.builder() \
            .app_id(config.FEISHU_APP_ID) \
            .app_secret(config.FEISHU_APP_SECRET) \
            .log_level(lark.LogLevel.ERROR) \
            .build()
    return _lark_client



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
            "is_short": True,
            "text": {
                "tag": "lark_md",
                "content": f"**指纹**\n{summary.fingerprint}"
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
            "content": "ℹ️ **当前阶段**：diagnosed\n系统已完成基础核查，等待 Agent 分析与自动修复。"
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
        print("=" * 80)
        for key, value in variables.items():
            print(f"{key}: {value}")
        print("=" * 80 + "\n")
        return {"mock": True, "card_type": card_type, "variables": variables}

    try:
        logger.info(f"Feishu mode: real, 发送{card_type}卡片")
        client = _get_lark_client()
        if not client:
            return None

        # 构造卡片内容
        card_content = json.dumps({
            "type": "template",
            "data": {
                "template_id": template_id,
                "template_variable": variables
            }
        })

        # 自动判断receive_id类型：ou_开头是用户open_id，oc_开头是群chat_id
        receive_id = config.FEISHU_CHAT_ID
        if receive_id.startswith("ou_"):
            receive_id_type = "open_id"
        elif receive_id.startswith("oc_"):
            receive_id_type = "chat_id"
        else:
            receive_id_type = "open_id"

        # 构造请求，完全对齐官方示例
        request = CreateMessageRequest.builder() \
            .receive_id_type(receive_id_type) \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .msg_type("interactive")
                .content(card_content)
                .build()
            ) \
            .build()

        # 发送请求
        response = client.im.v1.message.create(request)
        if not response.success():
            logger.error(f"发送飞书卡片失败, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")
            print(f"飞书API错误详情: code={response.code}, msg={response.msg}, log_id={response.get_log_id()}")
            return None

        logger.info(f"飞书卡片发送成功，message_id: {response.data.message_id}")
        return {
            "code": 0,
            "data": {
                "message_id": response.data.message_id
            }
        }

    except Exception as e:
        logger.error(f"发送飞书卡片失败: {str(e)}", exc_info=True)
        print(f"发送异常: {str(e)}")
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


def send_repair_plan_ready(
    incident_id: str,
    service_name: str,
    diagnosis_brief: str,
    fix_strategy: str,
    risk_level: str,
    policy_result: str,
    report_url: str = "",
) -> Optional[Dict]:
    from autorepair.cards import build_repair_plan_ready_variables

    return send_template_card(
        "repair_plan_ready",
        build_repair_plan_ready_variables(
            incident_id=incident_id,
            service_name=service_name,
            diagnosis_brief=diagnosis_brief,
            fix_strategy=fix_strategy,
            risk_level=risk_level,
            policy_result=policy_result,
            report_url=report_url,
        ),
    )


def send_manual_intervention(
    incident_id: str,
    service_name: str,
    reason_brief: str,
    evidence_brief: str,
    suggested_action: str,
    issue_url: str = "",
    report_url: str = "",
) -> Optional[Dict]:
    from autorepair.cards import build_manual_intervention_variables

    return send_template_card(
        "manual_intervention",
        build_manual_intervention_variables(
            incident_id=incident_id,
            service_name=service_name,
            reason_brief=reason_brief,
            evidence_brief=evidence_brief,
            suggested_action=suggested_action,
            issue_url=issue_url,
            report_url=report_url,
        ),
    )


def send_fix_pr_ready(
    incident_id: str,
    service_name: str,
    pr_number: int,
    pr_title: str,
    fix_brief: str,
    test_brief: str,
    risk_level: str,
    pr_url: str,
    report_url: str = "",
) -> Optional[Dict]:
    from autorepair.cards import build_fix_pr_ready_variables

    if not pr_url:
        return None
    return send_template_card(
        "fix_pr_ready",
        build_fix_pr_ready_variables(
            incident_id=incident_id,
            service_name=service_name,
            pr_number=pr_number,
            pr_title=pr_title,
            fix_brief=fix_brief,
            test_brief=test_brief,
            risk_level=risk_level,
            pr_url=pr_url,
            report_url=report_url,
        ),
    )


def send_fix_pr_ready_card(
    incident_id: str,
    issue_number: int,
    pr_url: str,
    pr_title: str,
    fix_summary: str,
    risk_level: str,
) -> Optional[Dict]:
    """
    兼容executor.py中的调用接口
    """
    return send_fix_pr_ready(
        incident_id=incident_id,
        service_name="demo_service",
        pr_number=int(pr_url.split("/")[-1]) if pr_url.startswith("http") else 0,
        pr_title=pr_title,
        fix_brief=fix_summary,
        test_brief="目标测试和全量测试均通过",
        risk_level=risk_level,
        pr_url=pr_url,
    )


def send_manual_intervention_card(
    incident_id: str,
    issue_number: int,
    error_message: str,
) -> Optional[Dict]:
    """
    兼容executor.py和sync_pr_status_once.py中的调用接口
    """
    return send_manual_intervention(
        incident_id=incident_id,
        service_name="demo_service",
        reason_brief="修复失败，需要人工介入",
        evidence_brief=error_message[:200] + "..." if len(error_message) > 200 else error_message,
        suggested_action=f"请查看Issue #{issue_number}并进行处理",
        issue_url=f"https://github.com/issues/{issue_number}" if issue_number else "",
    )


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
