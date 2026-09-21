"""防治处方生成：大模型优先，内置模板兜底。

【本次审查修正】

1. **诚实标注处方来源（P0 诚实性缺陷）**。
   原实现在无密钥或调用失败时**静默**回落模板，外部无法分辨。
   而对外材料一直把"大模型个性化处方"作为核心卖点——一旦评审查证，
   就是"声称大模型、实际跑模板"的事实性风险（本赛道对材料不实是直接取消资格）。
   现 `generate()` 返回 `(prescription, source)`，source 为 `"llm"` / `"template"`，
   由响应体透出，界面与答辩口径都能如实呈现。

2. **占位符防护**。若把 `.env.example` 误复制为 `.env`，原实现会认为"已配置密钥"
   而真的发起请求，每次等满 30 秒超时——现场演示的致命事故。
   现由 `config.LLM_ENABLED` 统一把关（占位符与过短密钥均视为未配置）。

3. **收紧超时**。原 `timeout=30` 不区分连接与读取，断网时拖满 30 秒。
   现拆为 `(连接 3.5s, 读取 12s)`，最坏情况显著缩短。

4. **健壮解析**。大模型常把 JSON 包在 ```json 代码块里返回；原实现直接
   `json.loads(content)` 会失败。现先剥离围栏，校验 HTTP 状态码，并校验字段完整性。

5. **补齐日志**。原先所有异常被 `except Exception` 静默吞掉。
"""

import json
import logging
import re
from typing import List, Optional, Tuple

from .config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_CONNECT_TIMEOUT,
    LLM_ENABLED,
    LLM_MODEL,
    LLM_READ_TIMEOUT,
)
from .schemas import Detection, Prescription

logger = logging.getLogger(__name__)

_system_prompt = (
    "你是一名资深植物医生/植保专家。请根据检测到的作物病害信息，"
    "用通俗易懂、面向小农户的语言，输出防治处方。"
    "必须包含：严重程度、防治方案（生物防治优先）、化学用药建议（强调减量增效与安全间隔期）、日常管理提示。"
    "严格以 JSON 返回，字段：disease, severity, summary, biological, chemical, tips。"
)

_REQUIRED_FIELDS = ("disease", "severity", "summary", "biological", "chemical", "tips")

# 匹配 ```json ... ``` 或 ``` ... ``` 围栏
_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


def _strip_fence(text: str) -> str:
    """剥离大模型常见的 markdown 代码块围栏。"""
    m = _FENCE_RE.match(text or "")
    return m.group(1) if m else (text or "")


class Prescriber:
    """处方生成器。"""

    def generate(
        self, detections: List[Detection], severity_grade: Optional[str] = None
    ) -> Tuple[Optional[Prescription], Optional[str]]:
        """生成处方。

        返回 `(处方, 来源)`，来源为 `"llm"` / `"template"` / `None`（无识别结果）。
        `severity_grade` 为可解释性通道量化出的严重度分级，会注入提示词，
        使"分级"与"处方"相互对应，而不是分级了但处方一字不变。
        """
        if not detections:
            return None, None
        top = detections[0]

        if LLM_ENABLED:
            result = self._generate_with_llm(top, detections, severity_grade)
            if result is not None:
                return result, "llm"
            logger.warning("大模型处方不可用，已回落内置模板（识别结果=%s）", top.name)
        else:
            logger.info("未配置有效的大模型密钥，处方使用内置模板（识别结果=%s）", top.name)

        return self._generate_from_template(top, severity_grade), "template"

    # -- 大模型路径 ---------------------------------------------------------

    def _generate_with_llm(
        self,
        top: Detection,
        detections: List[Detection],
        severity_grade: Optional[str],
    ) -> Optional[Prescription]:
        import requests

        user_lines = [
            "检测结果："
            + json.dumps(
                [{"name": d.name, "confidence": d.confidence} for d in detections],
                ensure_ascii=False,
            )
        ]
        if severity_grade:
            user_lines.append(f"图像量化严重度：{severity_grade}")

        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": _system_prompt},
                {"role": "user", "content": "\n".join(user_lines)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
        }
        try:
            r = requests.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json=payload,
                timeout=(LLM_CONNECT_TIMEOUT, LLM_READ_TIMEOUT),
            )
        except Exception:
            logger.exception("调用大模型失败（网络/超时），将回落模板")
            return None

        if r.status_code != 200:
            logger.warning(
                "大模型返回非 200 状态码：%s，响应片段=%s", r.status_code, (r.text or "")[:200]
            )
            return None

        try:
            content = r.json()["choices"][0]["message"]["content"]
        except Exception:
            logger.exception("大模型响应结构异常，无法取到 content")
            return None

        try:
            data = json.loads(_strip_fence(content))
        except Exception:
            logger.exception("大模型返回内容不是合法 JSON，片段=%s", (content or "")[:200])
            return None

        if not isinstance(data, dict) or any(k not in data for k in _REQUIRED_FIELDS):
            logger.warning("大模型返回 JSON 字段不完整，缺失=%s", [
                k for k in _REQUIRED_FIELDS if not isinstance(data, dict) or k not in data
            ])
            return None

        # 字段归一化：**不同模型的返回形态并不一致**，必须统一。
        # 实测（2026-09-20）：多数模型返回字符串，但 qwen3-max 会把分点内容
        # 返回为数组，直接 str() 会得到 "['...', '...']" 这种带方括号与引号的难读结果。
        # 这里统一转成面向农户的纯文本：数组按行拼接，对象按「键：值」拼接。
        normalized = {}
        for k in _REQUIRED_FIELDS:
            v = data[k]
            if isinstance(v, (list, tuple)):
                parts = [str(x).strip() for x in v if str(x).strip()]
                v = "\n".join(parts)
            elif isinstance(v, dict):
                v = "；".join(f"{kk}：{vv}" for kk, vv in v.items())
            else:
                v = str(v).strip()
            normalized[k] = v

        if not all(normalized[k] for k in _REQUIRED_FIELDS):
            logger.warning(
                "大模型返回存在空字段，回落模板：%s",
                [k for k in _REQUIRED_FIELDS if not normalized[k]],
            )
            return None

        try:
            return Prescription(**normalized)
        except Exception:
            logger.exception("构造处方对象失败")
            return None

    # -- 模板兜底 -----------------------------------------------------------

    def _generate_from_template(
        self, top: Detection, severity_grade: Optional[str] = None
    ) -> Prescription:
        disease = top.name
        if "健康" in disease:
            return Prescription(
                disease=disease,
                severity="健康",
                summary="植株当前状态良好，无需防治。",
                biological="保持合理密植与通风透光，增强植株抗性。",
                chemical="无需用药。",
                tips="持续观察，做好水肥管理与田间卫生。",
            )

        severity = severity_grade or "待评估"
        # 按严重度给出不同强度的建议，避免"分级了但处方一字不变"的自相矛盾
        biological = (
            "优先选用抗病品种、清除病残体，使用枯草芽孢杆菌等生物菌剂预防。"
            if severity in ("轻", "待评估")
            else "立即清除并集中销毁病叶病枝；增施生物菌剂与硅钾肥，提高植株抗性；改善通风透光、降低棚内湿度。"
        )
        chemical = (
            "科学用药，坚持减量增效，注意安全间隔期，避免盲目加大剂量。"
            if severity in ("轻", "待评估")
            else "在发病初期及时用药并注意轮换：保护性杀菌剂与内吸性药剂交替使用，严格按标签剂量、遵守安全间隔期，采收前禁用。"
        )
        tips = (
            "请结合当地植保站指导，轮换用药以防产生抗药性。"
            if severity in ("轻", "待评估")
            else "请尽快联系当地植保站或农技人员复核；加强田间巡查，标记并隔离发病中心，防止扩散。"
        )

        return Prescription(
            disease=disease,
            severity=severity,
            summary=f"检测到「{disease}」，建议尽快确认并采取综合防治。",
            biological=biological,
            chemical=chemical,
            tips=tips,
        )
