import json
from typing import List, Optional

from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from .schemas import Detection, Prescription

_system_prompt = (
    "你是一名资深植物医生/植保专家。请根据检测到的作物病害信息，"
    "用通俗易懂、面向小农户的语言，输出防治处方。"
    "必须包含：严重程度、防治方案（生物防治优先）、化学用药建议（强调减量增效与安全间隔期）、日常管理提示。"
    "严格以 JSON 返回，字段：disease, severity, summary, biological, chemical, tips。"
)


class Prescriber:
    def generate(self, detections: List[Detection]) -> Optional[Prescription]:
        if not detections:
            return None
        top = detections[0]
        if LLM_API_KEY:
            return self._generate_with_llm(top, detections)
        return self._generate_from_template(top)

    def _generate_with_llm(self, top: Detection, detections: List[Detection]) -> Prescription:
        import requests

        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": _system_prompt},
                {
                    "role": "user",
                    "content": "检测结果：" + json.dumps(
                        [{"name": d.name, "confidence": d.confidence} for d in detections],
                        ensure_ascii=False,
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
        }
        try:
            r = requests.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json=payload,
                timeout=30,
            )
            content = r.json()["choices"][0]["message"]["content"]
            return Prescription(**json.loads(content))
        except Exception:
            return self._generate_from_template(top)

    def _generate_from_template(self, top: Detection) -> Prescription:
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
        return Prescription(
            disease=disease,
            severity="待评估",
            summary=f"检测到「{disease}」，建议尽快确认并采取综合防治。",
            biological="优先选用抗病品种、清除病残体，使用枯草芽孢杆菌等生物菌剂预防。",
            chemical="科学用药，坚持减量增效，注意安全间隔期，避免盲目加大剂量。",
            tips="请结合当地植保站指导，轮换用药以防产生抗药性。",
        )