import os
import logging
import requests


logger = logging.getLogger("weekreport.siliconflow")


def llm_summary_enabled() -> bool:
    """读取环境变量，判断是否启用 LLM 摘要。"""
    flag = str(os.getenv("LLM_SUMMARY_ENABLED", os.getenv("SILICONFLOW_SUMMARY_ENABLED", "false"))).strip().lower()
    return flag in {"1", "true", "yes", "y"}


def _strip_html(html: str) -> str:
    """简单移除 HTML 标签，保留换行，便于喂给大模型。"""
    import re
    text = re.sub(r"<br\s*/?>", "\n", html or "")
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.S)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    return text


def summarize_weekly_html(html: str) -> str | None:
    """
    使用硅基流动平台的大模型对周报整体内容进行中文摘要。
    返回纯文本摘要；失败或未启用时返回 None。
    """
    if not llm_summary_enabled():
        return None

    api_key = os.getenv("SILICONFLOW_API_KEY")
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/")
    model = os.getenv("SILICONFLOW_MODEL", "Qwen2.5-14B-Instruct")

    if not api_key:
        logger.warning("SiliconFlow API key missing, skip LLM summary.")
        return None

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    content = _strip_html(html)
    system_prompt = (
        "你是资深项目经理。阅读输入的‘本周周报汇总’文本（表格列包含：成员、本周工作、下周计划、风险与问题），"
        "请仅按以下固定格式输出，不要添加任何开头/结尾/致敬语/说明文字：\n\n"
        "本周工作内容\n"
        "人名A\n"
        "- 任务1\n"
        "- 任务2\n"
        "人名B\n"
        "- 任务1\n"
        "- 任务2\n"
        "下周待办\n"
        "人名A\n"
        "- 待办1\n"
        "- 待办2\n"
        "人名B\n"
        "- 待办1\n"
        "- 待办2\n"
        "目前风险\n"
        "- 风险描述1\n"
        "- 风险描述2\n\n"
        "要求：\n"
        "- 语言为中文、内容简洁可执行；每人每部分 1-4 条；相似项合并、避免重复。\n"
        "- 仅保留人名与事项，不含部门/职位/项目名（除非必要理解）。\n"
        "- 无信息则写‘暂无’；无风险则输出‘暂无’。\n"
        "- 严格保持以上标题与短横线格式，避免多余空行与额外说明。"
    )
    user_prompt = (
        "以下是本周周报的聚合文本（包含成员、本周工作、下周计划、风险与问题），"
        "请抽取各成员对应的工作、下周计划与总体风险，按指定模板输出：\n\n"
        + content
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": float(os.getenv("SILICONFLOW_TEMPERATURE", "0.2")),
        "max_tokens": int(os.getenv("SILICONFLOW_MAX_TOKENS", "1024")),
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        ok = 200 <= resp.status_code < 300
        if not ok:
            logger.warning("SiliconFlow summary failed status=%s body=%s", resp.status_code, resp.text[:300])
            return None
        data = resp.json()
        text = (
            (data.get("choices") or [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not text:
            logger.warning("SiliconFlow summary empty content.")
            return None
        logger.info("SiliconFlow summary generated, len=%s", len(text))
        return text
    except Exception:
        logger.exception("SiliconFlow summary exception")
        return None